from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import FinancialEntry
from ..deps import active_user, require_roles

router=APIRouter()

class EntryIn(BaseModel):
    kind:str
    description:str
    amount:float
    status:str="paid"
    due_date:str=""

def _manual_entry(row: FinancialEntry):
    return not str(row.description or "").strip().lower().startswith("venda #")

@router.get("")
def list_entries(db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager"))):
    return db.query(FinancialEntry).filter(FinancialEntry.company_id==user.company_id).order_by(FinancialEntry.id.desc()).all()

@router.post("")
def create_entry(data:EntryIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager"))):
    if data.kind not in ("income","expense"):
        raise HTTPException(400,"Tipo de lançamento inválido")
    if float(data.amount or 0) < 0:
        raise HTTPException(400,"O valor não pode ser negativo")
    e=FinancialEntry(company_id=user.company_id,**data.model_dump())
    db.add(e); db.commit(); db.refresh(e)
    return e

@router.put("/{entry_id}")
def update_entry(entry_id:int,data:EntryIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager"))):
    row=db.query(FinancialEntry).filter(FinancialEntry.id==entry_id,FinancialEntry.company_id==user.company_id).first()
    if not row:
        raise HTTPException(404,"Lançamento não encontrado")
    if not _manual_entry(row):
        raise HTTPException(400,"Lançamentos automáticos de vendas devem ser corrigidos pela própria venda")
    if data.kind not in ("income","expense"):
        raise HTTPException(400,"Tipo de lançamento inválido")
    if float(data.amount or 0) < 0:
        raise HTTPException(400,"O valor não pode ser negativo")
    for key,value in data.model_dump().items():
        setattr(row,key,value)
    db.commit(); db.refresh(row)
    return row

@router.delete("/{entry_id}")
def delete_entry(entry_id:int,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager"))):
    row=db.query(FinancialEntry).filter(FinancialEntry.id==entry_id,FinancialEntry.company_id==user.company_id).first()
    if not row:
        raise HTTPException(404,"Lançamento não encontrado")
    if not _manual_entry(row):
        raise HTTPException(400,"Lançamentos automáticos de vendas não podem ser excluídos pelo Financeiro")
    db.delete(row); db.commit()
    return {"ok":True}
