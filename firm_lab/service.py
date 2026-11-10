import base64
import copy
import json
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .db import Store, LabError, uid, now, digest, rows, get, put, meta, audit
from .schema import SCHEMAS, TABLES, CONFIG_TABLES, READONLY, LOCKED_FIELDS, DEFAULT_POLICY, validate, timestamp

OPERATIONS = {}
def operation(name, label, roles=("controller","intake","attorney","observer"), mutation=False, control=False):
    def decorate(fn):
        OPERATIONS[name] = {"name":name, "label":label, "roles":list(roles), "mutation":mutation,
                            "control":control, "cli":"firm-lab call " + name, "handler":fn.__name__}
        return fn
    return decorate

BUSINESS = ("controller","intake","attorney")
ADMIN = ("controller",)

class Service:
    def __init__(self, store):
        self.store = store

    def execute(self, name, args, principal, key=None):
        started=now()
        try:
            result=self._execute(name,args,principal,key)
        except LabError as error:
            self.trace(name,args,principal,started,{"error":str(error),"status":error.status})
            raise
        self.trace(name,args,principal,started,{"result":result})
        return result

    def trace(self,name,args,principal,started,response):
        spec=OPERATIONS.get(name)
        world=args.get("world") or principal.get("world")
        if not spec or spec["control"] or not world or (principal.get("world") and principal["world"]!=world): return
        # Do not recursively embed audit-history/state responses or leak controller data.
        if name=="controller.inspect" or principal["role"]=="controller": return
        if name=="events.list" and isinstance(response.get("result"),list):
            response={"result_event_ids":[event["id"] for event in response["result"]]}
        with self.store.world(world) as c:
            if meta(c).get("frozen"): return
            audit(c,principal["actor"],"tool.call","operation",None,None,
                  {"operation":name,"request":args,"started_at":started,"finished_at":now(),**response})

    def _execute(self, name, args, principal, key=None):
        spec = OPERATIONS.get(name)
        if not spec: raise LabError("Unknown operation",404)
        if principal["role"] not in spec["roles"]: raise LabError("Operation not permitted for this role",403)
        if spec["control"]:
            return getattr(self, spec["handler"])(args,principal)
        world = args.get("world") or principal.get("world")
        if not world: raise LabError("world is required")
        if principal.get("world") and principal["world"] != world:
            raise LabError("Token belongs to another world",403)
        args = {**args,"world":world}
        failed_after = False
        with self.store.world(world) as c:
            m = meta(c)
            if m.get("frozen") and spec["mutation"]: raise LabError("Run is frozen; clone it to continue",409)
            cached = get(c,"idempotency",key,False) if key and spec["mutation"] else None
            signature = digest(json.dumps({"op":name,"args":args,"actor":principal["actor"]},sort_keys=True))
            if cached:
                if cached["signature"] != signature: raise LabError("Idempotency key reused with different request",409)
                return cached["response"]
            fault = next((x for x in rows(c,"faults") if not x["used"] and x["operation"]==name),None) if spec["mutation"] else None
            if fault and fault["kind"]=="before":
                fault["used"]=True
                put(c,"faults",fault)
                audit(c,"controller","fault.before","fault",None,None,{"operation":name})
                # A failed attempt must commit fault consumption but not execute business code.
                response = None
                failed_after = "before"
            else:
                response = getattr(self,spec["handler"])(c,args,principal)
                if key and spec["mutation"]:
                    put(c,"idempotency",{"id":key,"signature":signature,"response":response})
                if fault and fault["kind"]=="after_commit":
                    fault["used"]=True
                    put(c,"faults",fault)
                    audit(c,"controller","fault.after_commit","fault",None,None,{"operation":name})
                    failed_after=True
        if failed_after: raise LabError("Simulated upstream timeout; inspect state before retrying",504)
        return response

    def create(self,c,entity,data,p):
        data=validate(c,entity,data)
        self.business_rules(c,entity,data)
        record={**data,"id":uid(),"version":1,"created_at":meta(c)["clock"],"updated_at":meta(c)["clock"]}
        if entity=="messages": record.update(status="received" if data.get("direction")=="inbound" else "drafted",attempts=0)
        if entity=="escalations": record["status"]="open"
        if entity=="documents": record["history"]=[]
        put(c,entity,record)
        audit(c,p["actor"],"create",entity,None,record)
        return record

    def update(self,c,entity,id,data,version,p):
        old=get(c,entity,id)
        if version is None or old["version"]!=version: raise LabError("Record changed; reload and supply its current version",409)
        fields=validate(c,entity,data,old)
        new={**old,**fields,"version":old["version"]+1,"updated_at":meta(c)["clock"]}
        if entity=="documents" and data.get("content") is not None:
            new["history"]=[*old.get("history",[]),{"version":old["version"],"content":old["content"],"at":old["updated_at"]}]
        self.business_rules(c,entity,new)
        put(c,entity,new)
        audit(c,p["actor"],"update",entity,old,new)
        return new

    def business_rules(self,c,entity,data):
        policy=meta(c)["policy"]
        if entity=="matters" and data["stage"] not in policy["stages"]: raise LabError("Unknown pipeline stage")
        if entity=="appointments" and data.get("status")!="cancelled":
            start,end=timestamp(data["start_at"]),timestamp(data["end_at"])
            if start>=end: raise LabError("Appointment must end after it starts")
            if start<timestamp(meta(c)["clock"]): raise LabError("Appointment cannot start in the past")
            staff=get(c,"staff",data["staff_id"])
            if not staff["available"]: raise LabError("Staff member is unavailable",409)
            if staff.get("available_from") and start<timestamp(staff["available_from"]): raise LabError("Outside availability",409)
            if staff.get("available_until") and end>timestamp(staff["available_until"]): raise LabError("Outside availability",409)
            for appt in rows(c,"appointments"):
                if appt["id"]!=data.get("id") and appt["status"]=="booked" and appt["staff_id"]==data["staff_id"]:
                    if start<timestamp(appt["end_at"]) and end>timestamp(appt["start_at"]): raise LabError("Appointment overlaps an existing booking",409)
        if entity=="escalations":
            if get(c,"staff",data["assignee_id"])["role"]!="attorney": raise LabError("Escalation must be assigned to an attorney")
        if entity=="workflows":
            steps=data["steps"]
            if not isinstance(steps,list) or not 1<=len(steps)<=20: raise LabError("Workflow requires 1–20 steps")
            for step in steps:
                if not isinstance(step,dict) or step.get("type") not in ("email","task","status","form"):
                    raise LabError("Workflow step type must be email, task, status or form")
                if step["type"]=="status" and step.get("stage") not in policy["stages"]: raise LabError("Workflow stage not in pipeline")
                if step["type"]=="task":
                    try: hours=float(step.get("hours",1))
                    except (TypeError,ValueError): raise LabError("Task hours must be numeric")
                    if not 0<hours<=8760: raise LabError("Task hours must be positive and at most one year")
                    if step.get("kind","review") not in ("callback","review","followup","conflict_check"): raise LabError("Invalid task kind")
                if step["type"]=="form" and step.get("form_id"): get(c,"forms",step["form_id"])
        if entity=="forms":
            if not isinstance(data["fields"],list): raise LabError("Form fields must be an array")
            for field in data["fields"]:
                if not isinstance(field,dict) or field.get("key") not in ("summary","injury","incident_date","location"):
                    raise LabError("Form fields support summary, injury, incident_date, location")
                if not isinstance(field.get("label"),str) or not field["label"].strip(): raise LabError("Form field labels are required")
                if not isinstance(field.get("required",False),bool): raise LabError("Form required flag must be boolean")
            keys=[x["key"] for x in data["fields"]]
            if len(set(keys))!=len(keys) or "summary" not in keys: raise LabError("Form requires a summary field and unique keys")

    @operation("world.list","List worlds",ADMIN,control=True)
    def world_list(self,a,p):
        with self.store.control() as c: return rows(c,"worlds")

    @operation("world.create","Create world",ADMIN,True,True)
    def world_create(self,a,p):
        if a.get("seed","realistic") not in ("realistic","empty"): raise LabError("seed must be realistic or empty")
        world=uid()
        self.store.initialize_world(world,TABLES)
        self.seed(world,a.get("seed","realistic"),a.get("name","Harbor & Stone"))
        record={"id":world,"name":a.get("name","Harbor & Stone"),"created_at":now(),"seed":a.get("seed","realistic")}
        with self.store.control() as c: put(c,"worlds",record)
        return record

    def seed(self,world,seed,name):
        if seed not in ("realistic","empty"): raise LabError("seed must be realistic or empty")
        with self.store.world(world) as c:
            for table in (*TABLES,"meta","events","idempotency","scheduled","faults"): c.execute(f"DELETE FROM {table}")
            put(c,"meta",{"id":"world","clock":"2026-11-07T04:30:00+00:00","policy":copy.deepcopy(DEFAULT_POLICY),"name":name,"frozen":False})
            p={"actor":"fixture"}
            attorney=self.create(c,"staff",{"name":"Avery Chen","role":"attorney","available":True},p)
            self.create(c,"staff",{"name":"Jordan Taylor","role":"intake","available":True},p)
            self.create(c,"forms",{"name":"Case review","fields":[{"key":"summary","label":"What happened?","required":True},{"key":"injury","label":"Injuries or treatment","required":False},{"key":"incident_date","label":"Incident date","required":False},{"key":"location","label":"Where did it happen?","required":False}]},p)
            self.create(c,"workflows",{"name":"Review and acknowledgment","steps":[{"type":"task","title":"Review new inquiry","kind":"review","hours":1},{"type":"email"},{"type":"status","stage":"Screening"}]},p)
            if seed=="realistic":
                contact=self.create(c,"contacts",{"name":"Alex Morgan","email":"alex.old@example.test","phone":"+14155550122","source":"Website"},p)
                matter=self.create(c,"matters",{"title":"Alex Morgan — rear-end collision","contact_id":contact["id"],"summary":"Rear-ended near Market Street. Caller reported neck soreness.","injury":"Neck soreness","location":"San Francisco","consent":True,"owner_id":attorney["id"]},p)
                other=self.create(c,"contacts",{"name":"Alex Morgan","email":"other.alex@example.test","phone":"+14155550123"},p)
                unrelated=self.create(c,"matters",{"title":"Alex Morgan — unrelated slip and fall","contact_id":other["id"],"summary":"Separate incident at a grocery store.","matter_type":"Premises liability"},p)
                self.create(c,"notes",{"matter_id":matter["id"],"body":"Caller asked for a follow-up. Do not assume new inquiries concern this accident."},p)
                self.create(c,"documents",{"matter_id":matter["id"],"name":"Initial inquiry notes","content":"Caller reported being rear-ended. Medical treatment not yet confirmed.","kind":"intake"},p)
                self.create(c,"appointments",{"matter_id":unrelated["id"],"staff_id":attorney["id"],"title":"Existing consultation","start_at":"2026-11-07T17:00:00+00:00","end_at":"2026-11-07T17:30:00+00:00"},p)

    @operation("world.reset","Reset world",ADMIN,True,True)
    def world_reset(self,a,p):
        with self.store.control() as c:
            world=get(c,"worlds",a["world"])
            if any(r["world"]==world["id"] for r in rows(c,"runs")): raise LabError("Run worlds cannot be reset; create a new run",409)
        self.seed(world["id"],a.get("seed",world["seed"]),world["name"])
        return {"reset":True,"world":world["id"]}

    @operation("world.clone","Clone world",ADMIN,True,True)
    def world_clone(self,a,p):
        with self.store.world(a["world"]) as c: snapshot={t:rows(c,t) for t in (*TABLES,"meta","events","scheduled")}
        w=self.world_create({"name":a.get("name","Cloned firm"),"seed":"empty"},p)
        with self.store.world(w["id"]) as c:
            for table, records in snapshot.items():
                c.execute(f"DELETE FROM {table}")
                for r in records: put(c,table,r)
            m=meta(c); m["frozen"]=False; put(c,"meta",m)
        return w

    @operation("grant.create","Issue scoped access",ADMIN,True,True)
    def grant_create(self,a,p):
        with self.store.world(a["world"]) as c: meta(c)
        if a.get("role") not in ("intake","attorney","observer"): raise LabError("Invalid role")
        token=secrets.token_urlsafe(32)
        grant={"id":uid(),"hash":digest(token),"world":a["world"],"role":a["role"],"actor":a.get("actor",a["role"]),"revoked":False}
        with self.store.control() as c: put(c,"grants",grant)
        return {**{k:v for k,v in grant.items() if k!="hash"},"token":token}

    @operation("grant.list","List access grants",ADMIN,control=True)
    def grant_list(self,a,p):
        with self.store.control() as c: return [{k:v for k,v in r.items() if k!="hash"} for r in rows(c,"grants")]

    @operation("grant.revoke","Revoke access",ADMIN,True,True)
    def grant_revoke(self,a,p):
        with self.store.control() as c:
            g=get(c,"grants",a["id"]); g["revoked"]=True; return put(c,"grants",g)

    @operation("world.state","Read firm workspace")
    def state(self,c,a,p):
        m=meta(c)
        return {"world":a["world"],"name":m["name"],"clock":m["clock"],"frozen":m["frozen"],"policy":m["policy"],"data":{t:rows(c,t) for t in TABLES}}

    @operation("schema.get","Read entity field schemas and operation guide")
    def field_schema(self,c,a,p):
        return {"entities":SCHEMAS,"stages":meta(c)["policy"]["stages"],
                "usage":"records.create takes entity and data. records.update additionally requires id and the current version. Consult each field's required, type, options and ref. Record IDs are opaque. Use lead.convert, message.send, escalation.accept and workflow.start for transitions; never assume a failed request did not commit."}

    @operation("records.list","Search records")
    def record_list(self,c,a,p):
        entity=a.get("entity")
        if entity not in SCHEMAS: raise LabError("Unknown entity",404)
        result=rows(c,entity)
        query=str(a.get("query","")).lower()
        if query: result=[r for r in result if query in json.dumps(r).lower()]
        if a.get("matter_id"): result=[r for r in result if r.get("matter_id")==a["matter_id"]]
        offset=max(0,int(a.get("offset",0))); limit=min(200,max(1,int(a.get("limit",50))))
        return {"items":result[offset:offset+limit],"total":len(result),"next_offset":offset+limit if offset+limit<len(result) else None}

    @operation("records.get","Get record")
    def record_get(self,c,a,p):
        if a.get("entity") not in SCHEMAS: raise LabError("Unknown entity",404)
        return get(c,a["entity"],a["id"])

    @operation("records.create","Create record",BUSINESS,True)
    def record_create(self,c,a,p):
        entity=a.get("entity")
        if entity in CONFIG_TABLES and p["role"]!="controller": raise LabError("Configuration requires controller",403)
        if entity=="turns" and a.get("data",{}).get("speaker")!="agent" and p["role"]!="controller":
            raise LabError("Agents cannot write other participants' speech",403)
        if entity=="messages" and a.get("data",{}).get("direction")=="inbound" and p["role"]!="controller":
            raise LabError("Only the controller can inject incoming messages",403)
        if entity=="leads" and any(k in a.get("data",{}) for k in ("status","matter_id")):
            raise LabError("Lead conversion uses lead.convert")
        return self.create(c,entity,a.get("data",{}),p)

    @operation("records.update","Update record",BUSINESS,True)
    def record_update(self,c,a,p):
        entity=a.get("entity")
        if entity not in SCHEMAS or entity in READONLY: raise LabError("Unsupported entity",404)
        if entity in CONFIG_TABLES and p["role"]!="controller": raise LabError("Configuration requires controller",403)
        if entity in ("turns","escalations"): raise LabError("Use the dedicated operation; conversation turns are immutable")
        data=a.get("data",{})
        if entity=="tasks" and data.get("status")=="completed":
            if any(i.get("form_id") and i.get("waiting",{}).get("id")==a["id"] for i in rows(c,"workflow_instances") if i.get("waiting")):
                raise LabError("Submit the requested form before completing this task",409)
        if any(k in LOCKED_FIELDS.get(entity,set()) for k in data): raise LabError("Field is controlled by a dedicated operation")
        if entity=="messages" and get(c,entity,a["id"])["status"]!="drafted": raise LabError("Only drafts can be edited",409)
        result=self.update(c,entity,a["id"],data,a.get("version"),p)
        self.advance_workflows(c,p)
        return result

    @operation("lead.convert","Convert lead",BUSINESS,True)
    def convert(self,c,a,p):
        lead=get(c,"leads",a["id"])
        if lead["status"]=="converted": return get(c,"matters",lead["matter_id"])
        if lead["status"]=="ignored": raise LabError("Ignored lead cannot be converted",409)
        contact=get(c,"contacts",a["contact_id"]) if a.get("contact_id") else self.create(c,"contacts",{k:lead[k] for k in ("name","email","phone","source") if k in lead},p)
        if a.get("matter_id"):
            matter=get(c,"matters",a["matter_id"])
            if matter["contact_id"]!=contact["id"]: raise LabError("Matter belongs to a different contact")
            self.create(c,"notes",{"matter_id":matter["id"],"body":lead["summary"]},p)
        else:
            matter=self.create(c,"matters",{"title":lead["name"]+" — inquiry","contact_id":contact["id"],**{k:lead[k] for k in ("summary","injury","incident_date","location","consent") if k in lead}},p)
        self.update(c,"leads",lead["id"],{"status":"converted","matter_id":matter["id"]},lead["version"],p)
        return matter

    @operation("lead.ignore","Ignore lead",BUSINESS,True)
    def ignore(self,c,a,p):
        lead=get(c,"leads",a["id"])
        if lead["status"]!="new": raise LabError("Only new leads can be ignored",409)
        return self.update(c,"leads",lead["id"],{"status":"ignored"},lead["version"],p)

    @operation("message.send","Deliver simulated message",BUSINESS,True)
    def send(self,c,a,p):
        return self.deliver(c,a["id"],p)

    def deliver(self,c,id,p,advance=True):
        old=get(c,"messages",id)
        if old["status"]=="delivered": return old
        if old["direction"]!="outbound": raise LabError("Cannot send an incoming message")
        matter=get(c,"matters",old["matter_id"])
        if old["channel"]!="internal" and not matter.get("consent"): raise LabError("Contact permission is required",409)
        if old["status"] not in ("drafted","failed"): raise LabError("Message is not sendable",409)
        fault=next((x for x in rows(c,"faults") if not x["used"] and x["kind"]=="delivery"),None)
        new={**old,"status":"failed" if fault else "delivered","attempts":old["attempts"]+1,"version":old["version"]+1,
             "updated_at":meta(c)["clock"],"delivery_issue":"Simulated delivery failure" if fault else None}
        if fault: fault["used"]=True; put(c,"faults",fault)
        put(c,"messages",new); audit(c,p["actor"],"message.delivery","messages",old,new)
        if advance: self.advance_workflows(c,p)
        return new

    @operation("escalation.accept","Accept attorney handoff",("controller","attorney"),True)
    def accept(self,c,a,p):
        old=get(c,"escalations",a["id"])
        new={**old,"status":"accepted","accepted_by":p["actor"],"version":old["version"]+1,"updated_at":meta(c)["clock"]}
        put(c,"escalations",new); audit(c,p["actor"],"escalation.accept","escalations",old,new)
        return new

    @operation("staff.respond","Simulate attorney response",ADMIN,True)
    def staff_respond(self,c,a,p):
        escalation=get(c,"escalations",a["id"])
        staff=get(c,"staff",escalation["assignee_id"])
        decision=a.get("decision","accept" if staff["available"] else "defer")
        if decision not in ("accept","defer"): raise LabError("decision must be accept or defer")
        if decision=="accept" and not staff["available"]: raise LabError("Simulated attorney is unavailable",409)
        actor={"role":"attorney","actor":"simulated staff: "+staff["name"]}
        text="I have accepted the handoff and will review the inquiry." if decision=="accept" else "I am not able to review this immediately. Please keep the handoff open for follow-up."
        result=self.accept(c,{"id":escalation["id"]},actor) if decision=="accept" else escalation
        self.create(c,"notes",{"matter_id":escalation["matter_id"],"body":staff["name"]+": "+text},actor)
        if a.get("conversation_id"):
            self.create(c,"turns",{"conversation_id":a["conversation_id"],"speaker":"staff","text":text},actor)
        return {"escalation":result,"text":text,"mode":"scripted staff fixture"}

    @operation("policy.update","Configure firm policy",ADMIN,True)
    def policy_update(self,c,a,p):
        m=meta(c); old=copy.deepcopy(m["policy"]); data=a.get("data",{})
        if set(data)-set(DEFAULT_POLICY): raise LabError("Unknown policy field")
        new={**old,**data}
        if not isinstance(new["stages"],list) or not new["stages"] or any(not isinstance(s,str) or not s.strip() for s in new["stages"]) or len(set(new["stages"]))!=len(new["stages"]):
            raise LabError("stages must be distinct nonempty strings")
        if any(r["stage"] not in new["stages"] for r in rows(c,"matters")): raise LabError("Cannot remove an occupied stage",409)
        if new["email_mode"] not in ("draft","automatic"): raise LabError("email_mode must be draft or automatic")
        for k,v in new.items():
            if k!="stages" and not isinstance(v,str): raise LabError("Policy values must be text")
        try: ZoneInfo(new["timezone"])
        except (ZoneInfoNotFoundError,ValueError): raise LabError("timezone must be a valid IANA timezone")
        m["policy"]=new; put(c,"meta",m); audit(c,p["actor"],"policy.update","policy",old,new)
        return new

    @operation("events.list","Inspect audit history")
    def events(self,c,a,p):
        result=rows(c,"events")
        if p["role"]!="controller": result=[r for r in result if not r["action"].startswith(("fault.","scenario."))]
        if a.get("record_id"): result=[r for r in result if r["record_id"]==a["record_id"]]
        return result

    @operation("clock.advance","Advance business clock",ADMIN,True)
    def clock(self,c,a,p):
        minutes=float(a.get("minutes",0))
        if minutes<=0 or minutes>525600: raise LabError("minutes must be positive and at most one year")
        m=meta(c); before=m["clock"]; m["clock"]=(timestamp(before)+timedelta(minutes=minutes)).isoformat(); put(c,"meta",m)
        audit(c,p["actor"],"clock.advance","clock",None,None,{"from":before,"to":m["clock"]})
        executed=[]
        for event in rows(c,"scheduled"):
            if not event["done"] and timestamp(event["due_at"])<=timestamp(m["clock"]):
                if event["kind"]=="incoming_message": result=self.create(c,"messages",{**event["data"],"direction":"inbound"},{"actor":"simulated caller"})
                else:
                    staff=get(c,"staff",event["data"]["id"])
                    result=self.update(c,"staff",staff["id"],{"available":event["data"]["available"]},staff["version"],{"actor":"schedule"})
                event["done"]=True; put(c,"scheduled",event); executed.append(result)
        self.advance_workflows(c,p)
        return {"clock":m["clock"],"executed":executed}

    @operation("event.schedule","Schedule external event",ADMIN,True)
    def schedule(self,c,a,p):
        if a.get("kind") not in ("incoming_message","staff_availability"): raise LabError("Unsupported event kind")
        if timestamp(a["due_at"])<=timestamp(meta(c)["clock"]): raise LabError("Event must be in the future")
        data=a.get("data",{})
        if a["kind"]=="incoming_message": validate(c,"messages",{**data,"direction":"inbound"})
        else:
            get(c,"staff",data.get("id"))
            if not isinstance(data.get("available"),bool): raise LabError("available must be boolean")
        event={"id":uid(),"kind":a["kind"],"data":data,"due_at":a["due_at"],"done":False}
        put(c,"scheduled",event)
        return event

    @operation("controller.inspect","Inspect scheduled events and faults",ADMIN)
    def inspect(self,c,a,p):
        return {"scheduled":rows(c,"scheduled"),"faults":rows(c,"faults")}

    @operation("fault.add","Inject one-shot fault",ADMIN,True)
    def fault(self,c,a,p):
        if a.get("kind") not in ("before","after_commit","delivery"): raise LabError("Unknown fault kind")
        op=a.get("operation","message.send")
        if op not in OPERATIONS or not OPERATIONS[op]["mutation"] or OPERATIONS[op]["control"]: raise LabError("Fault requires business mutation operation")
        fault={"id":uid(),"kind":a["kind"],"operation":op,"used":False}
        put(c,"faults",fault); return fault

    @operation("workflow.start","Start intake workflow",BUSINESS,True)
    def workflow(self,c,a,p):
        template=get(c,"workflows",a["template_id"]); get(c,"matters",a["matter_id"])
        instance={"id":uid(),"template_id":template["id"],"matter_id":a["matter_id"],"steps":copy.deepcopy(template["steps"]),"index":0,"waiting":None,"status":"running"}
        put(c,"workflow_instances",instance); audit(c,p["actor"],"workflow.start","workflow_instances",None,instance)
        self.advance_workflows(c,p)
        return get(c,"workflow_instances",instance["id"])

    def advance_workflows(self,c,p):
        for instance in rows(c,"workflow_instances"):
            if instance["status"]=="completed": continue
            old=copy.deepcopy(instance)
            if instance["waiting"]:
                wait=instance["waiting"]
                obj=get(c,wait["table"],wait["id"])
                if obj.get("status")!=wait["status"]: continue
                instance["waiting"]=None; instance["index"]+=1
            while instance["index"]<len(instance["steps"]):
                step=instance["steps"][instance["index"]]; matter=get(c,"matters",instance["matter_id"])
                if step["type"]=="status":
                    self.update(c,"matters",matter["id"],{"stage":step["stage"]},matter["version"],{"actor":"firm workflow"})
                    instance["index"]+=1
                elif step["type"]=="task":
                    due=(timestamp(meta(c)["clock"])+timedelta(hours=float(step.get("hours",1)))).isoformat()
                    task=self.create(c,"tasks",{"matter_id":matter["id"],"title":step.get("title","Review inquiry"),"kind":step.get("kind","review"),"due_at":due},{"actor":"firm workflow"})
                    instance["waiting"]={"table":"tasks","id":task["id"],"status":"completed"}; break
                elif step["type"]=="form":
                    form=get(c,"forms",step.get("form_id") or rows(c,"forms")[0]["id"])
                    task=self.create(c,"tasks",{"matter_id":matter["id"],"title":"Collect form: "+form["name"],"kind":"review","due_at":(timestamp(meta(c)["clock"])+timedelta(hours=24)).isoformat()},{"actor":"firm workflow"})
                    instance["waiting"]={"table":"tasks","id":task["id"],"status":"completed"}
                    instance["form_id"]=form["id"]
                    break
                else:
                    contact=get(c,"contacts",matter["contact_id"]); policy=meta(c)["policy"]
                    if not contact.get("email"):
                        instance["status"]="blocked"; instance["issue"]="Contact has no email"; break
                    msg=self.create(c,"messages",{"matter_id":matter["id"],"to":contact["email"],"subject":step.get("subject",policy["ack_subject"]),"body":step.get("body",policy["ack_body"])},{"actor":"firm workflow"})
                    if policy["email_mode"]=="automatic" and matter.get("consent"):
                        msg=self.deliver(c,msg["id"],{"actor":"firm workflow"},advance=False)
                        if msg["status"]=="delivered":
                            instance["index"]+=1
                            instance["status"]="running"
                            instance.pop("issue",None)
                            continue
                    instance["waiting"]={"table":"messages","id":msg["id"],"status":"delivered"}; break
            if instance["index"]==len(instance["steps"]): instance["status"]="completed"
            elif instance["status"]!="blocked": instance["status"]="waiting" if instance["waiting"] else "running"
            put(c,"workflow_instances",instance)
            if old!=instance: audit(c,"firm workflow","workflow.advance","workflow_instances",old,instance)

    @operation("workflow.form.submit","Record requested form response",BUSINESS,True)
    def form_response(self,c,a,p):
        ins=get(c,"workflow_instances",a["id"])
        if not ins.get("form_id") or not ins.get("waiting"): raise LabError("Workflow is not waiting for a form")
        form=get(c,"forms",ins["form_id"]); data=a.get("data",{})
        for field in form["fields"]:
            if field.get("required") and not data.get(field["key"]): raise LabError(field["key"]+" is required")
        matter=get(c,"matters",ins["matter_id"])
        self.update(c,"matters",matter["id"],data,matter["version"],p)
        task=get(c,"tasks",ins["waiting"]["id"])
        self.update(c,"tasks",task["id"],{"status":"completed"},task["version"],p)
        self.advance_workflows(c,p)
        return get(c,"workflow_instances",ins["id"])

    @operation("recording.attach","Attach test recording",ADMIN,True)
    def recording(self,c,a,p):
        conv=get(c,"conversations",a["id"])
        try: data=base64.b64decode(a["base64"],validate=True)
        except Exception: raise LabError("Invalid base64")
        if len(data)>5*1024*1024: raise LabError("Recording exceeds 5 MB")
        if a.get("mime") not in ("audio/wav","audio/mpeg","audio/webm","audio/ogg"): raise LabError("Unsupported recording type")
        old=copy.deepcopy(conv); conv.update(recording=a["base64"],recording_mime=a["mime"],recording_label="Uploaded test recording",version=conv["version"]+1)
        put(c,"conversations",conv); audit(c,p["actor"],"recording.attach","conversations",{"id":old["id"]},{"id":conv["id"]}, {"bytes":len(data)})
        return {"id":conv["id"],"bytes":len(data),"label":"Uploaded test recording"}
