from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import FinancialEntry
from ..deps import current_user, active_user

router=APIRouter()
class EntryIn(BaseModel):
    kind:str
    description:str
    amount:float
    status:str="paid"
    due_date:str=""

@router.get("")
def list_entries(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(FinancialEntry).filter(FinancialEntry.company_id==user.company_id).order_by(FinancialEntry.id.desc()).all()

@router.post("")
def create_entry(data:EntryIn,db:Session=Depends(get_db),user=Depends(active_user)):
    e=FinancialEntry(company_id=user.company_id,**data.model_dump()); db.add(e); db.commit(); db.refresh(e); return e
