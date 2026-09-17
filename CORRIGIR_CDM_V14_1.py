from pathlib import Path
import shutil
import subprocess
import sys
import traceback

NEW_SYNC = 'def _sync_founders(db: Session):\n    # Regra determinística: os 10 primeiros clientes reais são fundadores.\n    # A empresa usada pelo administrador da plataforma é excluída.\n    admin_company_ids = _platform_admin_company_ids(db)\n    companies = db.query(Company).order_by(\n        Company.created_at.asc(), Company.id.asc()\n    ).all()\n    eligible = [c for c in companies if c.id not in admin_company_ids][:FOUNDER_LIMIT]\n    rows = []\n    for slot, company in enumerate(eligible, start=1):\n        rows.append({\n            "company_id": int(company.id),\n            "slot": slot,\n            "assigned_at": getattr(company, "created_at", None),\n        })\n    return rows\n'
PING = '_ensure_v14_tables()\n\n@router.get("/ping")\ndef v14_ping():\n    return {\n        "ok": True,\n        "version": "14.1",\n        "founder_limit": FOUNDER_LIMIT,\n        "monthly_price": _money_env("CDM_MONTHLY_PRICE", DEFAULT_MONTHLY_PRICE),\n        "implementation_fee": _money_env("CDM_IMPLEMENTATION_FEE", DEFAULT_IMPLEMENTATION_FEE),\n    }\n'
OLD_LOAD = "     const [r,readinessR,foundersR]=await Promise.all([\n       api.get('/admin/dashboard-v2'),\n       api.get('/v14/admin/platform-readiness').catch(()=>({data:null})),\n       api.get('/v14/admin/founders').catch(()=>({data:null}))\n     ])\n     setData(r.data||{})\n     setReadiness(readinessR.data||null)\n     setFounders(foundersR.data||null)\n     setLastUpdate(new Date())"
NEW_LOAD = "     const r=await api.get('/admin/dashboard-v2')\n     setData(r.data||{})\n     const [readinessR,foundersR]=await Promise.all([\n       api.get('/v14/admin/platform-readiness')\n         .then(x=>({ok:true,data:x.data}))\n         .catch(e=>({ok:false,error:`HTTP ${e.response?.status||'-'} - ${erroPt(e.response?.data?.detail)||e.message||'Falha na API V14'}`})),\n       api.get('/v14/admin/founders')\n         .then(x=>({ok:true,data:x.data}))\n         .catch(e=>({ok:false,error:`HTTP ${e.response?.status||'-'} - ${erroPt(e.response?.data?.detail)||e.message||'Falha na API V14'}`}))\n     ])\n     setReadiness(readinessR.ok?readinessR.data:null)\n     setFounders(foundersR.ok?foundersR.data:null)\n     setV14Errors({\n       readiness:readinessR.ok?'':readinessR.error,\n       founders:foundersR.ok?'':foundersR.error\n     })\n     setLastUpdate(new Date())"
FOUNDER_BLOCK = '     {section===\'revenue\'&&<section className="ownerCard v14FounderCard">\n       <div className="ownerCardHead">\n         <div><span>PROGRAMA FUNDADORES</span><h3>Regra dos 10 primeiros clientes</h3></div>\n         <span className="pill neutral">{founders?`${founders.assigned||0}/${founders.limit||10} vagas usadas`:\'V14.1\'}</span>\n       </div>\n       <div className="v14FounderStats">\n         <div><small>FUNDADORES</small><b>{founders?.assigned??\'-\'}</b></div>\n         <div><small>VAGAS RESTANTES</small><b>{founders?.remaining??\'-\'}</b></div>\n         <div><small>MENSALIDADE</small><b>{money(founders?.monthly_price||350)}</b></div>\n         <div><small>IMPLANTAÇÃO APÓS 10</small><b>{money(founders?.implementation_fee_after_founders||1500)}</b></div>\n       </div>\n       {founders?.founders?.length>0&&<div className="v14FounderNames">\n         {founders.founders.map(x=><span key={x.company_id}>#{x.slot} · {x.company_name}</span>)}\n       </div>}\n       {v14Errors.founders\n         ?<div className="ownerInfoNote"><b>Diagnóstico da API:</b> {v14Errors.founders}. O bloco permanece visível para facilitar a correção.</div>\n         :<div className="ownerInfoNote">Os 10 primeiros clientes reais ficam isentos da implantação. A partir do 11º cliente, a implantação é cobrada uma única vez, além da mensalidade recorrente.</div>}\n     </section>}\n\n'
DIAG_BLOCK = '     {section===\'system\'&&<section className="ownerCard v14ReadinessCard">\n       <div className="ownerCardHead">\n         <div><span>DIAGNÓSTICO V14.1</span><h3>Segurança, backup e integrações</h3></div>\n         <span className="pill neutral">{readiness?.database?.latency_ms!=null?`${readiness.database.latency_ms} ms DB`:\'Verificando API\'}</span>\n       </div>\n       {v14Errors.readiness&&<div className="ownerInfoNote"><b>API V14:</b> {v14Errors.readiness}. Agora o erro não fica mais escondido.</div>}\n       <div className="v14ReadinessGrid">\n         <div><small>BANCO DE DADOS</small><b className={readiness?.database?.online?\'v14ReadyYes\':\'v14ReadyNo\'}>{readiness?readiness.database?.online?\'Online\':\'Atenção\':\'Aguardando\'}</b></div>\n         <div><small>AUDITORIA</small><b>{readiness?`${readiness.audit?.events||0} eventos`:\'-\'}</b></div>\n         <div><small>BACKUP</small><b>{readiness?.backup?.last_download_at?new Date(readiness.backup.last_download_at).toLocaleDateString(\'pt-BR\'):\'Ainda não confirmado\'}</b></div>\n         <div><small>MERCADO PAGO</small><b className={readiness?.billing?.mercadopago_configured?\'v14ReadyYes\':\'v14ReadyNo\'}>{readiness?.billing?.mercadopago_configured?\'Credencial pronta\':\'Aguardando credencial\'}</b></div>\n         <div><small>WEBHOOK SEGURO</small><b className={readiness?.security?.billing_webhook_secret?\'v14ReadyYes\':\'v14ReadyNo\'}>{readiness?.security?.billing_webhook_secret?\'Configurado\':\'Pendente\'}</b></div>\n         <div><small>CRIPTOGRAFIA</small><b className={readiness?.security?.app_encryption_key?\'v14ReadyYes\':\'v14ReadyNo\'}>{readiness?.security?.app_encryption_key?\'Configurada\':\'Revisar ambiente\'}</b></div>\n         <div><small>MARKETPLACES ATIVOS</small><b>{readiness?.integrations?.active_marketplace_connections??\'-\'}</b></div>\n         <div><small>FUNDADORES</small><b>{readiness?`${readiness.founders?.assigned||0}/${readiness.founders?.limit||10}`:\'-/10\'}</b></div>\n       </div>\n     </section>}\n\n'

class PatchError(RuntimeError):
    pass

def find_project():
    here = Path.cwd()
    candidates = [here / "CDM_Desmontes_ERP_SaaS_Online_V4", here]
    for base in candidates:
        if (base / "frontend/src/main.jsx").exists() and (base / "backend/app/routers/platform_v14.py").exists():
            return base
    raise PatchError("Projeto não encontrado. Rode dentro de C:\\CDM_DEPLOY.")

def run(cmd, cwd=None):
    print(">", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def main():
    base = find_project()
    main_jsx = base / "frontend/src/main.jsx"
    v14_py = base / "backend/app/routers/platform_v14.py"
    original_jsx = main_jsx.read_text(encoding="utf-8")
    original_py = v14_py.read_text(encoding="utf-8")

    backup_dir = base / "_backup_v14_1"
    backup_dir.mkdir(exist_ok=True)
    (backup_dir / "main.jsx").write_text(original_jsx, encoding="utf-8")
    (backup_dir / "platform_v14.py").write_text(original_py, encoding="utf-8")

    try:
        print("Aplicando CDM V14.1...")

        py = original_py
        start = py.find("def _sync_founders(db: Session):")
        end = py.find("\ndef _founder_for_company", start)
        if start < 0 or end < 0:
            raise PatchError("Não encontrei _sync_founders.")
        py = py[:start] + NEW_SYNC + py[end:]

        if '@router.get("/ping")' not in py:
            anchor = "_ensure_v14_tables()\n"
            if anchor not in py:
                raise PatchError("Não encontrei inicialização V14.")
            py = py.replace(anchor, PING, 1)

        v14_py.write_text(py, encoding="utf-8")

        jsx = original_jsx

        if "v14Errors" not in jsx:
            anchor = " const [founders,setFounders]=useState(null)\n"
            if anchor not in jsx:
                raise PatchError("Não encontrei estado founders.")
            jsx = jsx.replace(
                anchor,
                anchor + " const [v14Errors,setV14Errors]=useState({founders:'',readiness:''})\n",
                1,
            )

        if OLD_LOAD in jsx:
            jsx = jsx.replace(OLD_LOAD, NEW_LOAD, 1)
        elif "setV14Errors({" not in jsx:
            raise PatchError("Não encontrei carregamento V14.")

        founder_start = jsx.find("     {section==='revenue'&&founders&&<section className=\"ownerCard v14FounderCard\">")
        if founder_start < 0:
            founder_start = jsx.find("     {section==='revenue'&&<section className=\"ownerCard v14FounderCard\">")
        founder_next = jsx.find("     {section==='system'&&<>", founder_start)
        if founder_start < 0 or founder_next < 0:
            raise PatchError("Não encontrei Programa Fundadores.")
        jsx = jsx[:founder_start] + FOUNDER_BLOCK + jsx[founder_next:]

        diag_start = jsx.find("     {section==='system'&&readiness&&<section className=\"ownerCard v14ReadinessCard\">")
        if diag_start < 0:
            diag_start = jsx.find("     {section==='system'&&<section className=\"ownerCard v14ReadinessCard\">")
        toast_pos = jsx.find("     {toast&&<div className=\"toast\">", diag_start)
        if diag_start < 0 or toast_pos < 0:
            raise PatchError("Não encontrei Diagnóstico V14.")
        jsx = jsx[:diag_start] + DIAG_BLOCK + jsx[toast_pos:]

        main_jsx.write_text(jsx, encoding="utf-8")

        print("\nValidando backend...")
        run([sys.executable, "-m", "py_compile", str(v14_py)], cwd=base)

        git = shutil.which("git")
        if git:
            print("\nValidando diff...")
            run([git, "diff", "--check"], cwd=base)

        npm = shutil.which("npm")
        if npm and (base / "frontend/node_modules").exists():
            print("\nValidando frontend...")
            run([npm, "run", "build"], cwd=base / "frontend")
        else:
            print("\nnode_modules não encontrado; build do frontend não executado.")

        print("\n==============================================")
        print("CDM V14.1 APLICADA E VALIDADA.")
        print("==============================================")
        print("Agora rode:")
        print("git add .")
        print('git commit -m "V14.1 corrige fundadores e diagnostico"')
        print("git push")

    except Exception as exc:
        print("\nERRO:", exc)
        print("Restaurando arquivos anteriores...")
        main_jsx.write_text(original_jsx, encoding="utf-8")
        v14_py.write_text(original_py, encoding="utf-8")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
