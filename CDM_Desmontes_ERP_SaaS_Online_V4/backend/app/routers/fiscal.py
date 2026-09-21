import base64, json, os, re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import httpx

from ..db import get_db
from ..deps import active_user
from ..models import Company, FiscalConfig, FiscalDocument, TaxConfig
from ..crypto import encrypt_secret, decrypt_secret

router=APIRouter()

class FiscalIn(BaseModel):
    series:str="1"; number:str=""; operation_type:str="saida"; purpose:str="normal"; operation_nature:str="Venda de mercadoria"; referenced_key:str=""; order_number:str=""; intermediary_indicator:str="sem_intermediador"; recipient:str=""; recipient_ie:str=""; sections:dict=Field(default_factory=dict)

class SetupIn(BaseModel):
    environment:str="homologacao"
    production_token:str=""
    homologation_token:str=""
    auto_issue_sales:bool=False

class CancelIn(BaseModel):
    justification:str


def _digits(v): return re.sub(r"\D", "", str(v or ""))
def _base(environment): return "https://api.focusnfe.com.br" if environment=="producao" else "https://homologacao.focusnfe.com.br"
def _regime(value):
    v=(value or "").lower()
    if "mei" in v:return 4
    if "simples" in v:return 1
    return 3

def _config(db, company_id, create=False):
    row=db.query(FiscalConfig).filter(FiscalConfig.company_id==company_id).first()
    if not row and create:
        row=FiscalConfig(company_id=company_id);db.add(row);db.commit();db.refresh(row)
    return row

def _token(cfg):
    if not cfg:return ""
    enc=cfg.production_token_enc if cfg.environment=="producao" else cfg.homologation_token_enc
    return decrypt_secret(enc)

def _public_setup(cfg, company=None, tax=None):
    cfg=cfg or FiscalConfig()
    company_ready=bool(
        company and len(_digits(company.cnpj))==14 and company.legal_name and company.city
        and company.state and company.address and _digits(company.state_registration)
    )
    tax_ready=bool(tax and tax.cfop_default and tax.csosn_default)
    certificate_ready=bool(cfg.certificate_uploaded)
    connection_ready=bool(_token(cfg))
    checks=[
        {"id":"company","label":"Dados da empresa","done":company_ready},
        {"id":"tax","label":"Tributação","done":tax_ready},
        {"id":"certificate","label":"Certificado A1","done":certificate_ready},
        {"id":"connection","label":"Conexão fiscal","done":connection_ready},
    ]
    completed=sum(1 for x in checks if x["done"])
    return {
        "provider":cfg.provider or "focusnfe","environment":cfg.environment or "homologacao",
        "provider_company_id":cfg.provider_company_id or "","certificate_name":cfg.certificate_name or "",
        "certificate_uploaded":certificate_ready,"setup_status":cfg.setup_status or "pending",
        "last_test_status":cfg.last_test_status or "","last_error":cfg.last_error or "",
        "auto_issue_sales":bool(cfg.auto_issue_sales),
        "has_production_token":bool(cfg.production_token_enc),"has_homologation_token":bool(cfg.homologation_token_enc),
        "company_ready":company_ready,"tax_ready":tax_ready,"connection_ready":connection_ready,
        "service_available":bool((os.getenv("FOCUS_MASTER_TOKEN") or "").strip()),
        "checks":checks,"completed":completed,"total":len(checks),"percent":round(completed/len(checks)*100),
        "ready":bool(cfg.setup_status=="ready" and company_ready and tax_ready and certificate_ready and connection_ready),
    }

def serialize(row):
    try: sections=json.loads(row.sections_json or "{}")
    except Exception: sections={}
    return {"id":row.id,"series":row.series,"number":row.number,"operation_type":row.operation_type,"purpose":row.purpose,"operation_nature":row.operation_nature,"referenced_key":row.referenced_key,"order_number":row.order_number,"intermediary_indicator":row.intermediary_indicator,"recipient":row.recipient,"recipient_ie":row.recipient_ie,"sections":sections,"status":row.status,"provider_ref":row.provider_ref,"access_key":row.access_key,"xml_url":row.xml_url,"danfe_url":row.danfe_url,"created_at":row.created_at,"updated_at":row.updated_at}

def _status(data):
    raw=str(data.get("status") or data.get("status_sefaz") or "processando").lower()
    if raw in {"autorizado","autorizada","authorized","approved"}:return "autorizada"
    if raw in {"cancelado","cancelada","canceled"}:return "cancelada"
    if raw in {"erro_autorizacao","rejeitada","rejeitado","error","failed","denied"}:return "rejeitada"
    if raw in {"processando_autorizacao","processando","processing","queued","pending"}:return "processando"
    return raw

def _update_provider_fields(row,data):
    row.status=_status(data)
    row.access_key=str(data.get("chave_nfe") or data.get("chave") or data.get("access_key") or row.access_key or "")
    row.number=str(data.get("numero") or row.number or "")
    row.series=str(data.get("serie") or row.series or "")
    row.xml_url=str(data.get("caminho_xml_nota_fiscal") or data.get("url_xml") or row.xml_url or "")
    row.danfe_url=str(data.get("caminho_danfe") or data.get("url_danfe") or row.danfe_url or "")
    row.provider_response=json.dumps(data,ensure_ascii=False)[:20000]


def _focus_company_payload(company,tax,cert_b64="",cert_password=""):
    p={
      "nome":company.legal_name or company.trade_name,"nome_fantasia":company.trade_name or company.legal_name,
      "cnpj":_digits(company.cnpj),"inscricao_estadual":_digits(company.state_registration) or None,
      "regime_tributario":_regime(company.tax_regime),"logradouro":company.address,"numero":company.number or "S/N",
      "complemento":company.complement or "","municipio":company.city,"cep":_digits(company.cep) or None,"uf":company.state,
      "telefone":_digits(company.phone),"email":company.email,"habilita_nfe":True,"orientacao_danfe":"portrait",
      "serie_nfe_producao":"1","serie_nfe_homologacao":"1",
    }
    if cert_b64:p.update({"arquivo_certificado_base64":cert_b64,"senha_certificado":cert_password,"certificado_especifico":True})
    return {k:v for k,v in p.items() if v not in {None,""}}


def _capture_focus_tokens(cfg,data):
    # A API/conta pode devolver nomes diferentes conforme o contrato. Aceitamos os formatos conhecidos sem expor os tokens.
    prod=data.get("token_producao") or data.get("production_token") or data.get("token") if isinstance(data,dict) else ""
    hom=data.get("token_homologacao") or data.get("homologation_token") if isinstance(data,dict) else ""
    if prod: cfg.production_token_enc=encrypt_secret(str(prod))
    if hom: cfg.homologation_token_enc=encrypt_secret(str(hom))
    if isinstance(data,dict): cfg.provider_company_id=str(data.get("id") or data.get("empresa_id") or cfg.provider_company_id or "")


@router.get("/setup")
def get_setup(db:Session=Depends(get_db),user=Depends(active_user)):
    company=db.get(Company,user.company_id);tax=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first();cfg=_config(db,user.company_id,True)
    return _public_setup(cfg,company,tax)

@router.put("/setup")
def save_setup(data:SetupIn,db:Session=Depends(get_db),user=Depends(active_user)):
    cfg=_config(db,user.company_id,True)
    if data.environment not in {"homologacao","producao"}:raise HTTPException(400,"Ambiente fiscal inválido")
    cfg.environment=data.environment;cfg.auto_issue_sales=data.auto_issue_sales
    if data.production_token.strip():cfg.production_token_enc=encrypt_secret(data.production_token.strip())
    if data.homologation_token.strip():cfg.homologation_token_enc=encrypt_secret(data.homologation_token.strip())
    cfg.setup_status="configured" if cfg.certificate_uploaded and _token(cfg) else "pending";cfg.last_error="";db.commit()
    company=db.get(Company,user.company_id);tax=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first()
    return _public_setup(cfg,company,tax)

@router.get("/cnpj/{cnpj}")
def lookup_cnpj(cnpj:str,user=Depends(active_user)):
    value=_digits(cnpj)
    if len(value)!=14:raise HTTPException(400,"Digite um CNPJ com 14 números")
    try:
        with httpx.Client(timeout=20) as c:r=c.get(f"https://brasilapi.com.br/api/cnpj/v1/{value}")
        if r.status_code>=400:raise HTTPException(404,"CNPJ não encontrado na consulta pública")
        d=r.json()
        ies=d.get("inscricoes_estaduais") or []
        active_ie=next((x for x in ies if x.get("ativo") is True),ies[0] if ies else {})
        ie=str(active_ie.get("inscricao_estadual") or active_ie.get("numero") or "")
        tax_regime="MEI" if d.get("opcao_pelo_mei") else ("Simples Nacional" if d.get("opcao_pelo_simples") else "")
        return {
            "cnpj":value,"legal_name":d.get("razao_social") or "",
            "trade_name":d.get("nome_fantasia") or d.get("razao_social") or "",
            "state_registration":ie,"tax_regime":tax_regime,
            "email":d.get("email") or "","phone":d.get("ddd_telefone_1") or d.get("ddd_telefone_2") or "",
            "cep":_digits(d.get("cep")),"state":d.get("uf") or "","city":d.get("municipio") or "",
            "address":d.get("logradouro") or "","number":d.get("numero") or "","complement":d.get("complemento") or ""
        }
    except HTTPException:raise
    except Exception as exc:raise HTTPException(502,f"Não foi possível consultar o CNPJ agora: {str(exc)[:120]}")

@router.post("/setup/certificate")
async def upload_certificate(certificate:UploadFile=File(...),password:str=Form(default=""),db:Session=Depends(get_db),user=Depends(active_user)):
    company=db.get(Company,user.company_id);tax=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first();cfg=_config(db,user.company_id,True)
    if not company or len(_digits(company.cnpj))!=14:raise HTTPException(400,"Cadastre um CNPJ válido nos dados da empresa antes do certificado")
    name=(certificate.filename or "certificado.pfx")
    if not name.lower().endswith((".pfx",".p12")):raise HTTPException(400,"Envie um certificado digital A1 no formato .pfx ou .p12")
    master=(os.getenv("FOCUS_MASTER_TOKEN") or "").strip()
    if not master:
        raise HTTPException(503,"A emissão fiscal ainda não está disponível para configuração nesta instalação. Tente novamente mais tarde.")
    content=await certificate.read()
    if not content or len(content)>8*1024*1024:raise HTTPException(400,"Certificado vazio ou acima de 8 MB")
    if master:
        payload=_focus_company_payload(company,tax,base64.b64encode(content).decode(),password)
        try:
            with httpx.Client(timeout=60) as c:
                if cfg.provider_company_id:
                    r=c.put(f"https://api.focusnfe.com.br/v2/empresas/{cfg.provider_company_id}",json=payload,auth=(master,""))
                else:
                    r=c.post("https://api.focusnfe.com.br/v2/empresas",json=payload,auth=(master,""))
            data=r.json() if "application/json" in r.headers.get("content-type","") else {"message":r.text[:1200]}
            if r.status_code>=400:raise RuntimeError(data.get("mensagem") or data.get("message") or r.text[:900])
            _capture_focus_tokens(cfg,data)
        except Exception as exc:
            cfg.last_error=f"Focus NFe: {str(exc)[:900]}";cfg.last_test_status="error";db.commit();raise HTTPException(400,cfg.last_error)
    # Nunca gravamos o arquivo ou a senha do certificado no CDM. Apenas registramos que foi enviado ao provedor.
    cfg.certificate_name=name;cfg.certificate_uploaded=True;cfg.last_error="";cfg.last_test_status="certificate_ok"
    if _token(cfg):cfg.setup_status="ready"
    else:cfg.setup_status="configured" if master else "pending"
    db.commit()
    return _public_setup(cfg,company,tax)

@router.post("/setup/test")
def test_setup(db:Session=Depends(get_db),user=Depends(active_user)):
    company=db.get(Company,user.company_id);tax=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first();cfg=_config(db,user.company_id,True);token=_token(cfg)
    problems=[]
    if not company or len(_digits(company.cnpj))!=14:problems.append("CNPJ da empresa")
    if not company or not company.legal_name or not company.city or not company.state or not company.address:problems.append("dados da empresa")
    if not company or not _digits(company.state_registration):problems.append("inscrição estadual")
    if not tax or not tax.cfop_default or not tax.csosn_default:problems.append("configuração tributária")
    if not cfg.certificate_uploaded:problems.append("certificado A1")
    if not token:problems.append("conexão com o emissor fiscal")
    if problems:
        cfg.last_test_status="pending";cfg.last_error="Falta: "+", ".join(problems);db.commit();return {"ok":False,"message":cfg.last_error,"setup":_public_setup(cfg,company,tax)}
    cfg.last_test_status="ok";cfg.last_error="";cfg.setup_status="ready";db.commit();return {"ok":True,"message":"Configuração fiscal pronta para emissão","setup":_public_setup(cfg,company,tax)}

@router.get("")
def list_documents(db:Session=Depends(get_db),user=Depends(active_user)):
    return [serialize(x) for x in db.query(FiscalDocument).filter(FiscalDocument.company_id==user.company_id).order_by(FiscalDocument.id.desc()).limit(300).all()]

@router.post("")
def create_draft(data:FiscalIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=FiscalDocument(company_id=user.company_id,**data.model_dump(exclude={"sections"}),sections_json=json.dumps(data.sections,ensure_ascii=False),status="rascunho");db.add(row);db.commit();db.refresh(row);return serialize(row)

@router.put("/{doc_id}")
def update_draft(doc_id:int,data:FiscalIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(FiscalDocument).filter(FiscalDocument.id==doc_id,FiscalDocument.company_id==user.company_id).first()
    if not row:raise HTTPException(404,"Documento fiscal não encontrado")
    if row.status in {"autorizada","cancelada"}:raise HTTPException(400,"Este documento fiscal não pode ser alterado")
    for k,v in data.model_dump(exclude={"sections"}).items():setattr(row,k,v)
    row.sections_json=json.dumps(data.sections,ensure_ascii=False);db.commit();db.refresh(row);return serialize(row)

def _nfe_payload(row,company,tax):
    sec=json.loads(row.sections_json or "{}");item=sec.get("items") or {};dest=sec.get("recipient") or {};transport=sec.get("transport") or {};financial=sec.get("financial") or {};tribut=sec.get("taxation") or {}
    qty=float(item.get("quantity") or 1);unit=float(item.get("unit_value") or 0);total=round(qty*unit,2)
    ncm=_digits(item.get("ncm") or tribut.get("ncm") or (tax.ncm_default if tax else ""))
    cfop=_digits(item.get("cfop") or tribut.get("cfop") or (tax.cfop_default if tax else "5102"))
    if not item.get("description") or total<=0 or not ncm:raise HTTPException(400,"Complete descrição, valor e NCM do item antes de emitir")
    if len(ncm)!=8:raise HTTPException(400,"O NCM do item deve ter exatamente 8 números")
    if len(cfop)!=4:raise HTTPException(400,"O CFOP deve ter exatamente 4 números")
    cpfcnpj=_digits(dest.get("cpf_cnpj"))
    payload={
      "natureza_operacao":row.operation_nature or "Venda de mercadoria","data_emissao":datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
      "tipo_documento":"1" if row.operation_type=="saida" else "0","finalidade_emissao":{"normal":"1","complementar":"2","ajuste":"3","devolucao":"4"}.get(row.purpose,"1"),
      "cnpj_emitente":_digits(company.cnpj),"nome_emitente":company.legal_name or company.trade_name,"nome_fantasia_emitente":company.trade_name,
      "logradouro_emitente":company.address,"numero_emitente":company.number or "S/N","municipio_emitente":company.city,"uf_emitente":company.state,"cep_emitente":_digits(company.cep),"inscricao_estadual_emitente":_digits(company.state_registration),"regime_tributario_emitente":_regime(company.tax_regime),
      "nome_destinatario":dest.get("name") or row.recipient or "CONSUMIDOR FINAL","indicador_inscricao_estadual_destinatario":"1" if row.recipient_ie else "9","inscricao_estadual_destinatario":_digits(row.recipient_ie),
      "logradouro_destinatario":dest.get("address") or "","numero_destinatario":dest.get("number") or "S/N","bairro_destinatario":dest.get("neighborhood") or "","municipio_destinatario":dest.get("city") or "","uf_destinatario":dest.get("state") or company.state,"cep_destinatario":_digits(dest.get("cep")),
      "valor_produtos":total,"valor_total":total,"modalidade_frete":{"emitente":0,"destinatario":1,"terceiros":2,"sem_frete":9}.get(transport.get("freight_mode"),9),
      "items":[{"numero_item":"1","codigo_produto":str(item.get("sku") or f"CDM{row.id}"),"descricao":str(item.get("description")),"cfop":cfop,"unidade_comercial":str(item.get("unit") or "UN"),"quantidade_comercial":qty,"valor_unitario_comercial":unit,"valor_bruto":total,"unidade_tributavel":str(item.get("unit") or "UN"),"quantidade_tributavel":qty,"valor_unitario_tributavel":unit,"codigo_ncm":ncm,"icms_situacao_tributaria":str(tribut.get("csosn") or (tax.csosn_default if tax else "102")),"pis_situacao_tributaria":str((tax.pis_cst if tax else "49") or "49"),"cofins_situacao_tributaria":str((tax.cofins_cst if tax else "49") or "49")}],
      "formas_pagamento":[{"forma_pagamento":{"pix":"17","dinheiro":"01","cartao_credito":"03","cartao_debito":"04","boleto":"15","transferencia":"18"}.get(financial.get("payment_method"),"99"),"valor_pagamento":float(financial.get("amount") or total)}],
    }
    if len(cpfcnpj)==11:payload["cpf_destinatario"]=cpfcnpj
    if len(cpfcnpj)==14:payload["cnpj_destinatario"]=cpfcnpj
    if row.series:payload["serie"]=row.series
    if row.number:payload["numero"]=row.number
    if row.referenced_key:payload["notas_referenciadas"]=[{"chave_nfe":_digits(row.referenced_key)}]
    return {k:v for k,v in payload.items() if v not in {None,""}}

@router.post("/{doc_id}/emit")
def emit(doc_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(FiscalDocument).filter(FiscalDocument.id==doc_id,FiscalDocument.company_id==user.company_id).first()
    if not row:raise HTTPException(404,"Documento fiscal não encontrado")
    company=db.get(Company,user.company_id);tax=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first();cfg=_config(db,user.company_id,False);token=_token(cfg)
    if not cfg or cfg.setup_status not in {"ready","configured"} or not token:raise HTTPException(503,"Conclua a configuração fiscal antes de emitir")
    ref=row.provider_ref or f"CDM{user.company_id}NFE{row.id}";row.provider_ref=ref
    payload=_nfe_payload(row,company,tax)
    try:
        with httpx.Client(timeout=60) as c:r=c.post(f"{_base(cfg.environment)}/v2/nfe",params={"ref":ref},json=payload,auth=(token,""))
        data=r.json() if "application/json" in r.headers.get("content-type","") else {"message":r.text[:2000]}
        _update_provider_fields(row,data)
        if r.status_code>=400:
            row.status="rejeitada";db.commit();raise HTTPException(400,str(data.get("mensagem") or data.get("message") or data)[:900])
        db.commit();db.refresh(row);return serialize(row)
    except HTTPException:raise
    except Exception as exc:raise HTTPException(502,f"Falha ao comunicar com o provedor fiscal: {str(exc)[:240]}")

@router.post("/{doc_id}/refresh")
def refresh_document(doc_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(FiscalDocument).filter(FiscalDocument.id==doc_id,FiscalDocument.company_id==user.company_id).first();cfg=_config(db,user.company_id,False);token=_token(cfg)
    if not row:raise HTTPException(404,"Documento fiscal não encontrado")
    if not row.provider_ref or not token:raise HTTPException(400,"Documento ainda não foi enviado ao provedor")
    with httpx.Client(timeout=40) as c:r=c.get(f"{_base(cfg.environment)}/v2/nfe/{row.provider_ref}",auth=(token,""))
    data=r.json() if "application/json" in r.headers.get("content-type","") else {"message":r.text[:2000]}
    if r.status_code>=400:raise HTTPException(r.status_code if r.status_code<500 else 502,str(data.get("mensagem") or data.get("message") or data)[:900])
    _update_provider_fields(row,data);db.commit();db.refresh(row);return serialize(row)

@router.post("/{doc_id}/cancel")
def cancel_document(doc_id:int,data:CancelIn,db:Session=Depends(get_db),user=Depends(active_user)):
    reason=data.justification.strip()
    if len(reason)<15 or len(reason)>255:raise HTTPException(400,"A justificativa deve ter entre 15 e 255 caracteres")
    row=db.query(FiscalDocument).filter(FiscalDocument.id==doc_id,FiscalDocument.company_id==user.company_id).first();cfg=_config(db,user.company_id,False);token=_token(cfg)
    if not row:raise HTTPException(404,"Documento fiscal não encontrado")
    if row.status!="autorizada":raise HTTPException(400,"Somente NF-e autorizada pode ser cancelada")
    with httpx.Client(timeout=60) as c:r=c.request("DELETE",f"{_base(cfg.environment)}/v2/nfe/{row.provider_ref}",json={"justificativa":reason},auth=(token,""))
    data=r.json() if "application/json" in r.headers.get("content-type","") else {"message":r.text[:2000]}
    if r.status_code>=400:raise HTTPException(400,str(data.get("mensagem") or data.get("message") or data)[:900])
    _update_provider_fields(row,data);row.status="cancelada";db.commit();db.refresh(row);return serialize(row)
