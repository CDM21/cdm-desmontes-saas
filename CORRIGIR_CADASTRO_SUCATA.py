from pathlib import Path
import shutil
import subprocess
import sys
import traceback

OLD_MAIN = '        "users":{"token_version":"INTEGER DEFAULT 0","last_login_at":"TIMESTAMP NULL"},\n        "products":'
NEW_MAIN = '        "users":{"token_version":"INTEGER DEFAULT 0","last_login_at":"TIMESTAMP NULL"},\n        "vehicles":{\n            "plate":"VARCHAR(20) DEFAULT \'\'",\n            "vin":"VARCHAR(80) DEFAULT \'\'",\n            "renavam":"VARCHAR(40) DEFAULT \'\'",\n            "brand":"VARCHAR(80) DEFAULT \'\'",\n            "model":"VARCHAR(120) DEFAULT \'\'",\n            "year":"INTEGER NULL",\n            "fuel":"VARCHAR(30) DEFAULT \'\'",\n            "transmission":"VARCHAR(30) DEFAULT \'\'",\n            "color":"VARCHAR(40) DEFAULT \'\'",\n            "acquisition_value":"FLOAT DEFAULT 0",\n            "other_costs":"FLOAT DEFAULT 0",\n            "status":"VARCHAR(30) DEFAULT \'received\'",\n            "created_at":"TIMESTAMP NULL"\n        },\n        "products":'
OLD_CREATE = '@router.post("")\ndef create_vehicle(data:VehicleIn, db:Session=Depends(get_db), user=Depends(require_roles("owner","admin","manager","stock"))):\n    v=Vehicle(company_id=user.company_id,**data.model_dump()); db.add(v); db.commit(); db.refresh(v); return v\n'
NEW_CREATE = '@router.post("")\ndef create_vehicle(data:VehicleIn, db:Session=Depends(get_db), user=Depends(require_roles("owner","admin","manager","stock"))):\n    payload=data.model_dump()\n    payload["plate"]=(payload.get("plate") or "").strip().upper()\n    payload["vin"]=(payload.get("vin") or "").strip().upper()\n    payload["renavam"]=(payload.get("renavam") or "").strip()\n    payload["brand"]=(payload.get("brand") or "").strip()\n    payload["model"]=(payload.get("model") or "").strip()\n    payload["fuel"]=(payload.get("fuel") or "").strip()\n    payload["transmission"]=(payload.get("transmission") or "").strip()\n    payload["color"]=(payload.get("color") or "").strip()\n    payload["acquisition_value"]=round(float(payload.get("acquisition_value") or 0),2)\n    payload["other_costs"]=round(float(payload.get("other_costs") or 0),2)\n\n    if not payload["brand"]:\n        raise HTTPException(400,"Selecione a marca do veículo")\n    if not payload["model"]:\n        raise HTTPException(400,"Selecione ou informe o modelo do veículo")\n    year=payload.get("year")\n    if year is not None and (int(year)<1971 or int(year)>datetime.utcnow().year+1):\n        raise HTTPException(400,"Ano do veículo inválido")\n\n    try:\n        v=Vehicle(company_id=user.company_id,**payload)\n        db.add(v)\n        db.commit()\n        db.refresh(v)\n        return v\n    except SQLAlchemyError as exc:\n        db.rollback()\n        message=str(getattr(exc,"orig",exc))\n        if "other_costs" in message.lower() or "column" in message.lower():\n            raise HTTPException(500,"O banco de dados do cadastro de sucatas precisa ser atualizado. Aguarde o novo deploy e tente novamente.")\n        raise HTTPException(500,"Não foi possível salvar a sucata no banco de dados")\n'
OLD_STATES = "const [form,setForm]=useState(empty),[overview,setOverview]=useState(null),[search,setSearch]=useState(''),[editVehicle,setEditVehicle]=useState(null)"
NEW_STATES = "const [form,setForm]=useState(empty),[overview,setOverview]=useState(null),[search,setSearch]=useState(''),[editVehicle,setEditVehicle]=useState(null),[saving,setSaving]=useState(false)"
OLD_ADD = " async function add(){try{await api.post('/vehicles',{...form,acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)});setForm({...empty,year:new Date().getFullYear()});await refresh();notice('Sucata cadastrada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao cadastrar')}}"
NEW_ADD = " async function add(){\n  if(saving)return\n  if(!form.brand){notice('Selecione a marca do veículo');return}\n  if(!form.model){notice('Selecione ou informe o modelo do veículo');return}\n  setSaving(true)\n  try{\n   await api.post('/vehicles',{...form,year:form.year?Number(form.year):null,acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)})\n   setForm({...empty,year:new Date().getFullYear()})\n   await refresh()\n   notice('Sucata cadastrada com sucesso')\n  }catch(e){\n   const detail=e.response?.data?.detail\n   const msg=typeof detail==='string'?detail:(Array.isArray(detail)?detail.map(x=>x.msg).filter(Boolean).join(' · '):'')\n   notice(msg||erroPt(detail)||`Erro ao cadastrar sucata${e.response?.status?` (HTTP ${e.response.status})`:''}`)\n  }finally{setSaving(false)}\n }"
OLD_BUTTON = '<button className="primary" onClick={add}>+ Cadastrar veículo</button>'
NEW_BUTTON = '<button className="primary" disabled={saving} onClick={add}>{saving?\'Salvando...\':\'+ Cadastrar veículo\'}</button>'

class PatchError(RuntimeError):
    pass

def find_project():
    here = Path.cwd()
    candidates = [here / "CDM_Desmontes_ERP_SaaS_Online_V4", here]
    for base in candidates:
        if (base / "backend/app/main.py").exists() and (base / "backend/app/routers/vehicles.py").exists() and (base / "frontend/src/main.jsx").exists():
            return base
    raise PatchError("Projeto não encontrado. Rode este arquivo dentro de C:\\CDM_DEPLOY.")

def run(cmd, cwd=None):
    print(">", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def main():
    base = find_project()
    main_py = base / "backend/app/main.py"
    vehicles_py = base / "backend/app/routers/vehicles.py"
    main_jsx = base / "frontend/src/main.jsx"

    original_main = main_py.read_text(encoding="utf-8")
    original_vehicles = vehicles_py.read_text(encoding="utf-8")
    original_jsx = main_jsx.read_text(encoding="utf-8")

    try:
        print("Aplicando correção do cadastro de sucatas...")

        text = original_main
        if OLD_MAIN not in text:
            raise PatchError("Não encontrei o bloco de migração em main.py.")
        text = text.replace(OLD_MAIN, NEW_MAIN, 1)
        main_py.write_text(text, encoding="utf-8")

        text = original_vehicles
        if "from sqlalchemy.exc import SQLAlchemyError" not in text:
            text = text.replace("from sqlalchemy.orm import Session\n", "from sqlalchemy.orm import Session\nfrom sqlalchemy.exc import SQLAlchemyError\n", 1)
        if "from datetime import datetime" not in text:
            text = text.replace("from fastapi import APIRouter, Depends, HTTPException\n", "from fastapi import APIRouter, Depends, HTTPException\nfrom datetime import datetime\n", 1)
        if OLD_CREATE not in text:
            raise PatchError("Não encontrei a função create_vehicle esperada.")
        text = text.replace(OLD_CREATE, NEW_CREATE, 1)
        vehicles_py.write_text(text, encoding="utf-8")

        text = original_jsx
        if OLD_STATES in text:
            text = text.replace(OLD_STATES, NEW_STATES, 1)
        elif "saving,setSaving" not in text:
            raise PatchError("Não encontrei os estados do cadastro de sucatas.")

        if OLD_ADD not in text:
            raise PatchError("Não encontrei a função add do cadastro de sucatas.")
        text = text.replace(OLD_ADD, NEW_ADD, 1)

        if OLD_BUTTON not in text:
            raise PatchError("Não encontrei o botão Cadastrar veículo.")
        text = text.replace(OLD_BUTTON, NEW_BUTTON, 1)
        main_jsx.write_text(text, encoding="utf-8")

        print("\nValidando backend...")
        run([sys.executable, "-m", "py_compile", str(main_py), str(vehicles_py)], cwd=base)

        git = shutil.which("git")
        if git:
            print("\nValidando diff...")
            run([git, "diff", "--check"], cwd=base.parent)

        npm = shutil.which("npm")
        if npm and (base / "frontend/node_modules").exists():
            print("\nValidando frontend...")
            run([npm, "run", "build"], cwd=base / "frontend")
        else:
            print("\nnode_modules não encontrado; build do frontend não executado.")

        print("\n==============================================")
        print("CORREÇÃO DO CADASTRO DE SUCATAS APLICADA E VALIDADA.")
        print("==============================================")
        print("Agora rode:")
        print("git add -A")
        print('git commit -m "Corrige cadastro de sucatas no banco e frontend"')
        print("git push")

    except Exception as exc:
        main_py.write_text(original_main, encoding="utf-8")
        vehicles_py.write_text(original_vehicles, encoding="utf-8")
        main_jsx.write_text(original_jsx, encoding="utf-8")
        print("\nERRO:", exc)
        print("Os arquivos foram restaurados.")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
