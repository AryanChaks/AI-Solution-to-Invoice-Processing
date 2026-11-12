import json, threading
from ..database.connection import SessionLocal
from ..database.models import ProcessingRun
from ..workflow.graph import run_workflow

def create_run(db, source, file_name=None, path=None, file_hash=None, parent=None) -> ProcessingRun:
    r = ProcessingRun(Source_Type=source, Uploaded_File_Name=file_name, Stored_File_Path=path, File_Hash=file_hash,
                      Processing_Status="RUNNING", Parent_Run_ID=parent)
    db.add(r); db.commit(); db.refresh(r)
    return r

def start_background(run_id: int, state: dict):
    threading.Thread(target=run_workflow, args=(run_id, state), daemon=True).start()

def jl(s):
    try: return json.loads(s) if s else None
    except Exception: return None

def row(o, exclude=()):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns if c.name not in exclude}
