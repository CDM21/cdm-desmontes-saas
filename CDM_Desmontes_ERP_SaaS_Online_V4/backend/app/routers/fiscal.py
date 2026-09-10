import json, os, httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import active_user
from ..models import FiscalDocument

router=APIRouter()
class FiscalIn(BaseModel):
    series:str="1"; number:str=""; operation_type:str="saida"; purpose:str="normal"; operation_nature:str="Venda de mercadoria"; referenced_key:str=""; order_number:str=""; intermediary_indicator:str="sem_intermediador"; recipient:str=""; recipient_ie:str=""; sections:dict=Field(default_factory=dict)

def serialize(row):
    try: sections=json.loads(row.sections_json or "{}")
    except Exception: sections={}
    return {"id":row.id,"series":row.series,"number":row.number,"operation_type":row.operation_type,"purpose":row.purpose,"operation_nature":row.operation_nature,"referenced_key":row.referenced_key,"order_number":row.order_number,"intermediary_indicator":row.intermediary_indicator,"recipient":row.recipient,"recipient_ie":row.recipient_ie,"sections":sections,"status":row.status,"access_key":row.access_key,"created_at":row.created_at,"updated_at":row.updated_at}
@router.get("")
def list_documents(db:Session=Depends(get_db),user=Depends(active_user)):
    return [serialize(x) for x in db.query(FiscalDocument).filter(FiscalDocument.company_id==user.company_id).order_by(FiscalDocument.id.desc()).limit(300).all()]
@router.post("")
def create_draft(data:FiscalIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=FiscalDocument(company_id=user.company_id,**data.model_dump(exclude={"sections"}),sections_json=json.dumps(data.sections,ensure_ascii=False),status="rascunho");db.add(row);db.commit();db.refresh(row);return serialize(row)
@router.put("/{doc_id}")
def update_draft(doc_id:int,data:FiscalIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(FiscalDocument).filter(FiscalDocument.id==doc_id,FiscalDocument.company_id==user.company_id).first()
    if not row: raise HTTPException(404,"Documento fiscal não encontrado")
    if row.status=="autorizada": raise HTTPException(400,"NF-e autorizada não pode ser alterada")
    for k,v in data.model_dump(exclude={"sections"}).items(): setattr(row,k,v)
    row.sections_json=json.dumps(data.sections,ensure_ascii=False);db.commit();db.refresh(row);return serialize(row)
@router.post("/{doc_id}/emit")
def emit(doc_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(FiscalDocument).filter(FiscalDocument.id==doc_id,FiscalDocument.company_id==user.company_id).first()
    if not row: raise HTTPException(404,"Documento fiscal não encontrado")
    provider_url=(os.getenv("FISCAL_PROVIDER_URL") or "").strip();provider_token=(os.getenv("FISCAL_PROVIDER_TOKEN") or "").strip()
    if not provider_url or not provider_token: raise HTTPException(503,"Emissão real de NF-e ainda não configurada no servidor. Configure o provedor fiscal e o certificado da empresa.")
    payload=serialize(row);headers={"Authorization":f"Bearer {provider_token}","Content-Type":"application/json"}
    try:
        with httpx.Client(timeout=45) as client: response=client.post(provider_url,json=payload,headers=headers)
        row.provider_response=response.text[:12000]
        if response.status_code>=400:
            row.status="rejeitada";db.commit();raise HTTPException(502,"O provedor fiscal rejeitou a emissão. Consulte o retorno do provedor.")
        data=response.json() if "application/json" in response.headers.get("content-type","") else {};row.status=str(data.get("status") or "processando").lower()
        if row.status in {"authorized","autorizada","approved"}: row.status="autorizada"
        row.access_key=str(data.get("access_key") or data.get("chave") or "");db.commit();db.refresh(row);return serialize(row)
    except HTTPException: raise
    except Exception as exc: raise HTTPException(502,f"Falha ao comunicar com o provedor fiscal: {str(exc)[:240]}")
