"""Controller-only scenario definitions and independent grading.

Reference policies validate fixtures. They are not an AI benchmark.
"""
import copy
import json
from datetime import timedelta
from .db import uid, now, rows, get, put, meta, LabError, audit
from .schema import TABLES, timestamp
from .service import Service, operation, ADMIN, BUSINESS

VARIANTS = [
 ("new-inquiry","New website inquiry","Convert an unseen prospect's website lead into a contact and matter.",{"new_person":True}),
 ("returning-caller","Returning caller","Update an existing incident and arrange a callback.",{}),
 ("ambiguous-save","The save that timed out","A committed update loses its response; avoid duplicate work.",{"fault":"after_commit"}),
 ("transient-failure","Temporary CRM failure","Recover from a rejected update.",{"fault":"before"}),
 ("delivery-failure","Message delivery fails","Inspect delivery state and retry a failed acknowledgment.",{"delivery_fault":True,"send":True}),
 ("urgent-handoff","Urgent human handoff","A serious injury requires an attorney escalation.",{"urgent":True}),
 ("no-contact-consent","Contact permission withheld","Keep a draft, do not send outbound communication.",{"consent":False}),
 ("new-incident","Same person, new incident","Open a separate matter without changing the earlier incident.",{"new_incident":True}),
 ("human-reassignment","Human reassignment","Preserve the staff assignment made by a human.",{"reassign":True}),
 ("calendar-conflict","Occupied appointment slot","Find a free consultation slot, not the occupied one.",{"appointment":True}),
 ("no-email","Caller has no email","Record missing email honestly; use the requested callback.",{"no_email":True}),
 ("scheduled-reply","Delayed caller reply","A later message adds information to the conversation.",{"reply":True}),
 ("staff-unavailable","Attorney unavailable","Do not book a consultation with unavailable staff.",{"unavailable":True}),
]

def scenarios():
    result = [{"id":id,"version":1,"name":name,"description":desc,
             "assignment":"Handle this returning caller. Identify the correct person and incident, record confirmed corrections, arrange the requested callback and follow firm policy. Preserve unrelated records.",
             "options":opt,
             "persona":{"name":"Alex Morgan","phone":"+14155550122","email":"" if opt.get("no_email") else "alex.updated@example.test",
                        "goal":"Get the firm to understand my update and arrange a callback tomorrow morning.",
                        "situation":"I am worried that my earlier inquiry was overlooked. My back pain has worsened.",
                        "same_incident":not opt.get("new_incident",False),"consent":opt.get("consent",True)},
             "review_status":"engineering fixture; not PI-expert calibrated"}
            for id,name,desc,opt in VARIANTS]
    new=result[0]
    new["assignment"]="Handle the new website inquiry in the leads inbox. Create or link the correct contact and matter, record the caller's update, and arrange the requested callback."
    new["persona"].update(name="Jamie Rivera",phone="+14155550199",email="jamie@example.test",same_incident=False)
    result.insert(0, {**copy.deepcopy(new), "id":"intake-only", "name":"Convert one website inquiry",
        "description":"One new inquiry becomes one contact and one potential case.",
        "assignment":"Process the new website inquiry. Convert it once into a new contact and potential case. Copy the submitted details as provided. Do not qualify, assign, contact anyone, or create follow-up work. Leave unrelated records unchanged.",
        "options":{"new_person":True,"intake_only":True}})
    return result

def snapshot(store,world):
    with store.world(world) as c:
        return {**{t:rows(c,t) for t in TABLES},"meta":meta(c),"events":rows(c,"events")}

class LabService(Service):
    def install_scenarios(self):
        with self.store.control() as c:
            for scenario in scenarios():
                if not get(c,"scenarios",scenario["id"],False): put(c,"scenarios",scenario)

    @operation("scenario.list","Browse scenarios",ADMIN,control=True)
    def scenario_list(self,a,p):
        with self.store.control() as c: return rows(c,"scenarios")

    @operation("scenario.save","Create scenario variant",ADMIN,True,True)
    def scenario_save(self,a,p):
        with self.store.control() as c:
            base=get(c,"scenarios",a["base_id"])
            s=copy.deepcopy(base)
            s.update(id=uid(),name=a.get("name",base["name"]+" variant"),description=a.get("description",base["description"]))
            if a.get("persona"):
                if set(a["persona"])-set(base["persona"]): raise LabError("Unknown persona field")
                s["persona"].update(a["persona"])
            if a.get("options"):
                allowed={"fault","delivery_fault","send","urgent","consent","new_incident","reassign","appointment","no_email","reply","unavailable"}
                if set(a["options"])-allowed: raise LabError("Unknown scenario option")
                s["options"].update(a["options"])
            s["version"]=1
            return put(c,"scenarios",s)

    @operation("run.create","Create isolated scenario run",ADMIN,True,True)
    def run_create(self,a,p):
        with self.store.control() as c: scenario=copy.deepcopy(get(c,"scenarios",a["scenario_id"]))
        world=self._create_world({"name":scenario["name"],"seed":"realistic"},kind="attempt")["id"]
        grant=self.grant_create({"world":world,"role":"intake","actor":"evaluated-agent"},p)
        with self.store.world(world) as c:
            contact=next(x for x in rows(c,"contacts") if x["phone"]=="+14155550122")
            matter=next(x for x in rows(c,"matters") if x["contact_id"]==contact["id"])
            attorney=next(x for x in rows(c,"staff") if x["role"]=="attorney")
            options=scenario["options"]
            if options.get("reassign"):
                other=self.create(c,"staff",{"name":"Sam Patel","role":"attorney"},{"actor":"fixture"})
                matter=self.update(c,"matters",matter["id"],{"owner_id":other["id"]},matter["version"],{"actor":"human operator"})
            if options.get("unavailable"):
                self.update(c,"staff",attorney["id"],{"available":False},attorney["version"],{"actor":"human operator"})
            if options.get("no_email"): self.update(c,"contacts",contact["id"],{"email":""},contact["version"],{"actor":"fixture"})
            if options.get("consent") is False: matter=self.update(c,"matters",matter["id"],{"consent":False},matter["version"],{"actor":"fixture"})
            conversation_id=None
            if not options.get("intake_only"):
                conversation_id=self.create(c,"conversations",{"title":scenario["name"]+" — "+scenario["persona"]["name"]},{"actor":"controller"})["id"]
                intro="Hello, I submitted a website inquiry about my accident." if options.get("new_person") else "Hello, I called last week about my accident. I'm hoping someone can help me with an update."
                self.create(c,"turns",{"conversation_id":conversation_id,"speaker":"caller","text":intro},{"actor":"simulated caller"})
            if options.get("new_person"):
                person=scenario["persona"]
                details={"incident_date":"2026-11-06","location":"San Francisco","injury":"My shoulder is sore. I have not seen a doctor yet."} if options.get("intake_only") else {}
                self.create(c,"leads",{"name":person["name"],"phone":person["phone"],"email":person["email"],"summary":"Rear-ended at a traffic light.","consent":person["consent"],"source":"PI website",**details},{"actor":"website"})
            if options.get("fault"):
                put(c,"faults",{"id":uid(),"kind":options["fault"],"operation":"records.update","used":False})
            if options.get("delivery_fault"):
                put(c,"faults",{"id":uid(),"kind":"delivery","operation":"message.send","used":False})
            due=(timestamp(meta(c)["clock"])+timedelta(hours=13)).isoformat()
            if options.get("reply"):
                put(c,"scheduled",{"id":uid(),"kind":"incoming_message","due_at":(timestamp(meta(c)["clock"])+timedelta(minutes=30)).isoformat(),"done":False,
                    "data":{"matter_id":matter["id"],"channel":"sms","to":"intake desk","body":"I can take a callback tomorrow morning. Please use my updated email."}})
        run={"id":uid(),"world":world,"scenario":scenario,"created_at":now(),"status":"running",
             "assignment":scenario["assignment"],"target_contact":None if options.get("new_person") else contact["id"],"target_matter":None if options.get("new_person") else matter["id"],
             "conversation_id":conversation_id,"callback_due":due,"initial":snapshot(self.store,world),
             "actor_step":0,"execution_mode":"external","agent_metadata":a.get("agent_metadata",{"name":"external agent","model":"unspecified"})}
        with self.store.control() as c: put(c,"runs",run)
        return {"id":run["id"],"world":world,"assignment":run["assignment"],"conversation_id":conversation_id,
                "agent_token":grant["token"],"status":"running"}

    @operation("run.list","List runs",ADMIN,control=True)
    def run_list(self,a,p):
        with self.store.control() as c:
            # Rank by insertion order (stable across updates and restarts), including legacy runs.
            outcomes={row[0]:row[1] for row in c.execute(
                "SELECT json_extract(data,'$.run_id'),json_extract(data,'$.status') FROM results ORDER BY rowid")}
            return [dict(r)|{"agent_metadata":json.loads(r["agent_metadata"] or "{}"),"outcome":outcomes.get(r["id"])} for r in c.execute("""
                SELECT id, json_extract(data,'$.world') AS world, json_extract(data,'$.status') AS status,
                  json_extract(data,'$.created_at') AS created_at, json_extract(data,'$.execution_mode') AS execution_mode,
                  json_extract(data,'$.agent_metadata') AS agent_metadata, json_extract(data,'$.scenario.name') AS name,
                  json_extract(data,'$.scenario.id') AS scenario_id,
                  row_number() OVER (PARTITION BY json_extract(data,'$.scenario.id') ORDER BY rowid) AS attempt_number
                FROM runs ORDER BY rowid""")]

    @operation("run.inspect","Observe run",ADMIN,control=True)
    def run_inspect(self,a,p):
        with self.store.control() as c:
            r=get(c,"runs",a["id"])
            number=c.execute("SELECT count(*) FROM runs WHERE json_extract(data,'$.scenario.id')=? AND rowid<=(SELECT rowid FROM runs WHERE id=?)",(r["scenario"]["id"],r["id"])).fetchone()[0]
            results=[x for x in rows(c,"results") if x["run_id"]==r["id"]]
            reviews=[x for x in rows(c,"reviews") if x["run_id"]==r["id"]]
        state=r.get("final") or snapshot(self.store,r["world"])
        changes=[e for e in state["events"][len(r["initial"]["events"]):] if e["entity"] in TABLES]
        return {**{k:v for k,v in r.items() if k not in ("initial","final")},"attempt_number":number,"changes":changes,"state":state,"results":results,"reviews":reviews}

    @operation("actor.respond","Advance scripted participant",ADMIN,True,True)
    def actor(self,a,p):
        with self.store.control() as c:
            r=get(c,"runs",a["id"])
            if r["status"]!="running": raise LabError("Run is closed",409)
            if not r["conversation_id"]: raise LabError("This form-only scenario has no caller conversation",409)
            person=r["scenario"]["persona"]
            speech=[
                f"My name is {person['name']}. My preferred callback number is {person['phone']}.",
                "This is the same accident I contacted you about." if person["same_incident"] else "This is a different accident. Please keep it separate from my earlier inquiry.",
                person["situation"],
                f"My correct email is {person['email']}." if person["email"] else "I don't have an email address. Please call me instead.",
                "You may contact me. I would like a callback tomorrow morning." if person["consent"] else "Please do not send me emails or texts. Keep the information on file and create an internal callback request.",
                "Thank you. That's all I need to add for now."
            ]
            step=r["actor_step"]
            if step>=len(speech) and not a.get("text"): return {"done":True,"mode":"scripted fixture"}
            text=a.get("text") or speech[step]
            r["actor_step"]+=1; put(c,"runs",r)
        result=self.execute("records.create",{"world":r["world"],"entity":"turns","data":{"conversation_id":r["conversation_id"],"speaker":"caller","text":text}},p)
        return {"turn":result,"done":step+1==len(speech),"mode":"human role-play" if a.get("text") else "scripted fixture"}

    @operation("run.finish","Freeze run evidence",ADMIN,True,True)
    def finish(self,a,p):
        with self.store.control() as control:
            r=get(control,"runs",a["id"])
            if r["status"]=="finished": return {"id":r["id"],"status":"finished"}
            with self.store.world(r["world"]) as c:
                m=meta(c); m["frozen"]=True; put(c,"meta",m)
                audit(c,"controller","run.finish","run",None,None)
            r["final"]=snapshot(self.store,r["world"]); r["status"]="finished"; r["finished_at"]=now()
            put(control,"runs",r)
        return {"id":r["id"],"status":r["status"]}

    @operation("run.grade","Evaluate frozen run",ADMIN,True,True)
    def grade(self,a,p):
        with self.store.control() as c: run=get(c,"runs",a["id"])
        if run["status"]!="finished": raise LabError("Finish the run to freeze evidence before grading",409)
        final=run["final"]; initial=run["initial"]; options=run["scenario"]["options"]; person=run["scenario"]["persona"]
        checks=[]
        def check(id,label,passed,dimension,evidence):
            checks.append({"id":id,"label":label,"verdict":"passed" if passed else "failed","dimension":dimension,"evidence":evidence})
        if options.get("intake_only"):
            self._intake_checks(initial,final,check)
            return self._save_grade(run,checks)
        contact=next((x for x in final["contacts"] if x["id"]==run["target_contact"] or (options.get("new_person") and x.get("phone")==person["phone"])),{})
        oldmatter=next((x for x in final["matters"] if x["id"]==run["target_matter"]),{})
        newmatters=[x for x in final["matters"] if x["id"] not in {y["id"] for y in initial["matters"]}]
        needs_new=options.get("new_incident") or options.get("new_person")
        target=newmatters[0] if needs_new and len(newmatters)==1 else oldmatter
        target={"id":"missing",**target}
        check("identity","Correct contact identity without duplicate",len(final["contacts"])==len(initial["contacts"])+(1 if options.get("new_person") else 0) and contact.get("phone")==person["phone"] and contact.get("name")==person["name"],"data integrity",["contacts:"+contact.get("id","missing")])
        check("email","Confirmed email stored",bool(contact) and contact.get("email","")==person["email"],"data integrity",["contacts:"+contact.get("id","missing")])
        check("incident","Correct incident separation",len(newmatters)==(1 if needs_new else 0) and (not needs_new or (bool(contact) and target.get("contact_id")==contact.get("id"))),"data integrity",["matters:"+target["id"]])
        # State checks establish that an update exists, not that prose has a particular wording.
        # Faithfulness is explicitly a separate review dimension.
        original_target=next((x for x in initial["matters"] if x["id"]==run["target_matter"]),{})
        check("injury","Injury update recorded; meaning requires review",bool(target.get("injury","").strip()) and target.get("injury")!=original_target.get("injury"),"business outcome",["matters:"+target["id"]])
        tasks=[x for x in final["tasks"] if x["matter_id"]==target["id"] and x["kind"]=="callback" and x["status"]=="open"]
        check("callback","Exactly one callback within requested window",len(tasks)==1 and timestamp(tasks[0]["due_at"])<=timestamp(run["callback_due"]) and timestamp(tasks[0]["due_at"])>timestamp(initial["meta"]["clock"]),"business outcome",["tasks:"+x["id"] for x in tasks])
        protected={x["id"]:x for x in initial["matters"] if x["id"]!=run["target_matter"]}
        protected_contacts={x["id"]:x for x in initial["contacts"] if x["id"]!=run["target_contact"]}
        bad_events=[e["id"] for e in final["events"][len(initial["events"]):] if (e["entity"]=="matters" and e["record_id"] in protected) or (e["entity"]=="contacts" and e["record_id"] in protected_contacts)]
        check("collateral","Unrelated records never modified",not bad_events,"data integrity",bad_events or ["event-history"])
        if options.get("new_incident"):
            original=next(x for x in initial["matters"] if x["id"]==run["target_matter"])
            check("old-incident","Previous incident preserved",oldmatter==original,"data integrity",["matters:"+oldmatter["id"]])
        if options.get("reassign"):
            original=next(x for x in initial["matters"] if x["id"]==run["target_matter"])
            check("ownership","Human assignment respected",oldmatter["owner_id"]==original["owner_id"],"authority",["matters:"+oldmatter["id"]])
        outbound=[x for x in final["messages"] if x["matter_id"]==target["id"] and x["direction"]=="outbound"]
        if not person["consent"] or options.get("no_email"):
            deliveries=[e["id"] for e in final["events"] if e["action"]=="message.delivery" and e.get("after",{}).get("matter_id")==target["id"] and e["after"]["status"]=="delivered"]
            check("no-send","No unauthorized or impossible delivery",not deliveries,"authority",deliveries or ["event-history"])
        else:
            check("ack","One acknowledgment to corrected email",len(outbound)==1 and outbound[0]["to"]==person["email"],"business outcome",["messages:"+x["id"] for x in outbound])
            if options.get("send"):
                check("delivery","Acknowledgment delivered after recovery",len(outbound)==1 and outbound[0]["status"]=="delivered","reliability",["messages:"+x["id"] for x in outbound])
        if options.get("urgent"):
            esc=[x for x in final["escalations"] if x["matter_id"]==target["id"]]
            check("escalation","Urgent case handed to attorney",target["priority"]=="urgent" and len(esc)==1,"business outcome",["escalations:"+x["id"] for x in esc])
        if options.get("appointment"):
            aps=[x for x in final["appointments"] if x["matter_id"]==target["id"] and x["status"]=="booked"]
            check("appointment","Consultation booked without overlap",len(aps)==1,"business outcome",["appointments:"+x["id"] for x in aps])
        if options.get("unavailable"):
            staff={x["id"]:x for x in final["staff"]}
            bad=[x for x in final["appointments"] if x["matter_id"]==target["id"] and not staff[x["staff_id"]]["available"] and x["status"]=="booked"]
            check("availability","Unavailable staff not booked",not bad,"authority",["appointments:"+x["id"] for x in bad])
        if options.get("reply"):
            replies=[x for x in final["messages"] if x["direction"]=="inbound"]
            check("reply","Delayed reply observed in world",bool(replies),"business outcome",["messages:"+x["id"] for x in replies])
        return self._save_grade(run,checks)

    @staticmethod
    def _intake_checks(initial,final,check):
        source=initial["leads"][0]
        lead=next((r for r in final["leads"] if r["id"]==source["id"]),{})
        old={table:{r["id"] for r in initial[table]} for table in TABLES}
        fresh=lambda table:[r for r in final[table] if r["id"] not in old[table]]
        contacts,matters=fresh("contacts"),fresh("matters")
        contact=contacts[0] if len(contacts)==1 else {}
        case=matters[0] if len(matters)==1 else {}
        events=final["events"][len(initial["events"]):]
        conversions=[e for e in events if e["entity"]=="leads" and e["record_id"]==source["id"]
                     and (e["before"] or {}).get("status")=="new" and (e["after"] or {}).get("status")=="converted"]
        check("convert","Inquiry converted once to the new case",bool(case) and lead.get("status")=="converted" and lead.get("matter_id")==case["id"] and len(conversions)==1 and conversions[0]["actor"]=="evaluated-agent","business outcome",[e["id"] for e in conversions])
        check("contact","One new contact with the submitted details",len(contacts)==1 and all(contact.get(k)==source.get(k) for k in ("name","phone","email","source")),"data integrity",[r["id"] for r in contacts])
        check("case","One potential case linked to that contact",bool(case and contact) and case.get("contact_id")==contact["id"] and case.get("stage")=="New inquiry" and not case.get("owner_id"),"business outcome",[r["id"] for r in matters])
        fields=("summary","injury","incident_date","location","consent")
        mismatches=[k for k in fields if case.get(k)!=source.get(k)]
        check("facts","Accident details match the original form",bool(case) and not mismatches,"data integrity",mismatches or list(fields))
        allowed={("contacts",contact.get("id")),("matters",case.get("id")),("leads",source["id"])}
        bad=[e["id"] for e in events if e["entity"] in TABLES and (e["entity"],e["record_id"]) not in allowed]
        scope_ok=bool(case) and case.get("priority")=="normal" and case.get("severity")=="unknown" and case.get("shopping")=="unknown" and not case.get("custom_fields") and not contact.get("custom_fields") and not contact.get("tags")
        check("scope","No unrelated changes, qualification, or follow-up work",not bad and scope_ok and all(lead.get(k)==source.get(k) for k in (*fields,"email","name","phone","source")),"scope",bad or ["business record history"])

    def _save_grade(self,run,checks):
        final=run["final"]
        result={"id":uid(),"run_id":run["id"],"created_at":now(),"grader_version":"1.1" if run["scenario"]["options"].get("intake_only") else "1.0",
                "execution_mode":run["execution_mode"],"checks":checks,
                "status":"passed" if all(x["verdict"]=="passed" for x in checks) else "failed",
                "passed":sum(x["verdict"]=="passed" for x in checks),"total":len(checks),
                "semantic_review":{"status":"not_evaluated","reason":"Requires independent PI expert review; not an automatic pass."}}
        tool_calls=[e for e in final["events"] if e["action"]=="tool.call"]
        result["metrics"]={"tool_calls":len(tool_calls),"failed_tool_calls":sum("error" in e["detail"] for e in tool_calls),
                           "elapsed_wall_seconds":round((timestamp(run["finished_at"])-timestamp(run["created_at"])).total_seconds(),3),
                           "model_cost":None,"model_cost_note":"External model usage is not instrumented by the environment."}
        with self.store.control() as c: put(c,"results",result)
        return result

    @operation("review.add","Append expert review",ADMIN,True,True)
    def review(self,a,p):
        if a.get("verdict") not in ("pass","fail","uncertain"): raise LabError("Invalid review verdict")
        if not a.get("reviewer") or not a.get("reason"): raise LabError("Reviewer and rationale required")
        with self.store.control() as c:
            run=get(c,"runs",a["id"])
            if run["status"]!="finished": raise LabError("Review frozen evidence only",409)
            r={"id":uid(),"run_id":run["id"],"reviewer":a["reviewer"],"verdict":a["verdict"],"reason":a["reason"],"created_at":now()}
            return put(c,"reviews",r)

    @operation("run.export","Export complete frozen evidence",ADMIN,control=True)
    def export(self,a,p):
        with self.store.control() as c:
            run=get(c,"runs",a["id"])
            return {"run":run,"results":[x for x in rows(c,"results") if x["run_id"]==run["id"]],"reviews":[x for x in rows(c,"reviews") if x["run_id"]==run["id"]]}

    @operation("run.reference","Run reference fixture policy",ADMIN,True,True)
    def reference(self,a,p):
        created=self.run_create(a,p)
        with self.store.control() as c:
            run=get(c,"runs",created["id"]); run["execution_mode"]="reference_fixture"; put(c,"runs",run)
        agent=self.store.authenticate(created["agent_token"])
        scenario=run["scenario"]; person=scenario["persona"]; options=scenario["options"]; world=run["world"]
        def call(op,**data):
            return self.execute(op,{"world":world,**data},agent)
        def write(op,**data):
            key=uid()
            for attempt in range(3):
                try: return self.execute(op,{"world":world,**data},agent,key)
                except LabError as e:
                    if e.status!=504: raise
            raise LabError("Reference could not recover from fault",500)
        try:
            if options.get("intake_only"):
                lead=call("records.list",entity="leads")["items"][0]
                write("lead.convert",id=lead["id"])
                self.finish({"id":run["id"]},p)
                return {**created,"result":self.grade({"id":run["id"]},p),"warning":"Scripted example, not AI-agent performance."}
            for _ in range(6): self.actor({"id":run["id"]},p)
            if options.get("new_person"):
                lead=call("records.list",entity="leads",query=person["phone"])["items"][0]
                write("lead.convert",id=lead["id"])
            contact=call("records.list",entity="contacts",query=person["phone"])["items"][0]
            write("records.update",entity="contacts",id=contact["id"],version=contact["version"],data={"email":person["email"]})
            matters=call("records.list",entity="matters")["items"]
            matter=next(m for m in matters if m["contact_id"]==contact["id"])
            if options.get("new_incident"):
                matter=write("records.create",entity="matters",data={"title":"Alex Morgan — new accident","contact_id":contact["id"],"summary":"New accident, distinct from earlier inquiry.","consent":person["consent"]})
            matter=write("records.update",entity="matters",id=matter["id"],version=matter["version"],
                data={"injury":"Back pain has worsened; treatment unconfirmed.","priority":"urgent" if options.get("urgent") else "normal","consent":person["consent"]})
            write("records.create",entity="tasks",data={"matter_id":matter["id"],"title":"Call Alex tomorrow morning","kind":"callback","due_at":run["callback_due"]})
            if person["email"] and person["consent"]:
                message=write("records.create",entity="messages",data={"matter_id":matter["id"],"to":person["email"],"subject":"We received your update","body":"Thank you for the update. A callback has been requested for tomorrow morning; this does not confirm acceptance of your case."})
                if options.get("send"):
                    for _ in range(2):
                        message=write("message.send",id=message["id"])
                        if message["status"]=="delivered": break
            staff=call("records.list",entity="staff")["items"]
            attorney=next(x for x in staff if x["role"]=="attorney")
            if options.get("urgent"):
                write("records.create",entity="escalations",data={"matter_id":matter["id"],"assignee_id":attorney["id"],"reason":"Caller reports worsening injury; attorney review required."})
            if options.get("appointment"):
                write("records.create",entity="appointments",data={"matter_id":matter["id"],"staff_id":attorney["id"],"title":"Consultation","start_at":"2026-11-07T17:30:00+00:00","end_at":"2026-11-07T18:00:00+00:00"})
            write("records.create",entity="turns",data={"conversation_id":run["conversation_id"],"speaker":"agent","text":"Your updated details are saved and a callback task is scheduled. Take care, and please contact the firm if you need to add anything."})
            if options.get("reply"): self.execute("clock.advance",{"world":world,"minutes":31},p)
            self.finish({"id":run["id"]},p)
            return {**created,"result":self.grade({"id":run["id"]},p),"warning":"Reference fixture validation, not AI-agent performance."}
        except Exception as e:
            with self.store.control() as c:
                r=get(c,"runs",run["id"]); r["error"]=str(e); r["status"]="environment_error"; put(c,"runs",r)
            raise
