from typing import Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..services import settings_service as S
from ..services.common import audit

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("/tolerances")
def get_t(db: Session = Depends(get_db)):
    return S.policy_dict(db)

@router.put("/tolerances")
def put_t(values: Dict[str, str], db: Session = Depends(get_db)):
    old = S.policy_dict(db)
    try:
        S.save_policy(db, values)
    except Exception as e:
        db.rollback(); raise HTTPException(422, str(e))
    audit(db, "Settings", 0, "TOLERANCE_UPDATE", old=old, new=values); db.commit()
    return S.policy_dict(db)
