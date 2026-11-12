from dataclasses import asdict, fields
from decimal import Decimal
from ..database.models import ToleranceSetting
from ..validation.tolerance import TolerancePolicy

def get_policy(db) -> TolerancePolicy:
    rows = {r.Key: r.Value for r in db.query(ToleranceSetting).all()}
    kw = {f.name: Decimal(rows[f.name]) for f in fields(TolerancePolicy) if f.name in rows}
    return TolerancePolicy(**kw)

def policy_dict(db) -> dict:
    return {k: str(v) for k, v in asdict(get_policy(db)).items()}

def save_policy(db, values: dict):
    valid = {f.name for f in fields(TolerancePolicy)}
    for k, v in values.items():
        if k not in valid:
            raise ValueError(f"Unknown setting {k}")
        d = Decimal(str(v))
        if d < 0:
            raise ValueError(f"{k} must be >= 0")
        row = db.get(ToleranceSetting, k)
        if row: row.Value = str(d)
        else: db.add(ToleranceSetting(Key=k, Value=str(d)))
    db.commit()
