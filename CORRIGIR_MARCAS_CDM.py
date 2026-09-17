from pathlib import Path
import shutil
import subprocess
import sys
import traceback

FALLBACK_LINE = "const FALLBACK_VEHICLE_BRANDS=['Agrale','Alfa Romeo','Audi','BMW','BYD','CAOA Chery','Chery','Chevrolet','Chrysler','Citroën','Dodge','Fiat','Ford','Geely','GWM','Honda','Hyundai','Iveco','JAC','Jaguar','Jeep','Kia','Land Rover','Lexus','Mercedes-Benz','Mini','Mitsubishi','Nissan','Peugeot','Porsche','RAM','Renault','Subaru','Suzuki','Toyota','Volkswagen','Volvo']\n"

class PatchError(RuntimeError):
    pass

def find_project():
    here = Path.cwd()
    candidates = [here / "CDM_Desmontes_ERP_SaaS_Online_V4", here]
    for base in candidates:
        if (base / "frontend/src/main.jsx").exists():
            return base
    raise PatchError("Projeto não encontrado. Rode este arquivo dentro de C:\\CDM_DEPLOY.")

def run(cmd, cwd=None):
    print(">", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def main():
    base = find_project()
    main_jsx = base / "frontend/src/main.jsx"
    original = main_jsx.read_text(encoding="utf-8")

    try:
        text = original

        # 1) Catálogo de fallback no próprio frontend.
        if "const FALLBACK_VEHICLE_BRANDS=" not in text:
            anchor = "const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})\n"
            if anchor not in text:
                raise PatchError("Não encontrei o ponto para adicionar o catálogo de marcas.")
            text = text.replace(anchor, anchor + FALLBACK_LINE, 1)

        # 2) O estado nunca começa vazio.
        old_state = "const [vehicleBrands,setVehicleBrands]=useState([]),[billing,setBilling]=useState({monthly_price:350,checkout_provider_configured:false})"
        new_state = "const [vehicleBrands,setVehicleBrands]=useState(FALLBACK_VEHICLE_BRANDS),[billing,setBilling]=useState({monthly_price:350,checkout_provider_configured:false})"
        if old_state in text:
            text = text.replace(old_state, new_state, 1)

        # 3) Falha da API de marcas não derruba todo o Promise.all.
        old_api = "api.get('/vehicle-catalog/brands')"
        new_api = "api.get('/vehicle-catalog/brands').catch(()=>({data:{brands:FALLBACK_VEHICLE_BRANDS}}))"
        if old_api in text and new_api not in text:
            text = text.replace(old_api, new_api, 1)

        # 4) Mesmo uma resposta vazia mantém as marcas disponíveis.
        old_set = "setVehicleBrands(vb.data.brands||[])"
        new_set = "setVehicleBrands((vb.data?.brands||[]).length?vb.data.brands:FALLBACK_VEHICLE_BRANDS)"
        if old_set in text:
            text = text.replace(old_set, new_set, 1)

        # 5) O próprio componente também tem fallback independente.
        old_component = """function VehicleBrandModel({form,setForm,brands=[]}){const [models,setModels]=useState([]),[customModel,setCustomModel]=useState(false);useEffect(()=>{let active=true;setModels([]);if(!form.brand){return}api.get('/vehicle-catalog/models',{params:{brand:form.brand}}).then(r=>{if(active){setModels(r.data.models||[]);if(form.model&&!(r.data.models||[]).includes(form.model))setCustomModel(true)}}).catch(()=>setModels([]));return()=>{active=false}},[form.brand]);return <><Field label="Marca"><select value={form.brand||''} onChange={e=>{setForm({...form,brand:e.target.value,model:''});setCustomModel(false)}}><option value="">Selecione a marca...</option>{brands.map(b=><option key={b} value={b}>{b}</option>)}</select></Field><Field label="Modelo">{customModel?<div className="inlineInput"><input autoFocus value={form.model||''} onChange={e=>setForm({...form,model:e.target.value})} placeholder="Digite o modelo"/><button type="button" className="ghost mini" onClick={()=>{setCustomModel(false);setForm({...form,model:''})}}>Lista</button></div>:<select value={form.model||''} disabled={!form.brand} onChange={e=>{if(e.target.value==='__custom__'){setCustomModel(true);setForm({...form,model:''})}else setForm({...form,model:e.target.value})}}><option value="">{form.brand?'Selecione o modelo...':'Escolha a marca primeiro'}</option>{models.map(m=><option key={m} value={m}>{m}</option>)}<option value="__custom__">Outro / digitar manualmente...</option></select>}</Field></>}"""

        new_component = """function VehicleBrandModel({form,setForm,brands=[]}){const [models,setModels]=useState([]),[customModel,setCustomModel]=useState(false);const availableBrands=brands?.length?brands:FALLBACK_VEHICLE_BRANDS;useEffect(()=>{let active=true;setModels([]);if(!form.brand){return}api.get('/vehicle-catalog/models',{params:{brand:form.brand}}).then(r=>{if(active){setModels(r.data.models||[]);if(form.model&&!(r.data.models||[]).includes(form.model))setCustomModel(true)}}).catch(()=>{if(active)setModels([])});return()=>{active=false}},[form.brand]);return <><Field label="Marca"><select value={form.brand||''} onChange={e=>{setForm({...form,brand:e.target.value,model:''});setCustomModel(false)}}><option value="">Selecione a marca...</option>{availableBrands.map(b=><option key={b} value={b}>{b}</option>)}</select></Field><Field label="Modelo">{customModel?<div className="inlineInput"><input autoFocus value={form.model||''} onChange={e=>setForm({...form,model:e.target.value})} placeholder="Digite o modelo"/><button type="button" className="ghost mini" onClick={()=>{setCustomModel(false);setForm({...form,model:''})}}>Lista</button></div>:<select value={form.model||''} disabled={!form.brand} onChange={e=>{if(e.target.value==='__custom__'){setCustomModel(true);setForm({...form,model:''})}else setForm({...form,model:e.target.value})}}><option value="">{form.brand?'Selecione o modelo...':'Escolha a marca primeiro'}</option>{models.map(m=><option key={m} value={m}>{m}</option>)}<option value="__custom__">Outro / digitar manualmente...</option></select>}</Field></>}"""

        if old_component in text:
            text = text.replace(old_component, new_component, 1)
        elif "const availableBrands=brands?.length?brands:FALLBACK_VEHICLE_BRANDS;" not in text:
            raise PatchError("Não encontrei o componente Marca/Modelo esperado.")

        # Corrige só o rótulo visual do diagnóstico que ficou em 14.1.
        text = text.replace("DIAGNÓSTICO V14.1", "DIAGNÓSTICO V14.2")

        main_jsx.write_text(text, encoding="utf-8")

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
        print("CORREÇÃO DE MARCAS APLICADA E VALIDADA.")
        print("==============================================")
        print("Agora rode:")
        print("git add -A")
        print('git commit -m "Corrige seletor de marcas no cadastro de sucatas"')
        print("git push")

    except Exception as exc:
        main_jsx.write_text(original, encoding="utf-8")
        print("\nERRO:", exc)
        print("O frontend foi restaurado.")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
