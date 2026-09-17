from pathlib import Path
import subprocess
import sys
import traceback

HELPER = "\nasync function prepareVehiclePhoto(file){\n const src=await new Promise((resolve,reject)=>{\n  const reader=new FileReader()\n  reader.onload=()=>resolve(reader.result)\n  reader.onerror=()=>reject(new Error('Não foi possível ler a foto'))\n  reader.readAsDataURL(file)\n })\n const img=await new Promise((resolve,reject)=>{\n  const el=new Image()\n  el.onload=()=>resolve(el)\n  el.onerror=()=>reject(new Error('Foto inválida'))\n  el.src=src\n })\n const max=1200\n const scale=Math.min(1,max/Math.max(img.width,img.height))\n const width=Math.max(1,Math.round(img.width*scale))\n const height=Math.max(1,Math.round(img.height*scale))\n const canvas=document.createElement('canvas')\n canvas.width=width\n canvas.height=height\n const ctx=canvas.getContext('2d')\n ctx.imageSmoothingEnabled=true\n ctx.imageSmoothingQuality='high'\n ctx.drawImage(img,0,0,width,height)\n return canvas.toDataURL('image/jpeg',0.78)\n}\n\n"
SANITIZE_NEW = '    payload["color"]=(payload.get("color") or "").strip()\n    photo_data=(payload.get("photo_data") or "").strip()\n    if photo_data:\n        if not photo_data.startswith("data:image/"):\n            raise HTTPException(400,"Formato da foto da sucata inválido")\n        if len(photo_data)>1800000:\n            raise HTTPException(400,"A foto da sucata ficou muito grande. Escolha outra imagem.")\n    payload["photo_data"]=photo_data\n'
HANDLER = "\n async function chooseVehiclePhoto(e){\n  const file=e.target.files?.[0]\n  if(!file)return\n  if(!String(file.type||'').startsWith('image/')){notice('Escolha uma imagem válida');return}\n  setPhotoBusy(true)\n  try{\n   const data=await prepareVehiclePhoto(file)\n   if(data.length>1800000){notice('Essa foto ficou muito grande. Escolha outra.');return}\n   setPhotoData(data)\n  }catch(err){notice(err.message||'Não foi possível preparar a foto')}\n  finally{setPhotoBusy(false)}\n }\n"
PHOTO_BLOCK = '<div style={{marginTop:14,display:\'grid\',gap:8}}>\n   <div><small style={{display:\'block\',marginBottom:6,fontWeight:800}}>FOTO PRINCIPAL DA SUCATA</small><input type="file" accept="image/*" capture="environment" onChange={chooseVehiclePhoto}/></div>\n   {photoBusy&&<small>Preparando foto...</small>}\n   {photoData&&<div style={{display:\'flex\',alignItems:\'center\',gap:12}}><img src={photoData} alt="Prévia da sucata" style={{width:150,height:105,objectFit:\'cover\',borderRadius:12,border:\'1px solid var(--border)\'}}/><button type="button" className="ghost" onClick={()=>setPhotoData(\'\')}>Remover foto</button></div>}\n  </div>\n  <button className="primary" disabled={saving||photoBusy} onClick={add}>{saving?\'Salvando...\':photoBusy?\'Preparando foto...\':\'+ Cadastrar veículo\'}</button>'
OLD_IDENTITY = '<div className="vehicleIdentity"><div className="vehicleBadge">#{v.id}</div><div><b>{[v.brand,v.model,v.year].filter(Boolean).join(\' \')||\'Veículo sem identificação\'}</b>'
NEW_IDENTITY = '<div className="vehicleIdentity">{v.photo_data?<img src={v.photo_data} alt="Sucata" style={{width:54,height:42,objectFit:\'cover\',borderRadius:10,border:\'1px solid var(--border)\',flex:\'0 0 auto\'}}/>:<div className="vehicleBadge">#{v.id}</div>}<div><b>{[v.brand,v.model,v.year].filter(Boolean).join(\' \')||\'Veículo sem identificação\'}</b>'
OLD_360 = '<div className="modalHead vehicle360Head"><div><small>VISÃO 360 DO VEÍCULO</small><h2>{[v.brand,v.model,v.year].filter(Boolean).join(\' \')||`Veículo #${v.id}`}</h2><p>{v.plate?`Placa ${v.plate} · `:\'\'}{info?.vehicle?.status_label||statusPt(v.status)}</p></div><button className="iconClose" onClick={onClose}>×</button></div>'
NEW_360 = '<div className="modalHead vehicle360Head"><div style={{display:\'flex\',alignItems:\'center\',gap:14}}>{v.photo_data&&<img src={v.photo_data} alt="Foto da sucata" style={{width:92,height:66,objectFit:\'cover\',borderRadius:12,border:\'1px solid var(--border)\'}}/>}<div><small>VISÃO 360 DO VEÍCULO</small><h2>{[v.brand,v.model,v.year].filter(Boolean).join(\' \')||`Veículo #${v.id}`}</h2><p>{v.plate?`Placa ${v.plate} · `:\'\'}{info?.vehicle?.status_label||statusPt(v.status)}</p></div></div><button className="iconClose" onClick={onClose}>×</button></div>'

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

    originals = {
        main_py: main_py.read_text(encoding="utf-8"),
        models_py: models_py.read_text(encoding="utf-8"),
        vehicles_py: vehicles_py.read_text(encoding="utf-8"),
        main_jsx: main_jsx.read_text(encoding="utf-8"),
    }

    try:
        print("Aplicando foto principal da sucata - V2...")

        # models.py
        text = originals[models_py]
        if "photo_data = Column(Text" not in text:
            anchors = [
                "    color = Column(String(40))\n",
                '    color = Column(String(40), default="")\n',
                "    color = Column(String(40), default='')\n",
            ]
            anchor = next((a for a in anchors if a in text), None)
            if not anchor:
                raise PatchError("Não encontrei a linha color da classe Vehicle em models.py.")
            text = text.replace(anchor, anchor + '    photo_data = Column(Text, default="")\n', 1)
        models_py.write_text(text, encoding="utf-8")

        # main.py migration
        text = originals[main_py]
        if '"photo_data":"TEXT DEFAULT \'\'' not in text:
            anchor = '            "color":"VARCHAR(40) DEFAULT \'\',\n'
            if anchor not in text:
                raise PatchError("Não encontrei o bloco vehicles em main.py.")
            text = text.replace(anchor, anchor + '            "photo_data":"TEXT DEFAULT \'\',\n', 1)
        main_py.write_text(text, encoding="utf-8")

        # vehicles.py
        text = originals[vehicles_py]
        if 'photo_data:str=""' not in text:
            anchor = '    color:str=""\n'
            if anchor not in text:
                raise PatchError("Não encontrei color em VehicleIn.")
            text = text.replace(anchor, anchor + '    photo_data:str=""\n', 1)

        sanitize_anchor = '    payload["color"]=(payload.get("color") or "").strip()\n'
        if 'len(photo_data)>1800000' not in text:
            if sanitize_anchor not in text:
                raise PatchError("Não encontrei o ponto de sanitização do veículo.")
            text = text.replace(sanitize_anchor, SANITIZE_NEW, 1)
        vehicles_py.write_text(text, encoding="utf-8")

        # frontend
        text = originals[main_jsx]

        if "async function prepareVehiclePhoto(file)" not in text:
            anchor = "function Vehicles({data,refresh,notice,brands=[],listings=[],createOnly=false}){"
            if anchor not in text:
                raise PatchError("Não encontrei a função Vehicles.")
            text = text.replace(anchor, HELPER + anchor, 1)

        old_state = "const [form,setForm]=useState(empty),[overview,setOverview]=useState(null),[search,setSearch]=useState(''),[editVehicle,setEditVehicle]=useState(null),[saving,setSaving]=useState(false)"
        new_state = old_state + ",[photoData,setPhotoData]=useState(''),[photoBusy,setPhotoBusy]=useState(false)"
        if old_state in text:
            text = text.replace(old_state, new_state, 1)
        elif "[photoData,setPhotoData]" not in text:
            raise PatchError("Não encontrei os estados da tela de sucatas.")

        if "async function chooseVehiclePhoto" not in text:
            marker = " const filtered=useMemo("
            start = text.find(marker, text.find("function Vehicles("))
            if start < 0:
                raise PatchError("Não encontrei onde inserir o manipulador da foto.")
            end = text.find("\n", start)
            text = text[:end+1] + HANDLER + text[end+1:]

        old_post = "await api.post('/vehicles',{...form,year:form.year?Number(form.year):null,acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)})"
        new_post = "await api.post('/vehicles',{...form,photo_data:photoData,year:form.year?Number(form.year):null,acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)})"
        if old_post in text:
            text = text.replace(old_post, new_post, 1)
        elif "photo_data:photoData" not in text:
            raise PatchError("Não encontrei o POST de cadastro da sucata.")

        reset_anchor = "setForm({...empty,year:new Date().getFullYear()})"
        if reset_anchor in text and "setPhotoData('')" not in text:
            text = text.replace(reset_anchor, reset_anchor + ";setPhotoData('')", 1)

        old_button = """<button className="primary" disabled={saving} onClick={add}>{saving?'Salvando...':'+ Cadastrar veículo'}</button>"""
        if old_button in text:
            text = text.replace(old_button, PHOTO_BLOCK, 1)
        elif "FOTO PRINCIPAL DA SUCATA" not in text:
            raise PatchError("Não encontrei o botão Cadastrar veículo.")

        if OLD_IDENTITY in text:
            text = text.replace(OLD_IDENTITY, NEW_IDENTITY, 1)

        if OLD_360 in text:
            text = text.replace(OLD_360, NEW_360, 1)

        main_jsx.write_text(text, encoding="utf-8")

        print("\nValidando backend...")
        run([sys.executable, "-m", "py_compile", str(main_py), str(models_py), str(vehicles_py)], cwd=base)

        print("\nValidando frontend...")
        run(["npm", "run", "build"], cwd=base / "frontend")

        print("\n==============================================")
        print("FOTO DA SUCATA V2 APLICADA E VALIDADA.")
        print("==============================================")
        print("A foto fica comprimida e salva no banco.")
        print("Agora rode:")
        print("git add -A")
        print('git commit -m "Adiciona foto persistente no cadastro de sucatas"')
        print("git push")

    except Exception as exc:
        for path, content in originals.items():
            path.write_text(content, encoding="utf-8")
        print("\nERRO:", exc)
        print("Os arquivos foram restaurados; nada ficou pela metade.")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
