from copy import deepcopy
from datetime import datetime
from .db import LabError, get

def f(label, type="text", required=False, default=None, options=None, ref=None):
    return {k:v for k,v in dict(label=label, type=type, required=required, default=default, options=options, ref=ref).items() if v is not None}

SCHEMAS = {
 "contacts": {
  "name": f("Full name", required=True), "email": f("Email", "email"), "phone": f("Callback number"),
  "source": f("Lead source", default="Website"), "tags": f("Tags"), "custom_fields": f("Custom fields", "json", default={})},
 "leads": {
  "name": f("Full name", required=True), "email": f("Email", "email"), "phone": f("Callback number", required=True),
  "summary": f("What happened", "textarea", True), "injury": f("Injuries / treatment", "textarea"),
  "incident_date": f("Incident date", "date"), "location": f("Location"), "source": f("Source", default="Website"),
  "consent": f("Contact permission", "boolean", default=False),
  "status": f("State", "select", default="new", options=["new","converted","ignored"]),
  "matter_id": f("Converted matter", ref="matters")},
 "matters": {
  "title": f("Matter name", required=True), "contact_id": f("Contact", required=True, ref="contacts"),
  "stage": f("Stage", "stage", default="New inquiry"), "matter_type": f("Matter type", default="Motor vehicle accident"),
  "summary": f("Incident summary", "textarea"), "injury": f("Injuries / treatment", "textarea"),
  "incident_date": f("Incident date", "date"), "location": f("Location"),
  "priority": f("Priority", "select", default="normal", options=["normal","urgent"]),
  "severity": f("Injury severity", "select", default="unknown", options=["unknown","minor","serious","catastrophic"]),
  "shopping": f("Comparing firms", "select", default="unknown", options=["unknown","yes","no"]),
  "owner_id": f("Assigned staff", ref="staff"), "consent": f("Contact permission", "boolean", default=False),
  "custom_fields": f("Custom fields", "json", default={})},
 "notes": {"matter_id": f("Matter", required=True, ref="matters"), "body": f("Note", "textarea", True)},
 "staff": {"name": f("Name", required=True), "role": f("Role", "select", default="intake", options=["intake","attorney"]),
  "available": f("Available", "boolean", default=True),
  "available_from": f("Available from", "datetime"), "available_until": f("Available until", "datetime")},
 "tasks": {"matter_id": f("Matter", required=True, ref="matters"), "title": f("Task", required=True),
  "assignee_id": f("Assignee", ref="staff"), "due_at": f("Due", "datetime", True),
  "kind": f("Kind", "select", default="callback", options=["callback","review","followup","conflict_check"]),
  "status": f("State", "select", default="open", options=["open","completed","cancelled"])},
 "messages": {"matter_id": f("Matter", required=True, ref="matters"),
  "channel": f("Channel", "select", default="email", options=["email","sms","internal"]),
  "direction": f("Direction", "select", default="outbound", options=["outbound","inbound"]),
  "to": f("Recipient", required=True), "subject": f("Subject"), "body": f("Message", "textarea", True)},
 "appointments": {"matter_id": f("Matter", required=True, ref="matters"), "staff_id": f("Staff", required=True, ref="staff"),
  "title": f("Appointment", required=True), "start_at": f("Start", "datetime", True), "end_at": f("End", "datetime", True),
  "status": f("State", "select", default="booked", options=["booked","cancelled"])},
 "documents": {"matter_id": f("Matter", required=True, ref="matters"), "name": f("Name", required=True),
  "content": f("Document text", "textarea", True), "kind": f("Kind", "select", default="intake", options=["intake","incident_report","medical","agreement","other"])},
 "escalations": {"matter_id": f("Matter", required=True, ref="matters"), "reason": f("Reason", "textarea", True),
  "assignee_id": f("Attorney", required=True, ref="staff")},
 "forms": {"name": f("Form name", required=True), "fields": f("Fields", "json", default=[{"key":"summary","label":"What happened","required":True}])},
 "workflows": {"name": f("Workflow name", required=True), "steps": f("Steps", "json", required=True)},
 "conversations": {"matter_id": f("Matter", ref="matters"), "title": f("Conversation", required=True)},
 "turns": {"conversation_id": f("Conversation", required=True, ref="conversations"),
  "speaker": f("Speaker", "select", required=True, options=["agent","caller","staff"]), "text": f("Text", "textarea", True)},
 "workflow_instances": {}
}
TABLES = tuple(SCHEMAS)
READONLY = {"workflow_instances"}
LOCKED_FIELDS = {"leads": {"status","matter_id"}, "messages":{"direction"}}
CONFIG_TABLES = {"staff","forms","workflows"}
DEFAULT_POLICY = {
 "firm_name": "Harbor & Stone Injury Law",
 "stages": ["New inquiry","Screening","Consultation scheduled","Awaiting agreement","Hired","Not hired"],
 "timezone": "America/Los_Angeles",
 "email_mode": "draft",
 "escalation_rule": "Urgent matters require an attorney handoff. Never promise acceptance or provide medical advice.",
 "qualification": "Collect incident, contact and injury facts. Preserve uncertainty. Confirm corrections. Returning callers may have a new incident.",
 "office_hours": "Monday–Friday, 09:00–17:00",
 "ack_subject": "We received your consultation request",
 "ack_body": "Thank you for contacting Harbor & Stone. Our intake team will follow up. Your inquiry does not mean the firm has accepted your case.",
}

def timestamp(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if d.tzinfo is None:
            raise ValueError()
        return d
    except ValueError:
        raise LabError("Datetime must be ISO 8601 with a timezone")

def validate(c, entity, data, existing=None):
    if entity not in SCHEMAS or entity in READONLY:
        raise LabError("Unsupported entity", 404)
    schema = SCHEMAS[entity]
    extra = set(data) - set(schema)
    if extra:
        raise LabError("Unknown fields: " + ", ".join(sorted(extra)))
    result = {k: deepcopy(v["default"]) for k,v in schema.items() if "default" in v}
    if existing:
        result.update({k:v for k,v in existing.items() if k in schema})
    result.update(data)
    for key, spec in schema.items():
        value = result.get(key)
        if spec.get("required") and (value is None or value == ""):
            raise LabError(f"{spec['label']} is required")
        if value is None or value == "":
            continue
        typ = spec["type"]
        if typ == "boolean":
            if not isinstance(value,bool): raise LabError(f"{key} must be boolean")
        elif typ == "json":
            if not isinstance(value,(dict,list)): raise LabError(f"{key} must be an object or array")
        elif not isinstance(value,str):
            raise LabError(f"{key} must be text")
        if isinstance(value,str) and len(value)>200000: raise LabError("Field too large")
        if spec.get("options") and value not in spec["options"]: raise LabError(f"Invalid {key}")
        if typ == "email" and ("@" not in value or any(x.isspace() for x in value)): raise LabError("Invalid email format")
        if typ == "datetime": timestamp(value)
        if typ == "date":
            try: datetime.strptime(value,"%Y-%m-%d")
            except ValueError: raise LabError("Date must be YYYY-MM-DD")
        if spec.get("ref"): get(c, spec["ref"], value)
    return result
