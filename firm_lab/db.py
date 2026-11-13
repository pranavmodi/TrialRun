import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

def uid():
    return uuid.uuid4().hex

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class LabError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("FIRM_LAB_DATA", ".local")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self.worlds = self.root / "worlds"
        self.worlds.mkdir(exist_ok=True)
        with self.control() as c:
            for table in ("worlds", "grants", "scenarios", "runs", "results", "reviews", "profiles"):
                c.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        tokenfile = self.root / "controller.token"
        if not tokenfile.exists():
            fd = os.open(tokenfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_urlsafe(36))
        self.controller = tokenfile.read_text().strip()

    @contextmanager
    def connect(self, path):
        c = sqlite3.connect(path, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=20000")
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def control(self):
        return self.connect(self.root / "control.sqlite")

    def path(self, world):
        if not isinstance(world, str) or len(world) != 32 or any(x not in "0123456789abcdef" for x in world):
            raise LabError("Invalid world identifier", 404)
        return self.worlds / (world + ".sqlite")

    def world(self, world):
        path = self.path(world)
        if not path.exists():
            raise LabError("World not found", 404)
        return self.connect(path)

    def authenticate(self, token):
        if token and secrets.compare_digest(token, self.controller):
            return {"role": "controller", "actor": "controller", "world": None}
        with self.control() as c:
            for grant in rows(c, "grants"):
                if token and secrets.compare_digest(grant["hash"], digest(token)) and not grant.get("revoked"):
                    return {k: grant[k] for k in ("role", "actor", "world")}
        raise LabError("A valid lab access token is required", 401)

    def initialize_world(self, world, tables):
        with self.connect(self.path(world)) as c:
            for table in (*tables, "meta", "events", "idempotency", "scheduled", "faults"):
                c.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)")

def rows(c, table):
    return [json.loads(r["data"]) for r in c.execute(f"SELECT data FROM {table} ORDER BY rowid")]

def get(c, table, key, required=True):
    row = c.execute(f"SELECT data FROM {table} WHERE id=?", (key,)).fetchone()
    if not row:
        if required:
            raise LabError(f"{table} record not found", 404)
        return None
    return json.loads(row["data"])

def put(c, table, data):
    c.execute(f"INSERT INTO {table}(id,data) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (data["id"], json.dumps(data)))
    return data

def meta(c):
    return get(c, "meta", "world")

tool_call_id = ContextVar("tool_call_id", default=None)

def audit(c, actor, action, entity, before, after, detail=None):
    event = {"id": uid(), "at": meta(c)["clock"], "wall_at": now(), "actor": actor,
             "action": action, "entity": entity, "record_id": (after or before or {}).get("id"),
             "before": before, "after": after, "detail": detail or {}}
    if tool_call_id.get(): event["tool_call_id"]=tool_call_id.get()
    put(c, "events", event)
    return event
