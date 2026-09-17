from pathlib import Path
import shutil
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROUTER_CODE = (HERE / "payload_platform_v14.py").read_text(encoding="utf-8")
SMART_COMPONENT = (HERE / "payload_smart_dismantling.jsx").read_text(encoding="utf-8")
CSS_V14 = (HERE / "payload_v14.css").read_text(encoding="utf-8")

class PatchError(RuntimeError):
    pass

def replace_once(text, old, new, label):
    if old not in text:
        raise PatchError(f"Âncora não encontrada: {label}")
    return text.replace(old, new, 1)

def run(cmd, cwd=None):
    print(">", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def find_project():
    here = Path.cwd()
    candidates = [
        here / "CDM_Desmontes_ERP_SaaS_Online_V4",
        here,
    ]
    for base in candidates:
        if (base / "backend/app/main.py").exists() and (base / "frontend/src/main.jsx").exists():
            return base
    raise PatchError(
        "Projeto não encontrado. Rode este arquivo dentro de C:\\CDM_DEPLOY "
        "ou dentro da pasta CDM_Desmontes_ERP_SaaS_Online_V4."
    )

def main():
    base = find_project()
    main_py = base / "backend/app/main.py"
    router_py = base / "backend/app/routers/platform_v14.py"
    env_example = base / "backend/.env.example"
    main_jsx = base / "frontend/src/main.jsx"
    styles_css = base / "frontend/src/styles.css"

    tracked = [main_py, env_example, main_jsx, styles_css]
    originals = {p: p.read_text(encoding="utf-8") for p in tracked}
    router_original = router_py.read_text(encoding="utf-8") if router_py.exists() else None

    print(f"Projeto encontrado: {base}")
    print("Aplicando CDM V14...")

    try:
        router_py.write_text(ROUTER_CODE, encoding="utf-8")

        # backend/app/main.py
        text = originals[main_py]
        old_import = (
            "from .routers import auth, vehicles, products, sales, finance, stock, "
            "marketplaces, company, catalog, billing, vehicle_catalog, admin, "
            "notifications, fiscal, intelligence"
        )
        if "platform_v14" not in text:
            text = replace_once(
                text,
                old_import,
                old_import + ", platform_v14",
                "import platform_v14",
            )
        if 'prefix="/api/v14"' not in text:
            anchor = 'app.include_router(intelligence.router, prefix="/api/intelligence", tags=["Inteligência CDM"])'
            text = replace_once(
                text,
                anchor,
                anchor + '\napp.include_router(platform_v14.router, prefix="/api/v14", tags=["CDM V14"])',
                "include_router V14",
            )
        text = text.replace('version="12.0.0"', 'version="14.0.0"')
        text = text.replace('"version":"12.0.0"', '"version":"14.0.0"')
        main_py.write_text(text, encoding="utf-8")

        # backend/.env.example
        env = originals[env_example]
        if "CDM_IMPLEMENTATION_FEE=" not in env:
            env = env.replace(
                "CDM_MONTHLY_PRICE=350",
                "CDM_MONTHLY_PRICE=350\n"
                "# Taxa única cobrada a partir do 11º cliente\n"
                "CDM_IMPLEMENTATION_FEE=1500",
                1,
            )
        env_example.write_text(env, encoding="utf-8")

        # frontend/src/main.jsx
        jsx = originals[main_jsx]
        if "function SmartDismantling(" not in jsx:
            jsx = replace_once(
                jsx,
                "function OwnerPortal({session,onPreview}){",
                SMART_COMPONENT + "\n\nfunction OwnerPortal({session,onPreview}){",
                "componente Desmonte Inteligente",
            )

        owner_start = jsx.index("function OwnerPortal({session,onPreview}){")
        owner_end = jsx.index("// CDM MOBILE NAV V2", owner_start)
        before = jsx[:owner_start]
        owner = jsx[owner_start:owner_end]
        after = jsx[owner_end:]

        if "setReadiness" not in owner:
            owner = replace_once(
                owner,
                " const [lastUpdate,setLastUpdate]=useState(null)\n"
                " const s=data.summary||{}, rows=data.companies||[], logs=data.recent_logs||[]",
                " const [lastUpdate,setLastUpdate]=useState(null)\n"
                " const [readiness,setReadiness]=useState(null)\n"
                " const [founders,setFounders]=useState(null)\n"
                " const s=data.summary||{}, rows=data.companies||[], logs=data.recent_logs||[]\n"
                " const founderMap=new Map((founders?.founders||[]).map(x=>[Number(x.company_id),Number(x.slot)]))",
                "estados V14 do Portal do Dono",
            )

        if "readinessR" not in owner:
            owner = replace_once(
                owner,
                "     const r=await api.get('/admin/dashboard-v2')\n"
                "     setData(r.data||{})\n"
                "     setLastUpdate(new Date())",
                "     const [r,readinessR,foundersR]=await Promise.all([\n"
                "       api.get('/admin/dashboard-v2'),\n"
                "       api.get('/v14/admin/platform-readiness').catch(()=>({data:null})),\n"
                "       api.get('/v14/admin/founders').catch(()=>({data:null}))\n"
                "     ])\n"
                "     setData(r.data||{})\n"
                "     setReadiness(readinessR.data||null)\n"
                "     setFounders(foundersR.data||null)\n"
                "     setLastUpdate(new Date())",
                "carregamento V14 do Portal do Dono",
            )

        if "Fundador #${founderMap" not in owner:
            owner = replace_once(
                owner,
                "<small>Empresa #{c.id} · criada {c.created_at?new Date(c.created_at).toLocaleDateString('pt-BR'):'—'}</small>",
                "<small>Empresa #{c.id} · criada {c.created_at?new Date(c.created_at).toLocaleDateString('pt-BR'):'—'}{founderMap.has(Number(c.id))?` · Fundador #${founderMap.get(Number(c.id))}`:''}</small>",
                "selo Fundador",
            )

        if "PROGRAMA FUNDADORES" not in owner:
            founder_block = """
     {section==='revenue'&&founders&&<section className="ownerCard v14FounderCard">
       <div className="ownerCardHead"><div><span>PROGRAMA FUNDADORES</span><h3>Regra dos 10 primeiros clientes</h3></div><span className="pill neutral">{founders.assigned||0}/{founders.limit||10} vagas usadas</span></div>
       <div className="v14FounderStats">
         <div><small>FUNDADORES</small><b>{founders.assigned||0}</b></div>
         <div><small>VAGAS RESTANTES</small><b>{founders.remaining||0}</b></div>
         <div><small>MENSALIDADE</small><b>{money(founders.monthly_price||350)}</b></div>
         <div><small>IMPLANTAÇÃO APÓS 10</small><b>{money(founders.implementation_fee_after_founders||1500)}</b></div>
       </div>
       <div className="v14FounderNames">{(founders.founders||[]).map(x=><span key={x.company_id}>#{x.slot} · {x.company_name}</span>)}</div>
       <div className="ownerInfoNote">Os fundadores ficam isentos da implantação. A partir do 11º cliente, o CDM prepara a cobrança única de implantação + a mensalidade recorrente.</div>
     </section>}
"""
            owner = replace_once(
                owner,
                "     {section==='system'&&<>",
                founder_block + "\n     {section==='system'&&<>",
                "painel de fundadores",
            )

        if "DIAGNÓSTICO V14" not in owner:
            readiness_block = """
     {section==='system'&&readiness&&<section className="ownerCard v14ReadinessCard">
       <div className="ownerCardHead"><div><span>DIAGNÓSTICO V14</span><h3>Segurança, backup e integrações</h3></div><span className="pill neutral">{readiness.database?.latency_ms??'—'} ms DB</span></div>
       <div className="v14ReadinessGrid">
         <div><small>BANCO DE DADOS</small><b className={readiness.database?.online?'v14ReadyYes':'v14ReadyNo'}>{readiness.database?.online?'Online':'Atenção'}</b></div>
         <div><small>AUDITORIA</small><b className={readiness.audit?.enabled?'v14ReadyYes':'v14ReadyNo'}>{readiness.audit?.events||0} eventos</b></div>
         <div><small>BACKUP</small><b>{readiness.backup?.last_download_at?new Date(readiness.backup.last_download_at).toLocaleDateString('pt-BR'):'Ainda não baixado'}</b></div>
         <div><small>MERCADO PAGO</small><b className={readiness.billing?.mercadopago_configured?'v14ReadyYes':'v14ReadyNo'}>{readiness.billing?.mercadopago_configured?'Credencial pronta':'Aguardando credencial'}</b></div>
         <div><small>WEBHOOK SEGURO</small><b className={readiness.security?.billing_webhook_secret?'v14ReadyYes':'v14ReadyNo'}>{readiness.security?.billing_webhook_secret?'Configurado':'Pendente'}</b></div>
         <div><small>CRIPTOGRAFIA</small><b className={readiness.security?.app_encryption_key?'v14ReadyYes':'v14ReadyNo'}>{readiness.security?.app_encryption_key?'Configurada':'Revisar ambiente'}</b></div>
         <div><small>MARKETPLACES ATIVOS</small><b>{readiness.integrations?.active_marketplace_connections||0}</b></div>
         <div><small>FUNDADORES</small><b>{readiness.founders?.assigned||0}/{readiness.founders?.limit||10}</b></div>
       </div>
     </section>}
"""
            owner = replace_once(
                owner,
                '     {toast&&<div className="toast">✓ {toast}</div>}',
                readiness_block + '\n     {toast&&<div className="toast">✓ {toast}</div>}',
                "diagnóstico V14",
            )

        main_jsx.write_text(before + owner + after, encoding="utf-8")

        # frontend/src/styles.css
        css = originals[styles_css]
        if "CDM V14 - FUNDADORES + DESMONTE INTELIGENTE + MONITORAMENTO" not in css:
            css = css.rstrip() + "\n\n" + CSS_V14.strip() + "\n"
        styles_css.write_text(css, encoding="utf-8")

        print("\nValidando backend...")
        run([sys.executable, "-m", "py_compile", str(main_py), str(router_py)], cwd=base)

        git = shutil.which("git")
        if git:
            print("\nValidando diff...")
            run([git, "diff", "--check"], cwd=base)

        npm = shutil.which("npm")
        if npm and (base / "frontend/node_modules").exists():
            print("\nValidando frontend com Vite...")
            run([npm, "run", "build"], cwd=base / "frontend")
        else:
            print("\nBuild do frontend não executado automaticamente.")
            print("Se necessário: cd frontend ; npm install ; npm run build")

        print("\n==============================================")
        print("CDM V14 APLICADA E VALIDADA.")
        print("==============================================")
        print("Agora rode:")
        print("git add .")
        print('git commit -m "V14 fundadores desmonte inteligente monitoramento"')
        print("git push")
        print("\nO Render deverá iniciar o deploy após o push.")

    except Exception as exc:
        print("\nERRO durante a aplicação:", exc)
        print("Restaurando arquivos anteriores...")
        for path, content in originals.items():
            path.write_text(content, encoding="utf-8")
        if router_original is None:
            if router_py.exists():
                router_py.unlink()
        else:
            router_py.write_text(router_original, encoding="utf-8")
        print("Arquivos restaurados. Nada da V14 ficou aplicado.")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
