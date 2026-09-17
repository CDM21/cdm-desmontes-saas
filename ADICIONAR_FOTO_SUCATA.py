from pathlib import Path
import subprocess
import sys
import traceback

ENDPOINT = '@router.post("/{vehicle_id}/photo")\ndef upload_vehicle_photo(vehicle_id:int, file:UploadFile=File(...), db:Session=Depends(get_db), user=Depends(require_roles("owner","admin","manager","stock"))):\n    vehicle=db.query(Vehicle).filter(Vehicle.id==vehicle_id, Vehicle.company_id==user.company_id).first()\n    if not vehicle:\n        raise HTTPException(404,"Veículo não encontrado")\n    content_type=(file.content_type or "").lower()\n    allowed={"image/jpeg":".jpg","image/jpg":".jpg","image/png":".png","image/webp":".webp"}\n    if content_type not in allowed:\n        raise HTTPException(400,"Envie uma imagem JPG, PNG ou WEBP")\n    ext=allowed[content_type]\n    filename=f"vehicle_{vehicle.id}_{uuid4().hex}{ext}"\n    target=VEHICLE_UPLOAD_DIR / filename\n    with target.open("wb") as buffer:\n        shutil.copyfileobj(file.file, buffer)\n    vehicle.photo_url=f"/uploads/vehicles/{filename}"\n    db.commit()\n    db.refresh(vehicle)\n    return {"ok":True,"photo_url":vehicle.photo_url,"vehicle_id":vehicle.id}\n\n'
OLD_ADD = " async function add(){\n  if(saving)return\n  if(!form.brand){notice('Selecione a marca do veículo');return}\n  if(!form.model){notice('Selecione ou informe o modelo do veículo');return}\n  setSaving(true)\n  try{\n   await api.post('/vehicles',{...form,year:form.year?Number(form.year):null,acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)})\n   setForm({...empty,year:new Date().getFullYear()})\n   await refresh()\n   notice('Sucata cadastrada com sucesso')\n  }catch(e){\n   const detail=e.response?.data?.detail\n   const msg=typeof detail==='string'?detail:(Array.isArray(detail)?detail.map(x=>x.msg).filter(Boolean).join(' · '):'')\n   notice(msg||erroPt(detail)||`Erro ao cadastrar sucata${e.response?.status?` (HTTP ${e.response.status})`:''}`)\n  }finally{setSaving(false)}\n }"
NEW_ADD = " async function add(){\n  if(saving)return\n  if(!form.brand){notice('Selecione a marca do veículo');return}\n  if(!form.model){notice('Selecione ou informe o modelo do veículo');return}\n  setSaving(true)\n  try{\n   const created=await api.post('/vehicles',{...form,year:form.year?Number(form.year):null,acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)})\n   if(photoFile&&created?.data?.id){\n    const fd=new FormData()\n    fd.append('file',photoFile)\n    await api.post(`/vehicles/${created.data.id}/photo`,fd,{headers:{'Content-Type':'multipart/form-data'}})\n   }\n   setForm({...empty,year:new Date().getFullYear()})\n   setPhotoFile(null)\n   setPhotoPreview('')\n   await refresh()\n   notice(photoFile?'Sucata e foto cadastradas com sucesso':'Sucata cadastrada com sucesso')\n  }catch(e){\n   const detail=e.response?.data?.detail\n   const msg=typeof detail==='string'?detail:(Array.isArray(detail)?detail.map(x=>x.msg).filter(Boolean).join(' · '):'')\n   notice(msg||erroPt(detail)||`Erro ao cadastrar sucata${e.response?.status?` (HTTP ${e.response.status})`:''}`)\n  }finally{setSaving(false)}\n }"
BUTTON_NEW = '<div><small>Foto principal da sucata</small><input type="file" accept="image/*" onChange={e=>{const f=e.target.files?.[0]||null;setPhotoFile(f);setPhotoPreview(f?URL.createObjectURL(f):\'\')}} /></div>{photoPreview&&<div style={{marginTop:8}}><img src={photoPreview} alt="Prévia da sucata" style={{width:120,height:90,objectFit:\'cover\',borderRadius:10,border:\'1px solid var(--border)\'}} /></div>}<button className="primary" disabled={saving} onClick={add}>{saving?\'Salvando...\':\'+ Cadastrar veículo\'}</button>'

class PatchError(RuntimeError):
    pass

def run(cmd, cwd=None):
    print(">", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def find_project():
    here = Path.cwd()
    candidates = [here / "CDM_Desmontes_ERP_SaaS_Online_V4", here]
    for base in candidates:
        if (base / "backend/app/main.py").exists() and (base / "backend/app/models.py").exists() and (base / "backend/app/routers/vehicles.py").exists() and (base / "frontend/src/main.jsx").exists():
            return base
    raise PatchError("Projeto não encontrado. Rode este arquivo dentro de C:\\CDM_DEPLOY.")

def main():
    base = find_project()
    main_py = base / "backend/app/main.py"
    models_py = base / "backend/app/models.py"
    vehicles_py = base / "backend/app/routers/vehicles.py"
    main_jsx = base / "frontend/src/main.jsx"

    original_main = main_py.read_text(encoding="utf-8")
    original_models = models_py.read_text(encoding="utf-8")
    original_vehicles = vehicles_py.read_text(encoding="utf-8")
    original_jsx = main_jsx.read_text(encoding="utf-8")

    try:
        print("Aplicando suporte a foto da sucata...")

        # models.py
        text = original_models
        if "photo_url = Column(String(500), default='')" not in text and 'photo_url = Column(String(500), default="")' not in text:
            anchor = "    color = Column(String(40), default='')\n"
            if anchor not in text:
                anchor = '    color = Column(String(40), default="")\n'
            if anchor not in text:
                raise PatchError("Não encontrei o ponto para inserir photo_url em models.py.")
            text = text.replace(anchor, anchor + "    photo_url = Column(String(500), default='')\n", 1)
        models_py.write_text(text, encoding="utf-8")

        # main.py
        text = original_main
        if 'photo_url' not in text:
            anchor = '"color":"VARCHAR(40) DEFAULT \'\',\n'
            if anchor not in text:
                anchor = '"color":"VARCHAR(40) DEFAULT \'\',\r\n'
            if anchor in text and '"vehicles":{' in text:
                text = text.replace(anchor, anchor + '            "photo_url":"VARCHAR(500) DEFAULT \'\',\n', 1)
            else:
                raise PatchError("Não encontrei o bloco vehicles em main.py para inserir photo_url.")

        if "app.mount('/uploads'" not in text and 'app.mount("/uploads"' not in text:
            if "from pathlib import Path" not in text:
                if "from fastapi import FastAPI\n" in text:
                    text = text.replace("from fastapi import FastAPI\n", "from fastapi import FastAPI\nfrom pathlib import Path\n", 1)
                elif "from fastapi import FastAPI\r\n" in text:
                    text = text.replace("from fastapi import FastAPI\r\n", "from fastapi import FastAPI\r\nfrom pathlib import Path\r\n", 1)

            if "from fastapi.staticfiles import StaticFiles" not in text:
                if "from fastapi.middleware.cors import CORSMiddleware\n" in text:
                    text = text.replace("from fastapi.middleware.cors import CORSMiddleware\n", "from fastapi.middleware.cors import CORSMiddleware\nfrom fastapi.staticfiles import StaticFiles\n", 1)
                elif "from fastapi.middleware.cors import CORSMiddleware\r\n" in text:
                    text = text.replace("from fastapi.middleware.cors import CORSMiddleware\r\n", "from fastapi.middleware.cors import CORSMiddleware\r\nfrom fastapi.staticfiles import StaticFiles\r\n", 1)

            if "UPLOADS_DIR = Path(__file__).resolve().parent.parent / 'uploads'" not in text:
                app_marker = "app = FastAPI("
                pos = text.find(app_marker)
                if pos < 0:
                    raise PatchError("Não encontrei a criação do app em main.py.")
                close = text.find(")\n", pos)
                if close < 0:
                    close = text.find(")\r\n", pos)
                if close < 0:
                    raise PatchError("Não consegui localizar o fechamento do FastAPI em main.py.")
                text = text[:close+2] + "UPLOADS_DIR = Path(__file__).resolve().parent.parent / 'uploads'\nUPLOADS_DIR.mkdir(parents=True, exist_ok=True)\n" + text[close+2:]

            if "app.mount('/uploads', StaticFiles(directory=str(UPLOADS_DIR)), name='uploads')" not in text:
                anchor = "app.include_router("
                pos = text.find(anchor)
                if pos < 0:
                    raise PatchError("Não encontrei onde montar /uploads em main.py.")
                text = text[:pos] + "app.mount('/uploads', StaticFiles(directory=str(UPLOADS_DIR)), name='uploads')\n" + text[pos:]

        main_py.write_text(text, encoding="utf-8")

        # vehicles.py
        text = original_vehicles
        if "def upload_vehicle_photo(" not in text:
            if "from fastapi import APIRouter, Depends, HTTPException\n" in text:
                text = text.replace("from fastapi import APIRouter, Depends, HTTPException\n", "from fastapi import APIRouter, Depends, HTTPException, UploadFile, File\n", 1)
            elif "from fastapi import APIRouter, Depends, HTTPException\r\n" in text:
                text = text.replace("from fastapi import APIRouter, Depends, HTTPException\r\n", "from fastapi import APIRouter, Depends, HTTPException, UploadFile, File\r\n", 1)
            if "from pathlib import Path" not in text:
                text = "from pathlib import Path\nfrom uuid import uuid4\nimport shutil\n" + text
            if "VEHICLE_UPLOAD_DIR" not in text:
                text = text.replace("router = APIRouter()\n", "router = APIRouter()\n\nVEHICLE_UPLOAD_DIR = Path(__file__).resolve().parents[2] / 'uploads' / 'vehicles'\nVEHICLE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)\n\n", 1)
            anchor = '@router.get("")'
            if anchor in text:
                text = text.replace(anchor, ENDPOINT + anchor, 1)
            else:
                text += "\n" + ENDPOINT
        vehicles_py.write_text(text, encoding="utf-8")

        # main.jsx
        text = original_jsx
        state_anchor = "const [form,setForm]=useState(empty),[overview,setOverview]=useState(null),[search,setSearch]=useState(''),[editVehicle,setEditVehicle]=useState(null),[saving,setSaving]=useState(false)"
        if "setPhotoFile" not in text:
            if state_anchor not in text:
                raise PatchError("Não encontrei os estados da tela de sucatas em main.jsx.")
            text = text.replace(state_anchor, state_anchor + ",[photoFile,setPhotoFile]=useState(null),[photoPreview,setPhotoPreview]=useState('')", 1)

        if OLD_ADD in text:
            text = text.replace(OLD_ADD, NEW_ADD, 1)
        elif "photoFile&&created?.data?.id" not in text:
            raise PatchError("Não encontrei a função add da tela de sucatas para incluir upload da foto.")

        button_old = """<button className="primary" disabled={saving} onClick={add}>{saving?'Salvando...':'+ Cadastrar veículo'}</button>"""
        if button_old in text and "Foto principal da sucata" not in text:
            text = text.replace(button_old, BUTTON_NEW, 1)

        list_old = """<b>{[v.brand,v.model,v.year].filter(Boolean).join(' ')||`Veículo #${v.id}`}</b>"""
        list_new = """<div style={{display:'flex',alignItems:'center',gap:10}}>{v.photo_url&&<img src={v.photo_url} alt="Sucata" style={{width:52,height:40,objectFit:'cover',borderRadius:8,border:'1px solid var(--border)'}} />}<b>{[v.brand,v.model,v.year].filter(Boolean).join(' ')||`Veículo #${v.id}`}</b></div>"""
        if list_old in text and 'alt="Sucata"' not in text:
            text = text.replace(list_old, list_new, 1)

        overview_old = """<div className="vehicleOverviewHero">"""
        overview_new = """<div className="vehicleOverviewHero">{overview?.vehicle?.photo_url&&<img src={overview.vehicle.photo_url} alt="Foto da sucata" style={{width:140,height:100,objectFit:'cover',borderRadius:12,border:'1px solid var(--border)',marginBottom:12}} />}"""
        if overview_old in text and 'alt="Foto da sucata"' not in text:
            text = text.replace(overview_old, overview_new, 1)

        main_jsx.write_text(text, encoding="utf-8")

        print("\nValidando backend...")
        run([sys.executable, "-m", "py_compile", str(main_py), str(models_py), str(vehicles_py)], cwd=base)

        print("\nValidando frontend...")
        run(["npm", "run", "build"], cwd=base / "frontend")

        print("\n==============================================")
        print("FOTO DA SUCATA APLICADA E VALIDADA.")
        print("==============================================")
        print("Agora rode:")
        print("git add -A")
        print('git commit -m "Adiciona foto principal no cadastro de sucatas"')
        print("git push")

    except Exception as exc:
        main_py.write_text(original_main, encoding="utf-8")
        models_py.write_text(original_models, encoding="utf-8")
        vehicles_py.write_text(original_vehicles, encoding="utf-8")
        main_jsx.write_text(original_jsx, encoding="utf-8")
        print("\nERRO:", exc)
        print("Os arquivos foram restaurados.")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
