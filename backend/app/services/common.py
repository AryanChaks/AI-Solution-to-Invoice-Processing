import json
from decimal import Decimal
from datetime import date, datetime
from ..database.models import AuditLog

def jdump(o) -> str:
    return json.dumps(o, default=lambda x: str(x) if isinstance(x, (Decimal, date, datetime)) else repr(x))

def audit(db, entity_type, entity_id, action, old=None, new=None, reason=None, actor="local-user"):
    db.add(AuditLog(Entity_Type=entity_type, Entity_ID=entity_id, Action=action,
                    Old_Value=None if old is None else jdump(old), New_Value=None if new is None else jdump(new),
                    Reason=reason, Actor=actor))
