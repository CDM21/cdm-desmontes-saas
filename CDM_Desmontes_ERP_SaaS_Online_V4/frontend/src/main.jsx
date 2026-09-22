import React,{useEffect,useMemo,useRef,useState} from 'react'
import {createRoot} from 'react-dom/client'
import axios from 'axios'
import {QRCodeSVG} from 'qrcode.react'
import './styles.css'

const API=import.meta.env.VITE_API_URL || ((location.hostname==='localhost'||location.hostname==='127.0.0.1')?'http://localhost:8000/api':'/api')
const api=axios.create({baseURL:API})
const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})
const cleanNcm=v=>String(v||'').replace(/\D/g,'').slice(0,8)
const FALLBACK_VEHICLE_BRANDS=['Agrale','Alfa Romeo','Audi','BMW','BYD','CAOA Chery','Chery','Chevrolet','Chrysler','Citroën','Dodge','Fiat','Ford','Geely','GWM','Honda','Hyundai','Iveco','JAC','Jaguar','Jeep','Kia','Land Rover','Lexus','Mercedes-Benz','Mini','Mitsubishi','Nissan','Peugeot','Porsche','RAM','Renault','Subaru','Suzuki','Toyota','Volkswagen','Volvo']
const fmtDate=v=>v?new Date(v).toLocaleDateString('pt-BR'):'—'
const statusPt=v=>({trial:'Teste',active:'Ativa',pending:'Pendente',past_due:'Atrasada',canceled:'Cancelada',inactive:'Inativa',paid:'Pago',published:'Publicado',processing:'Processando',queued:'Na fila',draft:'Rascunho',authorized:'Autorizada',approved:'Aprovada',rejected:'Rejeitada',cancelled:'Cancelada',disconnected:'Desconectado',connected:'Conectado',needs_connection:'Conectar conta',needs_product_data:'Completar produto',sold_out:'Sem estoque',sync_error:'Erro de sincronização',error:'Erro',paused:'Pausado',closed:'Encerrado',open:'Aberto',normal:'Normal',received:'Recebido',available:'Disponível',sold:'Vendido',completed:'Concluído',finished:'Finalizado',blocked:'Bloqueado',cancelled_by_user:'Cancelada pelo usuário',rascunho:'Rascunho',autorizada:'Autorizada',rejeitada:'Rejeitada',processando:'Processando'}[String(v||'').toLowerCase()]||v||'—')
const valuePt=(key,v)=>key==='kind'?({income:'Entrada',expense:'Saída'}[v]||v):key==='status'?statusPt(v):key==='source'?({manual:'Venda local',mercadolivre:'Mercado Livre',shopee:'Shopee',olx:'OLX',system:'Sistema'}[v]||v):key==='payment_method'?({pix:'PIX',cash:'Dinheiro',card:'Cartão',credit:'Cartão de crédito',debit:'Cartão de débito',mercadolivre:'Mercado Livre',shopee:'Shopee',olx:'OLX'}[v]||v):key==='condition'?({new:'Novo',used:'Usado',reconditioned:'Recondicionado'}[v]||v):key==='role'?({owner:'Administrador principal',admin:'Administrador',user:'Usuário'}[v]||v):key==='active'?(v?'Sim':'Não'):v
const erroPt=v=>{
 const t=String(v||'').trim();if(!t)return '';const l=t.toLowerCase();
 const pt=[
  ['account_not_connected','Conta não conectada'],['unauthorized','Autorização expirada ou inválida'],['invalid token','Autorização expirada ou inválida'],
  ['bad request','O canal recusou os dados enviados'],['timeout','O canal demorou para responder'],['timed out','O canal demorou para responder'],
  ['required','Há informações obrigatórias faltando'],['missing','Há informações obrigatórias faltando'],['not found','Informação não encontrada no serviço externo'],
  ['forbidden','A conta não tem permissão para concluir esta operação'],['rate limit','O limite temporário do serviço externo foi atingido. Tente novamente em alguns minutos'],
  ['too many requests','O serviço recebeu muitas solicitações. Tente novamente em alguns minutos'],['expired','A autorização expirou. Conecte a conta novamente'],
  ['invalid','O serviço externo recusou uma informação enviada'],['already exists','Este cadastro já existe no serviço externo'],
  ['user bad request','O Mercado Pago recusou os dados do usuário de teste'],['both payer and collector','Pagador e recebedor precisam ser usuários válidos do mesmo ambiente de pagamento']
 ];
 for(const [k,msg] of pt)if(l.includes(k))return msg;
 if(/[áàâãéêíóôõúç]/i.test(t)||/\b(não|erro|conta|empresa|peça|venda|assinatura|pagamento|cadastro|produto|estoque|autorização|inválid|obrigat|encontrad|configurad)\b/i.test(t))return t;
 return 'Não foi possível concluir a operação no serviço externo. Verifique a configuração do canal.'
}
function setToken(t){localStorage.setItem('token',t);api.defaults.headers.common.Authorization=`Bearer ${t}`}
async function logout(){try{await api.post('/auth/logout')}catch(e){}localStorage.removeItem('token');delete api.defaults.headers.common.Authorization;location.href='/'}

const MENU=[
 {key:'dashboard',icon:'▦',label:'Painel'},
 {key:'qrcode',icon:'⌗',label:'Código QR'},
 {key:'cadastros',icon:'▣',label:'Cadastros',children:[
   {key:'vehicle-create',icon:'▰',label:'Cadastro de Sucatas'},
   {key:'product-create',icon:'⚙',label:'Cadastro de Peças'},
   {key:'part-groups',icon:'◆',label:'Grupo de peças'},
   {key:'customers',icon:'♣',label:'Clientes'},
   {key:'locations',icon:'●',label:'Localizações'},
   {key:'carriers',icon:'▰',label:'Transportadoras'},
   {key:'sellers',icon:'♟',label:'Vendedores'},
   {key:'suppliers',icon:'♙',label:'Fornecedores'},
   {key:'tax',icon:'⌁',label:'Configuração Tributária'},
   {key:'users',icon:'♟',label:'Usuários e permissões'}
 ]},
 {key:'products',icon:'▤',label:'Estoque de peças'},
 {key:'vehicles',icon:'▱',label:'Sucatas'},
 {key:'etiquetas',icon:'◇',label:'Etiquetas',children:[
   {key:'labels',label:'Gerar etiquetas'},
   {key:'label-models',label:'Modelos de etiqueta'}
 ]},
 {key:'integracoes',icon:'◈',label:'Integrações',children:[
   {key:'marketplaces',label:'Central de canais'},
   {key:'mercadolivre',label:'Mercado Livre'},
   {key:'shopee',label:'Shopee'},
   {key:'olx',label:'OLX'}
 ]},
 {key:'compras',icon:'▾',label:'Compras',children:[
   {key:'purchase-new',label:'Nova Compra'},
   {key:'purchases',label:'Compras Realizadas'}
 ]},
 {key:'vendas',icon:'$',label:'Vendas',children:[
   {key:'sales',label:'Nova Venda'},
   {key:'sales-history',label:'Central de Pedidos'},
   {key:'shipping',label:'Painel de Expedição'}
 ]},
 {key:'notas',icon:'▧',label:'Notas Fiscais',children:[
   {key:'invoices',label:'NF-e'},
   {key:'invoice-history',label:'Notas Emitidas'},
   {key:'xml',label:'Enviar XML'},
   {key:'invalidate-number',label:'Inutilizar número'}
 ]},
 {key:'inteligencia',icon:'✦',label:'Inteligência CDM',children:[
   {key:'assistant-cdm',label:'Assistente CDM'},
   {key:'owner-panel',label:'Painel do Dono'},
   {key:'radar',label:'Radar de Oportunidades'},
   {key:'smart-dismantling',label:'Desmonte Inteligente'},
   {key:'smart-pricing',label:'Preço Inteligente'},
   {key:'sale-protection',label:'Proteção de Venda'}
 ]},
 {key:'finance',icon:'◉',label:'Financeiro'},
 {key:'subscription',icon:'R$',label:'Assinatura'},
 {key:'cashflow',icon:'⇆',label:'Fluxo de Caixa'},
 {key:'reports',icon:'▥',label:'Relatórios'},
 {key:'gamification',icon:'✦',label:'Gamificação'},
 {key:'platform-admin',icon:'★',label:'Painel SaaS do Dono'}
]
const ROLE_TABS={
 manager:new Set(['dashboard','qrcode','cadastros','vehicle-create','product-create','part-groups','customers','locations','carriers','sellers','suppliers','products','vehicles','marketplaces','sales','sales-history','shipping','finance','cashflow','reports']),
 stock:new Set(['dashboard','qrcode','cadastros','vehicle-create','product-create','part-groups','locations','suppliers','products','vehicles','shipping','reports']),
 cashier:new Set(['dashboard','customers','products','sales','sales-history','shipping','reports']),
 user:new Set(['dashboard','products','vehicles','sales-history','reports'])
}
function roleLabel(r){return ({owner:'Dono',admin:'Administrador',manager:'Gerente',stock:'Estoque',cashier:'Vendedor / Caixa',user:'Somente leitura'}[r]||r||'Usuário')}
function canAccessTab(r,k,isPlatformAdmin=false){if(k==='platform-admin')return !!isPlatformAdmin;if(r==='owner'||r==='admin')return true;return (ROLE_TABS[r]||ROLE_TABS.user).has(k)}
const TITLE_MAP={company:'Informações da Empresa'}
MENU.forEach(item=>{TITLE_MAP[item.key]=item.label;(item.children||[]).forEach(c=>TITLE_MAP[c.key]=c.label)})



function OwnerPreviewReturnButton({onReturn}){
 const [pos,setPos]=useState(()=>{
  try{
   const saved=JSON.parse(localStorage.getItem('ownerPreviewReturnPos')||'null')
   return saved&&Number.isFinite(saved.x)&&Number.isFinite(saved.y)?saved:null
  }catch{return null}
 })
 const [open,setOpen]=useState(false)
 const drag=useRef(null)
 const moved=useRef(false)

 function clampPosition(x,y,w,h){
  const pad=8
  return {
   x:Math.max(pad,Math.min(x,window.innerWidth-w-pad)),
   y:Math.max(pad,Math.min(y,window.innerHeight-h-pad))
  }
 }

 function startDrag(e){
  if(e.button!==0)return
  const rect=e.currentTarget.getBoundingClientRect()
  drag.current={dx:e.clientX-rect.left,dy:e.clientY-rect.top,w:rect.width,h:rect.height,sx:e.clientX,sy:e.clientY}
  moved.current=false
  setOpen(true)
  e.currentTarget.setPointerCapture?.(e.pointerId)
 }

 function moveDrag(e){
  if(!drag.current)return
  const d=drag.current
  if(Math.abs(e.clientX-d.sx)>4||Math.abs(e.clientY-d.sy)>4)moved.current=true
  setPos(clampPosition(e.clientX-d.dx,e.clientY-d.dy,d.w,d.h))
 }

 function endDrag(e){
  if(!drag.current)return
  drag.current=null
  e.currentTarget.releasePointerCapture?.(e.pointerId)
 }

 function handleClick(e){
  if(moved.current){
   e.preventDefault()
   e.stopPropagation()
   moved.current=false
   return
  }
  onReturn()
 }

 useEffect(()=>{
  if(!pos)return
  localStorage.setItem('ownerPreviewReturnPos',JSON.stringify(pos))
 },[pos])

 useEffect(()=>{
  if(!pos)return
  const fit=()=>{
   const el=document.querySelector('.ownerPreviewFloat')
   if(!el)return
   const rect=el.getBoundingClientRect()
   setPos(p=>p?clampPosition(p.x,p.y,rect.width,rect.height):p)
  }
  window.addEventListener('resize',fit)
  return()=>window.removeEventListener('resize',fit)
 },[])

 const expanded=open||!!drag.current
 const style=pos?{left:pos.x,top:pos.y,right:'auto',bottom:'auto',touchAction:'none',cursor:drag.current?'grabbing':'grab',userSelect:'none'}:{touchAction:'none',cursor:drag.current?'grabbing':'grab',userSelect:'none'}

 return <button
  className={`ownerPreviewFloat ownerPreviewFloatCompact ${expanded?'open':''}`}
  title={expanded?'Arraste para mover ou clique para voltar':'Voltar ao Portal do Dono'}
  onPointerDown={startDrag}
  onPointerMove={moveDrag}
  onPointerUp={endDrag}
  onPointerCancel={endDrag}
  onMouseEnter={()=>setOpen(true)}
  onMouseLeave={()=>{if(!drag.current)setOpen(false)}}
  onFocus={()=>setOpen(true)}
  onBlur={()=>{if(!drag.current)setOpen(false)}}
  onClick={handleClick}
  style={style}
 >
  <span className="ownerPreviewFloatIcon">↩</span>
  <span className="ownerPreviewFloatText">Voltar ao Portal do Dono</span>
 </button>
}


function App(){
 const [logged,setLogged]=useState(!!localStorage.getItem('token'))
 const [tab,setTab]=useState('dashboard')
 const [theme,setTheme]=useState(localStorage.getItem('theme')||'dark')
 const [session,setSession]=useState(null)
 const [vehicles,setVehicles]=useState([]),[products,setProducts]=useState([]),[sales,setSales]=useState([]),[finance,setFinance]=useState([]),[marketplaces,setMarketplaces]=useState([]),[listings,setListings]=useState([])
 const [vehicleBrands,setVehicleBrands]=useState(FALLBACK_VEHICLE_BRANDS),[billing,setBilling]=useState({monthly_price:350,checkout_provider_configured:false})
 const [catalog,setCatalog]=useState({customers:[],suppliers:[],carriers:[],sellers:[],partGroups:[],locations:[],users:[],tax:null})
 const [toast,setToast]=useState('')
 const [mobileNav,setMobileNav]=useState(false)
 const [ownerPreview,setOwnerPreview]=useState(false)
 useEffect(()=>{document.body.dataset.theme=theme;localStorage.setItem('theme',theme)},[theme])
 useEffect(()=>{const t=localStorage.getItem('token');if(t)api.defaults.headers.common.Authorization=`Bearer ${t}`},[])
 async function load(){
   try{
     const me=await api.get('/auth/me')
     setSession(me.data)
     const platformAdmin=!!me.data?.is_platform_admin
     if(platformAdmin&&!ownerPreview){setBilling({active:true});return}
     const bi=platformAdmin?{data:{active:true}}:await api.get('/billing/status')
     setBilling(bi.data||{})
     const role=me.data?.user?.role||'user';const canFinance=['owner','admin','manager'].includes(role);const canUsers=['owner','admin'].includes(role)
     if(bi.data?.active===false){
       setVehicles([]);setProducts([]);setSales([]);setFinance([]);setMarketplaces([]);setListings([])
       return
     }
     const [v,p,s,f,m,l,cu,su,ca,se,pg,lo,us,tx,vb]=await Promise.all([
       api.get('/vehicles'),api.get('/products'),api.get('/sales'),canFinance?api.get('/finance'):Promise.resolve({data:[]}),api.get('/marketplaces/status'),api.get('/marketplaces/listings'),
       api.get('/catalog/customers'),api.get('/catalog/suppliers'),api.get('/catalog/carriers'),api.get('/catalog/sellers'),api.get('/catalog/part-groups'),api.get('/catalog/locations'),canUsers?api.get('/catalog/users'):Promise.resolve({data:[]}),api.get('/catalog/tax'),api.get('/vehicle-catalog/brands').catch(()=>({data:{brands:FALLBACK_VEHICLE_BRANDS}}))
     ])
     setVehicles(v.data);setProducts(p.data);setSales(s.data);setFinance(f.data);setMarketplaces(m.data);setListings(l.data)
     setVehicleBrands((vb.data?.brands||[]).length?vb.data.brands:FALLBACK_VEHICLE_BRANDS)
     setCatalog({customers:cu.data,suppliers:su.data,carriers:ca.data,sellers:se.data,partGroups:pg.data,locations:lo.data,users:us.data,tax:tx.data})
   }catch(e){if(e.response?.status===401){logout()}else if(e.response?.status===402){setBilling(b=>({...b,active:false}))}else console.error(e)}
 }
 useEffect(()=>{if(logged)load()},[logged,ownerPreview])
 useEffect(()=>{if(session&&!canAccessTab(session?.user?.role,tab,session?.is_platform_admin))setTab('dashboard')},[tab,session])
 useEffect(()=>{const q=new URLSearchParams(location.search);const integration=q.get('integration');const status=q.get('status');const billingReturn=q.get('billing');if(integration){setTab('marketplaces');setTimeout(()=>notice(status==='connected'?`${marketName(integration)} conectado com sucesso`:`Não foi possível conectar ${marketName(integration)}`),300);history.replaceState({},'',location.pathname);return}if(billingReturn==='return'){setTab('billing');setTimeout(async()=>{await load();notice(q.get('stage')==='implementation'?'Pagamento recebido. Confira a implantação e continue para a mensalidade.':'Pagamento retornou do Mercado Pago. Atualizando sua assinatura...')},350);history.replaceState({},'',location.pathname)}},[])
 function notice(t){setToast(t);setTimeout(()=>setToast(''),3800)}
 const publicParams=new URLSearchParams(location.search)
 const publicStore=publicParams.get('loja'),warrantyToken=publicParams.get('garantia')
 if(publicStore)return <PublicCatalog companyId={+publicStore}/>
 if(warrantyToken)return <PublicWarranty token={warrantyToken}/>
 if(!logged)return <Login onLogin={r=>{setToken(r.access_token);setSession(r);setLogged(true)}}/>
 if(logged&&!session)return <div className="ownerLoading">Carregando CDM...</div>
 if(session?.is_platform_admin&&!ownerPreview)return <OwnerPortal session={session} onPreview={()=>{setOwnerPreview(true);setTab('dashboard')}}/>
 const accessBlocked=!!session&&billing?.active===false
 return <div className="appShell">
   <Sidebar tab={tab} setTab={setTab} company={session?.company} role={session?.user?.role} isAdmin={session?.is_platform_admin} openMobile={mobileNav} onClose={()=>setMobileNav(false)}/>
   <main className="mainArea">
     <Topbar tab={tab} setTab={setTab} session={session} theme={theme} setTheme={setTheme} onMenu={()=>setMobileNav(true)}/>
     <div className="content">
       {accessBlocked?<BillingPage billing={billing} session={session} refresh={load} notice={notice}/>:<>
       {tab==='dashboard'&&<Dashboard v={vehicles} p={products} s={sales} f={finance} marketplaces={marketplaces} session={session} setTab={setTab}/>}
       {tab==='company'&&<CompanyInfo session={session} reload={load} notice={notice}/>}
       {tab==='qrcode'&&<QRCodeModule products={products} locations={catalog.locations}/>}
       {tab==='vehicle-create'&&<Vehicles data={vehicles} refresh={load} notice={notice} brands={vehicleBrands} listings={listings}/>}
       {tab==='vehicles'&&<Vehicles data={vehicles} refresh={load} notice={notice} brands={vehicleBrands} listings={listings}/>}
       {tab==='product-create'&&<ProductForm refresh={load} notice={notice} groups={catalog.partGroups} brands={vehicleBrands} vehicles={vehicles} locations={catalog.locations}/>}
       {tab==='products'&&<Inventory data={products} listings={listings} refresh={load} notice={notice} groups={catalog.partGroups} brands={vehicleBrands} vehicles={vehicles} locations={catalog.locations} company={session?.company}/>}
       {['customers','suppliers','carriers','sellers','part-groups','locations','tax'].includes(tab)&&<CatalogModule tab={tab} data={catalog} refresh={load} notice={notice}/>} {tab==='users'&&<UsersPermissions notice={notice}/>}
       {tab==='cadastros'&&<CadastrosHome setTab={setTab}/>}
       {['labels','label-models','etiquetas'].includes(tab)&&<LabelsModule tab={tab} products={products} company={session?.company}/>}
       {tab==='sales'&&<Sales products={products} sales={sales} customers={catalog.customers} refresh={load} notice={notice}/>}
       {tab==='sales-history'&&<SalesHistory sales={sales} refresh={load}/>}
       {tab==='shipping'&&<ShippingPanel sales={sales} refresh={load} notice={notice}/>}
       {['marketplaces','mercadolivre','shopee','olx','integracoes'].includes(tab)&&<Marketplaces data={marketplaces} listings={listings} products={products} refresh={load} notice={notice} focus={tab} subscription={session?.subscription}/>}
       {['purchase-new','purchases','compras'].includes(tab)&&<SimpleModule eyebrow="COMPRAS" title={tab==='purchase-new'?'Nova Compra':'Compras'} text="Controle pedidos de compra, fornecedores, custos e recebimentos." actions={['Novo pedido de compra','Compras realizadas','Recebimentos']}/>}
       {['invoices','invoice-history','xml','invalidate-number','notas'].includes(tab)&&<FiscalModule tab={tab} notice={notice}/>}
       {tab==='inteligencia'&&<IntelligenceHome setTab={setTab}/>}
       {tab==='assistant-cdm'&&<AssistantCDM/>}
       {tab==='owner-panel'&&<OwnerPanel/>}
       {tab==='radar'&&<OpportunityRadar/>}
       {tab==='smart-dismantling'&&<SmartDismantling vehicles={vehicles} notice={notice}/>}
       {tab==='smart-pricing'&&<SmartPricing products={products} refresh={load} notice={notice}/>}
       {tab==='sale-protection'&&<SaleProtection sales={sales} products={products} notice={notice}/>}
       {tab==='finance'&&<Finance data={finance} refresh={load} notice={notice}/>}
       {tab==='subscription'&&<BillingPage billing={billing} session={session} refresh={load} notice={notice}/>}
       {tab==='cashflow'&&<CashFlow data={finance}/>}
       {tab==='reports'&&<Reports products={products} sales={sales} finance={finance} vehicles={vehicles}/>}
       {tab==='gamification'&&<Gamification sales={sales} products={products}/>}
       {tab==='platform-admin'&&session?.is_platform_admin&&<PlatformAdminV2 notice={notice}/>}
       </>}
     </div>
   </main>
   {session?.is_platform_admin&&ownerPreview&&<OwnerPreviewReturnButton onReturn={()=>setOwnerPreview(false)}/>}
   {toast&&<div className="toast">✓ {toast}</div>}
 </div>
}

function OwnerPortal({session,onPreview}){
 const [section,setSection]=useState('overview')
 const [data,setData]=useState({summary:{},companies:[],recent_logs:[],automation:{}})
 const [filter,setFilter]=useState('all')
 const [query,setQuery]=useState('')
 const [busy,setBusy]=useState(false)
 const [toast,setToast]=useState('')
 const [lastUpdate,setLastUpdate]=useState(null)
 const [readiness,setReadiness]=useState(null)
 const [founders,setFounders]=useState(null)
 const [billingOverview,setBillingOverview]=useState(null)
 const [mpHealth,setMpHealth]=useState(null)
 const [launch,setLaunch]=useState(null)
 const [restoreTesting,setRestoreTesting]=useState(false)
 const [mpTesting,setMpTesting]=useState(false)
 const [v14Errors,setV14Errors]=useState({founders:'',readiness:'',billing:'',mercadopago:''})
 const s=data.summary||{}, rows=data.companies||[], logs=data.recent_logs||[]
 const founderMap=new Map((founders?.founders||[]).map(x=>[Number(x.company_id),Number(x.slot)]))
 const setupFeeMap=new Map((billingOverview?.items||[]).map(x=>[Number(x.company_id),x]))
 const statusMeta={active:['Ativa','success'],trial:['Teste','info'],past_due:['Atrasada','danger'],blocked:['Bloqueada','dark'],canceled:['Cancelada','muted'],inactive:['Inativa','muted']}
 const pop=t=>{setToast(t);setTimeout(()=>setToast(''),3200)}

 async function load(silent=false){
   if(!silent)setBusy(true)
   try{
     const r=await api.get('/admin/dashboard-v2')
     setData(r.data||{})
     const [readinessR,foundersR,billingR,mpHealthR,launchR]=await Promise.all([
       api.get('/v14/admin/platform-readiness')
         .then(x=>({ok:true,data:x.data}))
         .catch(e=>({ok:false,error:`HTTP ${e.response?.status||'-'} - ${erroPt(e.response?.data?.detail)||e.message||'Falha na API V14'}`})),
       api.get('/v14/admin/founders')
         .then(x=>({ok:true,data:x.data}))
         .catch(e=>({ok:false,error:`HTTP ${e.response?.status||'-'} - ${erroPt(e.response?.data?.detail)||e.message||'Falha na API V14'}`})),
       api.get('/v14/admin/billing-overview')
         .then(x=>({ok:true,data:x.data}))
         .catch(e=>({ok:false,error:`HTTP ${e.response?.status||'-'} - ${erroPt(e.response?.data?.detail)||e.message||'Falha na cobrança V14'}`})),
       api.get('/billing/admin/mercadopago-health')
         .then(x=>({ok:true,data:x.data}))
         .catch(e=>({ok:false,error:`HTTP ${e.response?.status||'-'} - ${erroPt(e.response?.data?.detail)||e.message||'Falha ao validar Mercado Pago'}`})),
       api.get('/v15/admin/launch-readiness')
         .then(x=>({ok:true,data:x.data}))
         .catch(e=>({ok:false,error:`HTTP ${e.response?.status||'-'} - ${erroPt(e.response?.data?.detail)||e.message||'Falha no diagnóstico V15'}`}))
     ])
     setReadiness(readinessR.ok?readinessR.data:null)
     setFounders(foundersR.ok?foundersR.data:null)
     setBillingOverview(billingR.ok?billingR.data:null)
     setMpHealth(mpHealthR.ok?mpHealthR.data:null)
     setLaunch(launchR.ok?launchR.data:null)
     setV14Errors({
       readiness:readinessR.ok?'':readinessR.error,
       founders:foundersR.ok?'':foundersR.error,
       billing:billingR.ok?'':billingR.error,
       mercadopago:mpHealthR.ok?'':mpHealthR.error
     })
     setLastUpdate(new Date())
   }catch(e){pop(erroPt(e.response?.data?.detail)||'Erro ao carregar o Portal do Dono')}
   finally{if(!silent)setBusy(false)}
 }
 useEffect(()=>{load();const t=setInterval(()=>load(true),60000);return()=>clearInterval(t)},[])

 async function testRestore(){
   setRestoreTesting(true)
   try{
     const r=await api.post('/v15/admin/backup-restore-drill',{key:''})
     pop(`Restauração validada: ${r.data?.tables||0} tabelas · ${r.data?.rows||0} registros`)
     await load(true)
   }catch(e){pop(erroPt(e.response?.data?.detail)||'Não foi possível concluir o teste de restauração')}
   finally{setRestoreTesting(false)}
 }
 async function testMercadoPago(){
   setMpTesting(true)
   try{
     const r=await api.get('/billing/admin/mercadopago-health?refresh=true')
     setMpHealth(r.data||null)
     if(r.data?.valid)pop(r.data?.ready?'Mercado Pago validado e pronto':'Mercado Pago validado; revise o webhook')
     else pop(r.data?.message||'Mercado Pago nao foi validado')
   }catch(e){pop(erroPt(e.response?.data?.detail)||'Nao foi possivel testar o Mercado Pago')}
   finally{setMpTesting(false)}
 }
 async function act(c,action){
   try{
     if(action==='trial')await api.post(`/admin/companies/${c.id}/trial?days=7`)
     if(action==='active')await api.post(`/admin/companies/${c.id}/activate?days=31`)
     if(action==='past_due')await api.post(`/admin/companies/${c.id}/past-due`)
     if(action==='cancel')await api.post(`/admin/companies/${c.id}/cancel`)
     if(action==='block')await api.post(`/admin/companies/${c.id}/block`)
     if(action==='unblock')await api.post(`/admin/companies/${c.id}/unblock`)
     pop('Empresa atualizada');await load(true)
   }catch(e){pop(erroPt(e.response?.data?.detail)||'Não foi possível atualizar a empresa')}
 }
 async function removeCompany(c){
   if(!confirm(`Excluir ${c.trade_name}?\n\nSó será permitido se a empresa não possuir dados operacionais.`))return
   try{await api.delete(`/admin/companies/${c.id}`);pop('Empresa excluída');await load(true)}
   catch(e){pop(erroPt(e.response?.data?.detail)||'Não foi possível excluir a empresa')}
 }

 const shown=rows.filter(c=>{
   const byStatus=filter==='all'||c.visual_status===filter
   const q=query.trim().toLowerCase()
   const byText=!q||[c.trade_name,c.legal_name,c.cnpj,c.email].some(v=>(v||'').toLowerCase().includes(q))
   return byStatus&&byText
 })
 const newClients=Number(s.new_this_month||0)
 const mrr=Number(s.projected_mrr||0)
 const arr=Number(s.projected_arr||mrr*12)
 const attention=Number(s.past_due||0)+Number(s.blocked||0)
 const activeRate=Number(s.companies_total||0)?Math.round((Number(s.active||0)/Number(s.companies_total))*100):0
 const latest=[...rows].sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0)).slice(0,5)

 function badge(c){const [label,kind]=statusMeta[c.visual_status]||[statusPt(c.visual_status),'muted'];return <span className={`ownerStatus ${kind}`}><i/>{label}</span>}
 function expiry(c){
   if(!c.expires_at)return 'Sem vencimento'
   const d=new Date(c.expires_at).toLocaleDateString('pt-BR')
   if(c.visual_status==='past_due')return `Venceu em ${d}`
   if(c.days_remaining===0)return `Vence hoje · ${d}`
   if(c.days_remaining!=null&&c.days_remaining>0)return `${c.days_remaining} dia(s) · ${d}`
   return d
 }

 return <div className="ownerPortal">
   <aside className="ownerSide">
     <div className="ownerBrand"><div>CDM</div><span><b>ADMIN</b><small>Portal do Dono</small></span></div>
     <nav>
       {[['overview','▦','Visão geral'],['clients','♟','Clientes'],['revenue','R$','Receita'],['launch','✓','Lançamento'],['system','◉','Sistema']].map(([k,i,l])=><button key={k} className={section===k?'active':''} onClick={()=>setSection(k)}><span>{i}</span>{l}</button>)}
     </nav>
     <div className="ownerSideBottom">
       <button className="ownerPreviewBtn" onClick={onPreview}>◫ Visualizar ERP</button>
       <div className="ownerIdentity"><b>{session?.user?.name||'Administrador'}</b><span>{session?.user?.email}</span></div>
       <button className="ownerLogout" onClick={logout}>Sair</button>
     </div>
   </aside>

   <main className="ownerMain">
     <header className="ownerTop">
       <div><span>CDM DESMONTES · ADMINISTRAÇÃO</span><h1>{section==='overview'?'Visão geral':section==='clients'?'Clientes':section==='revenue'?'Receita':section==='launch'?'Lançamento':'Sistema'}</h1></div>
       <div className="ownerTopActions"><span className="ownerLive"><i/> Online</span><button onClick={()=>load()} disabled={busy}>{busy?'Atualizando...':'↻ Atualizar'}</button></div>
     </header>

     {section==='overview'&&<>
       <section className="ownerWelcome">
         <div><span>PAINEL EXECUTIVO</span><h2>Olá, Caio.</h2><p>Acompanhe clientes, receita recorrente e saúde da plataforma sem entrar na operação do desmanche.</p></div>
         <div className="ownerDate"><small>Última atualização</small><b>{lastUpdate?lastUpdate.toLocaleTimeString('pt-BR'):'—'}</b></div>
       </section>
       <div className="ownerKpis">
         <article className="main"><span>MRR PREVISTO</span><b>{money(mrr)}</b><small>Receita recorrente mensal das assinaturas ativas</small></article>
         <article><span>ASSINANTES ATIVOS</span><b>{s.active||0}</b><small>{activeRate}% da base cadastrada</small></article>
         <article><span>NOVOS ESTE MÊS</span><b>{newClients}</b><small>Empresas cadastradas no mês atual</small></article>
         <article className={attention?'attention':''}><span>PRECISAM ATENÇÃO</span><b>{attention}</b><small>{s.past_due||0} atrasadas · {s.blocked||0} bloqueadas</small></article>
       </div>
       <div className="ownerOverviewGrid">
         <section className="ownerCard ownerRevenueCard">
           <div className="ownerCardHead"><div><span>RECEITA</span><h3>Visão financeira</h3></div><button onClick={()=>setSection('revenue')}>Ver detalhes →</button></div>
           <div className="ownerRevenueBig"><small>Projeção anual</small><b>{money(arr)}</b></div>
           <div className="ownerRevenueLine"><span>Mensalidade padrão</span><b>{money(s.monthly_price||350)}</b></div>
           <div className="ownerRevenueLine"><span>Assinaturas em teste</span><b>{s.trial||0}</b></div>
           <div className="ownerRevenueLine"><span>Assinaturas atrasadas</span><b>{s.past_due||0}</b></div>
           <div className="ownerInfoNote">O valor acima é projeção de recorrência. Receita efetivamente recebida será contabilizada quando os pagamentos do Mercado Pago forem registrados individualmente.</div>
         </section>
         <section className="ownerCard">
           <div className="ownerCardHead"><div><span>BASE DE CLIENTES</span><h3>Status das assinaturas</h3></div></div>
           <div className="ownerStatusBars">
             {[['Ativas',s.active,'good'],['Teste',s.trial,'info'],['Atrasadas',s.past_due,'bad'],['Bloqueadas',s.blocked,'dark'],['Canceladas',s.canceled,'muted']].map(([l,n,k])=><div key={l}><div><span>{l}</span><b>{n||0}</b></div><em><i className={k} style={{width:`${Math.max(3,Math.min(100,Number(s.companies_total||0)?Number(n||0)/Number(s.companies_total)*100:0))}%`}}/></em></div>)}
           </div>
         </section>
       </div>
       <div className="ownerOverviewGrid">
         <section className="ownerCard">
           <div className="ownerCardHead"><div><span>CLIENTES RECENTES</span><h3>Últimas empresas</h3></div><button onClick={()=>setSection('clients')}>Gerenciar →</button></div>
           <div className="ownerRecent">{latest.map(c=><div key={c.id}><div><b>{c.trade_name}</b><span>{c.created_at?new Date(c.created_at).toLocaleDateString('pt-BR'):'—'} · {c.email||'sem e-mail'}</span></div>{badge(c)}</div>)}{!latest.length&&<p className="ownerEmpty">Nenhuma empresa cadastrada.</p>}</div>
         </section>
         <section className="ownerCard">
           <div className="ownerCardHead"><div><span>PLATAFORMA</span><h3>Uso geral</h3></div><button onClick={()=>setSection('system')}>Monitorar →</button></div>
           <div className="ownerMiniStats"><div><b>{s.users_total||0}</b><span>usuários</span></div><div><b>{s.products_total||0}</b><span>peças</span></div><div><b>{s.sales_total||0}</b><span>vendas</span></div><div><b>{s.companies_total||0}</b><span>empresas</span></div></div>
         </section>
       </div>
     </>}

     {section==='clients'&&<>
       <section className="ownerSectionIntro"><div><span>CLIENTES SaaS</span><h2>Empresas e assinaturas</h2><p>Busque, acompanhe e controle o acesso de cada cliente.</p></div><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar empresa, CNPJ ou e-mail..."/></section>
       <div className="ownerFilters">{[['all','Todas',s.companies_total],['active','Ativas',s.active],['trial','Teste',s.trial],['past_due','Atrasadas',s.past_due],['blocked','Bloqueadas',s.blocked],['canceled','Canceladas',s.canceled]].map(([k,l,n])=><button key={k} className={filter===k?'active':''} onClick={()=>setFilter(k)}>{l}<b>{n||0}</b></button>)}</div>
       <section className="ownerTableCard">
         <div className="ownerCompanyRow head"><span>Empresa</span><span>Status</span><span>Vencimento</span><span>Uso</span><span>Ações</span></div>
         {shown.map(c=><div className="ownerCompanyRow" key={c.id}>
           <div className="ownerCompanyIdentity"><b>{c.trade_name}</b><span>{c.email||c.cnpj||'Sem contato'}</span><small>Empresa #{c.id} · criada {c.created_at?new Date(c.created_at).toLocaleDateString('pt-BR'):'—'}{founderMap.has(Number(c.id))?` · Fundador #${founderMap.get(Number(c.id))}`:setupFeeMap.get(Number(c.id))?` · Implantação ${setupFeeMap.get(Number(c.id)).status==='paid'?'paga':'pendente'}`:''}</small></div>
           <div>{badge(c)}</div>
           <div className="ownerExpiry"><b>{expiry(c)}</b><small>{c.provider||c.subscription_status||'manual'}</small></div>
           <div className="ownerUsage"><span><b>{c.users}</b> usuários</span><span><b>{c.products}</b> peças</span><span><b>{c.sales}</b> vendas</span></div>
           <div className="ownerActions"><select defaultValue="" onChange={e=>{const v=e.target.value;e.target.value='';if(v)act(c,v)}}><option value="">Alterar situação...</option><option value="trial">Dar teste · 7 dias</option><option value="active">Ativar · 31 dias</option><option value="past_due">Marcar atrasada</option><option value="cancel">Cancelar assinatura</option>{c.active?<option value="block">Bloquear acesso</option>:<option value="unblock">Liberar acesso</option>}</select><button onClick={()=>removeCompany(c)}>Excluir</button></div>
         </div>)}
         {!shown.length&&<div className="ownerEmpty">Nenhuma empresa encontrada.</div>}
       </section>
     </>}

     {section==='revenue'&&<>
       <section className="ownerSectionIntro"><div><span>FINANCEIRO DO SaaS</span><h2>Receita e recorrência</h2><p>Indicadores comerciais da plataforma, separados do financeiro dos clientes.</p></div></section>
       <div className="ownerKpis">
         <article className="main"><span>MRR PREVISTO</span><b>{money(mrr)}</b><small>{s.active||0} assinaturas ativas</small></article>
         <article><span>ARR PREVISTO</span><b>{money(arr)}</b><small>MRR × 12 meses</small></article>
         <article><span>MENSALIDADE</span><b>{money(s.monthly_price||350)}</b><small>Plano profissional</small></article>
         <article><span>IMPLANTAÇÕES RECEBIDAS</span><b>{money(billingOverview?.implementation?.received_total||0)}</b><small>{billingOverview?.implementation?.paid||0} pagas · {billingOverview?.implementation?.pending||0} pendentes</small></article>
       </div>
       <section className="ownerCard ownerRevenueExplain">
         <div><span>COBRANÇA AUTOMÁTICA</span><h3>Implantação + mensalidade separadas com segurança</h3><p>A implantação é conciliada como pagamento único aprovado no Mercado Pago. A mensalidade permanece recorrente. O MRR continua sendo projeção até a conciliação individual das cobranças mensais.</p></div>
         <div className="ownerRevenueSteps"><span className="done">✓ Regra dos 10 fundadores</span><span className="done">✓ Implantação única</span><span className="done">✓ Assinatura mensal</span><span className="done">✓ Webhook + reconciliação</span></div>
       </section>
     </>}


     {section==='revenue'&&<section className="ownerCard v14FounderCard">
       <div className="ownerCardHead">
         <div><span>PROGRAMA FUNDADORES</span><h3>Regra dos 10 primeiros clientes</h3></div>
         <span className="pill neutral">{founders?`${founders.assigned||0}/${founders.limit||10} vagas usadas`:'V14.3'}</span>
       </div>
       <div className="v14FounderStats">
         <div><small>FUNDADORES</small><b>{founders?.assigned??'-'}</b></div>
         <div><small>VAGAS RESTANTES</small><b>{founders?.remaining??'-'}</b></div>
         <div><small>MENSALIDADE</small><b>{money(founders?.monthly_price||350)}</b></div>
         <div><small>IMPLANTAÇÃO APÓS 10</small><b>{money(founders?.implementation_fee_after_founders||1500)}</b></div>
       </div>
       {founders?.founders?.length>0&&<div className="v14FounderNames">
         {founders.founders.map(x=><span key={x.company_id}>#{x.slot} · {x.company_name}</span>)}
       </div>}
       {v14Errors.founders
         ?<div className="ownerInfoNote"><b>Diagnóstico da API:</b> {v14Errors.founders}. O bloco permanece visível para facilitar a correção.</div>
         :<div className="ownerInfoNote">Os 10 primeiros clientes reais ficam isentos da implantação. A partir do 11º cliente, a implantação é cobrada uma única vez, além da mensalidade recorrente.</div>}
     </section>}


     {section==='launch'&&<>
       <section className="ownerSectionIntro"><div><span>V15.3 · CENTRO DE LANÇAMENTO</span><h2>Prontidão para clientes reais</h2><p>Um único painel para cobrança, banco, backup, NF-e, marketplaces, e-mail e lançamento comercial.</p></div></section>
       <section className="ownerCard launchHero">
         <div className="launchScore"><strong>{launch?.summary?.percent??0}%</strong><span>{launch?.summary?.done??0} de {launch?.summary?.total??0} verificações concluídas</span></div>
         <div className="launchHeroText">
           <span>STATUS GERAL</span>
           <h3>{launch?.summary?.core_ready?'Base principal pronta para lançamento':'Ainda existem bloqueios antes de liberar clientes'}</h3>
           <p>{launch?.summary?.external_pending||0} item(ns) dependem de serviço ou aprovação externa. O CDM mantém isso separado do que já está funcionando.</p>
         </div>
         <button className="primary" onClick={()=>load()} disabled={busy}>{busy?'Verificando...':'Verificar tudo agora'}</button>
       </section>

       <div className="launchSections">
         {(launch?.sections||[]).map(group=><section className="ownerCard launchGroup" key={group.id}>
           <div className="ownerCardHead"><div><span>{group.id==='critical'?'PRODUÇÃO':group.id==='operations'?'OPERAÇÃO':'COMERCIAL'}</span><h3>{group.label}</h3></div><span className="pill neutral">{(group.checks||[]).filter(x=>x.done).length}/{(group.checks||[]).length}</span></div>
           <div className="launchChecks">
             {(group.checks||[]).map(item=><article key={item.key} className={item.done?'done':item.external?'external':'pending'}>
               <div className="launchCheckIcon">{item.done?'✓':item.external?'↗':'!'}</div>
               <div><b>{item.label}</b><span>{item.detail}</span>{!item.done&&item.action&&<small>{item.action}</small>}</div>
               <em>{item.done?'PRONTO':item.external?'EXTERNO':'PENDENTE'}</em>
             </article>)}
           </div>
         </section>)}
       </div>

       <section className="ownerCard launchActions">
         <div><span>SEGURANÇA DOS DADOS</span><h3>Teste real de restauração</h3><p>O teste baixa o backup externo, valida SHA-256 e reconstrói uma cópia isolada. Ele não escreve no banco de produção.</p></div>
         <button className="ghost" disabled={restoreTesting} onClick={testRestore}>{restoreTesting?'Testando restauração...':'Testar restauração agora'}</button>
       </section>
     </>}

     {section==='system'&&<>
       <section className="ownerSectionIntro"><div><span>SAÚDE DA PLATAFORMA</span><h2>Sistema e monitoramento</h2><p>Uso geral, automações e últimas ações administrativas.</p></div></section>
       <div className="ownerKpis">
         <article><span>EMPRESAS</span><b>{s.companies_total||0}</b><small>cadastradas</small></article>
         <article><span>USUÁRIOS</span><b>{s.users_total||0}</b><small>na plataforma</small></article>
         <article><span>PEÇAS</span><b>{s.products_total||0}</b><small>cadastradas pelos clientes</small></article>
         <article><span>VENDAS</span><b>{s.sales_total||0}</b><small>registradas pelos clientes</small></article>
       </div>
       <div className="ownerOverviewGrid">
         <section className="ownerCard"><div className="ownerCardHead"><div><span>AUTOMAÇÃO</span><h3>Status do SaaS</h3></div></div><div className="ownerAutomationList"><div><i/>Vencimento automático habilitado</div><div><i/>Atualização do painel a cada 60 segundos</div><div><i/>Isolamento por empresa ativo</div><div className={mpHealth?.ready?'':'pending'}><i/>{mpHealth?.ready?'Mercado Pago e conciliação validados':'Mercado Pago aguardando validação'}</div></div></section>
         <section className="ownerCard"><div className="ownerCardHead"><div><span>LOGS</span><h3>Atividades recentes</h3></div></div><div className="ownerLogs">{logs.slice(0,20).map(x=><div key={x.id}><div><b>{x.action}</b><span>{x.entity||'sistema'} {x.entity_id||''}</span></div><small>{x.created_at?new Date(x.created_at).toLocaleString('pt-BR'):'—'}</small></div>)}{!logs.length&&<div className="ownerEmpty">Nenhuma atividade recente.</div>}</div></section>
       </div>
     </>}


     {section==='system'&&<section className="ownerCard v14ReadinessCard">
       <div className="ownerCardHead">
         <div><span>DIAGNÓSTICO V15</span><h3>Segurança, backup e integrações</h3></div>
         <span className="pill neutral">{readiness?.database?.latency_ms!=null?`${readiness.database.latency_ms} ms DB`:'Verificando API'}</span>
       </div>
       {v14Errors.readiness&&<div className="ownerInfoNote"><b>API V14:</b> {v14Errors.readiness}. Agora o erro não fica mais escondido.</div>}
       <div className="v14ReadinessGrid">
         <div><small>BANCO DE DADOS</small><b className={readiness?.database?.online?'v14ReadyYes':'v14ReadyNo'}>{readiness?readiness.database?.online?'Online':'Atenção':'Aguardando'}</b></div>
         <div><small>AUDITORIA</small><b>{readiness?`${readiness.audit?.events||0} eventos`:'-'}</b></div>
         <div><small>BACKUP</small><b>{readiness?.backup?.last_download_at?new Date(readiness.backup.last_download_at).toLocaleDateString('pt-BR'):'Ainda não confirmado'}</b></div>
         <div><small>MERCADO PAGO</small><b className={mpHealth?.valid?'v14ReadyYes':'v14ReadyNo'}>{mpHealth?.valid?'Conectado e validado':readiness?.billing?.mercadopago_configured?'Credencial nao validada':'Aguardando credencial'}</b></div>
         <div><small>WEBHOOK SEGURO</small><b className={readiness?.security?.billing_webhook_secret?'v14ReadyYes':'v14ReadyNo'}>{readiness?.security?.billing_webhook_secret?'Configurado':'Pendente'}</b></div>
         <div><small>CRIPTOGRAFIA</small><b className={readiness?.security?.app_encryption_key?'v14ReadyYes':'v14ReadyNo'}>{readiness?.security?.app_encryption_key?'Configurada':'Revisar ambiente'}</b></div>
         <div><small>MARKETPLACES ATIVOS</small><b>{readiness?.integrations?.active_marketplace_connections??'-'}</b></div>
         <div><small>FUNDADORES</small><b>{readiness?`${readiness.founders?.assigned||0}/${readiness.founders?.limit||10}`:'-/10'}</b></div>
       </div>
       <div className={`mpHealthPanel ${mpHealth?.ready?'ready':mpHealth?.valid?'partial':'attention'}`}>
         <div className="mpHealthHead">
           <div>
             <small>PAGAMENTOS CDM</small>
             <b>{mpHealth?.ready?'Mercado Pago conectado e validado':mpHealth?.valid?'Credencial valida · webhook precisa de atencao':'Validacao do Mercado Pago necessaria'}</b>
             <span>{mpHealth?.message||v14Errors.mercadopago||'O CDM testa a credencial sem criar nenhuma cobranca.'}</span>
           </div>
           <button className="ghost" onClick={testMercadoPago} disabled={mpTesting}>{mpTesting?'Testando...':'Testar agora'}</button>
         </div>
         <div className="mpHealthFacts">
           <span><small>API</small><b>{mpHealth?.valid?'Autenticada':'Pendente'}</b></span>
           <span><small>WEBHOOK</small><b>{mpHealth?.webhook_configured?'Protegido':'Revisar'}</b></span>
           <span><small>PIX</small><b>{mpHealth?.pix_available?'Disponivel':mpHealth?.valid?'Nao listado':'—'}</b></span>
           <span><small>IMPLANTACAO</small><b>{money(mpHealth?.implementation_fee||1500)}</b></span>
           <span><small>MENSALIDADE</small><b>{money(mpHealth?.monthly_price||350)}</b></span>
         </div>
         <small className="mpHealthNote">O teste consulta a API oficial do Mercado Pago e nao cria pagamento. O tipo da credencial (teste ou producao) deve permanecer conferido no painel do Mercado Pago; o CDM nunca exibe seu Access Token.</small>
       </div>
     </section>}

     {toast&&<div className="toast">✓ {toast}</div>}
   </main>
 </div>
}

// CDM MOBILE NAV V2
function Sidebar({tab,setTab,company,role='user',isAdmin,openMobile=false,onClose}){
 const [open,setOpen]=useState({cadastros:true,etiquetas:false,integracoes:false,compras:false,vendas:true,notas:true,inteligencia:true})
 function isActive(item){return tab===item.key||(item.children||[]).some(c=>c.key===tab)}
 const visibleMenu=MENU.map(item=>item.children?({...item,children:item.children.filter(c=>canAccessTab(role,c.key,isAdmin))}):item).filter(item=>item.key==='platform-admin'?isAdmin:(item.children?item.children.length>0:canAccessTab(role,item.key,isAdmin)))
 function go(key){setTab(key);onClose?.()}
 return <>
   {openMobile&&<button className="mobileNavBackdrop" aria-label="Fechar menu" onClick={()=>onClose?.()}/>}
   <aside className={'sidebar '+(openMobile?'mobileOpen':'')}>
     <button className="mobileSidebarClose" aria-label="Fechar menu" onClick={()=>onClose?.()}>×</button>
     <div className="brand"><div className="brandMark">CDM</div><div><h1>{company?.trade_name||'CDM Desmontes'}</h1><small>ERP de autopeças</small></div></div>
     <nav className="sideNav">{visibleMenu.map(item=>item.children?
       <div className={'navGroup '+(isActive(item)?'activeGroup':'')} key={item.key}>
         <button className={'navMain '+(isActive(item)?'active':'')} onClick={()=>setOpen({...open,[item.key]:!open[item.key]})}><span className="navIcon">{item.icon}</span><span className="navLabel">{item.label}</span><span className={'chevron '+(open[item.key]?'open':'')}>⌄</span></button>
         {open[item.key]&&<div className="subNav">{item.children.map(c=><button key={c.key} className={tab===c.key?'active':''} onClick={()=>go(c.key)}><span>{c.icon||'·'}</span>{c.label}</button>)}</div>}
       </div>
       :<button key={item.key} className={'navMain '+(tab===item.key?'active':'')} onClick={()=>go(item.key)}><span className="navIcon">{item.icon}</span><span className="navLabel">{item.label}</span></button>)}</nav>
     <div className="sidebarFoot"><span><i/> Sistema conectado</span><small>CDM Desmontes · V15.3 Integrações</small></div>
   </aside>
 </>
}

function V8Icon({name}){const paths={document:<><path d="M6 2h9l3 3v17H6z"/><path d="M14 2v5h4"/><path d="M9 11h6M9 15h6"/></>,bell:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,cart:<><path d="M3 3h2l2 12h10l2-8H6"/><circle cx="9" cy="19" r="1"/><circle cx="17" cy="19" r="1"/></>,user:<><circle cx="12" cy="8" r="4"/><path d="M4 21c1-5 4-7 8-7s7 2 8 7"/></>};return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]||paths.user}</svg>}

// CDM NOTIFICATIONS V2
function Topbar({tab,setTab,session,theme,setTheme,onMenu}){
 const [profile,setProfile]=useState(false),[query,setQuery]=useState(''),[notifications,setNotifications]=useState([]),[notifOpen,setNotifOpen]=useState(false),[notifFilter,setNotifFilter]=useState('all'),[notifBusy,setNotifBusy]=useState(false)
 const sub=session?.subscription,unread=notifications.filter(n=>!n.is_read).length
 const visibleNotifications=notifFilter==='unread'?notifications.filter(n=>!n.is_read):notifications

 async function loadNotifications(showNotice=false){
   setNotifBusy(true)
   try{
     setNotifications((await api.get('/notifications')).data||[])
   }catch(e){
   }finally{
     setNotifBusy(false)
   }
 }

 async function readAll(){
   try{
     await api.post('/notifications/read-all')
     setNotifications(v=>v.map(x=>({...x,is_read:true})))
   }catch(e){}
 }

 async function readOne(n){
   if(n.is_read)return
   try{
     await api.post(`/notifications/${n.id}/read`)
     setNotifications(v=>v.map(x=>x.id===n.id?{...x,is_read:true}:x))
   }catch(e){}
 }

 async function openNotification(n){
   await readOne(n)
   if(n.sale_id){
     setTab('sales-history')
     setNotifOpen(false)
   }
 }

 useEffect(()=>{loadNotifications();const timer=setInterval(()=>loadNotifications(false),20000);return()=>clearInterval(timer)},[])

 return <header className="topbar">
   <button className="hamb" title="Menu" onClick={()=>onMenu?.()}>☰</button>
   <div className="globalSearch">⌕<input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')setTab('products')}} placeholder="O que você está procurando?"/></div>
   <button className="topAdd" title="Cadastrar peça" onClick={()=>setTab('product-create')}>＋</button><div className="topSpacer"/>
   <button className="topIcon" title="Notas fiscais" onClick={()=>setTab('invoices')}><V8Icon name="document"/></button>
   <div className="notificationWrap">
     <button className="topIcon notificationTrigger" title="Notificações" onClick={()=>{setNotifOpen(!notifOpen);setProfile(false)}}><V8Icon name="bell"/>{unread>0&&<span className="notificationBadge">{unread>99?'99+':unread}</span>}</button>
     {notifOpen&&<div className="notificationPanel notificationPanelV2">
       <div className="notificationHead">
         <div><small>CENTRAL</small><h3>Notificações</h3><span>{unread} não lida(s)</span></div>
         <button onClick={readAll} disabled={!unread}>Marcar tudo como lido</button>
       </div>
       <div className="notificationTools">
         <div><button className={notifFilter==='all'?'active':''} onClick={()=>setNotifFilter('all')}>Todas</button><button className={notifFilter==='unread'?'active':''} onClick={()=>setNotifFilter('unread')}>Não lidas</button></div>
         <button className="notificationRefresh" onClick={()=>loadNotifications(true)} disabled={notifBusy}>{notifBusy?'...':'↻ Atualizar'}</button>
       </div>
       <div className="notificationList">{visibleNotifications.length?visibleNotifications.map(n=><button key={n.id} className={'notificationItem '+(!n.is_read?'unread':'')} onClick={()=>openNotification(n)}>
         <div className={'notificationSource '+n.source}>{n.source==='mercadolivre'?'ML':n.source==='shopee'?'SH':n.source==='olx'?'OLX':'$'}</div>
         <div><b>{n.title}</b><span>{n.message}</span><small>{n.created_at?new Date(n.created_at).toLocaleString('pt-BR'):'Agora'} · {n.source_label||'Sistema'}{n.sale_status?` · ${statusPt(n.sale_status)}`:''}{n.external_order_id?` · Pedido ${n.external_order_id}`:''}</small></div>
         <strong>{Number(n.amount||0)>0?money(n.amount):''}</strong>
       </button>):<div className="notificationEmpty">{notifFilter==='unread'?'Nenhuma notificação não lida.':'Nenhuma notificação por enquanto.'}</div>}</div>
       <div className="notificationFoot">Notificações de vendas são atualizadas automaticamente a cada 20 segundos.</div>
     </div>}
   </div>
   <button className="topIcon" title="Compras" onClick={()=>setTab('purchases')}><V8Icon name="cart"/></button>
   <div className="profileWrap"><button className="profileButton" title="Perfil" onClick={()=>{setProfile(!profile);setNotifOpen(false)}}><V8Icon name="user"/><span>⌄</span></button>
     {profile&&<div className="profileMenu"><div className="profileHead"><div className="avatar">{(session?.user?.name||'U').slice(0,1).toUpperCase()}</div><div><b>{session?.user?.email}</b><small>{roleLabel(session?.user?.role)}</small></div></div><button onClick={()=>{setTab('company');setProfile(false)}}>▦ <span>Informações da Empresa</span></button><div className="themeRow"><span>◉ Alterar tema</span><div><button className={theme==='light'?'sel':''} onClick={()=>setTheme('light')}>☀</button><button className={theme==='dark'?'sel':''} onClick={()=>setTheme('dark')}>☾</button></div></div><div className="subMini"><span>Plano {sub?.plan||'mensal'}</span><b className={['active','trial'].includes(sub?.status)?'ok':'bad'}>{statusPt(sub?.status)}</b></div><button className="dangerText" onClick={logout}>↪ <span>Sair</span></button></div>}
   </div>
 </header>
}

function Login({onLogin}){
 const qs=new URLSearchParams(window.location.search)
 const resetToken=qs.get('reset_token')||''
 const [mode,setMode]=useState(resetToken?'reset':'login'),[err,setErr]=useState(''),[info,setInfo]=useState(''),[busy,setBusy]=useState(false)
 const [login,setLogin]=useState({email:'',password:''})
 const [reg,setReg]=useState({company_name:'',name:'',email:'',password:'',cnpj:'',phone:''})
 const [forgotEmail,setForgotEmail]=useState('')
 const [newPassword,setNewPassword]=useState('')

 async function go(){
   setBusy(true);setErr('');setInfo('')
   try{
     if(mode==='login'){
       const r=await api.post('/auth/login',login);onLogin(r.data)
     }else if(mode==='register'){
       const r=await api.post('/auth/register',reg);onLogin(r.data)
     }else if(mode==='forgot'){
       await api.post('/auth/forgot-password',{email:forgotEmail})
       setInfo('Se este e-mail estiver cadastrado, você receberá as instruções para criar uma nova senha.')
     }else if(mode==='reset'){
       await api.post('/auth/reset-password',{token:resetToken,password:newPassword})
       window.history.replaceState({},document.title,window.location.pathname)
       setInfo('Senha alterada com sucesso. Entre com a nova senha.')
       setMode('login')
       setNewPassword('')
     }
   }catch(e){setErr(erroPt(e.response?.data?.detail)||'Não foi possível continuar')}
   finally{setBusy(false)}
 }

 return <div className="loginPage"><section className="loginHero"><div className="heroLogo">CDM</div><span>CDM DESMONTES ERP</span><h1>Seu desmanche conectado a todos os canais.</h1><p>Estoque, sucatas, vendas, financeiro e publicação nos canais de venda em uma única operação.</p><div className="loginBenefits"><span>✓ Multiempresa</span><span>✓ Mercado Livre, Shopee e OLX</span><span>✓ Controle por assinatura</span><span>✓ 7 dias grátis · depois R$ 350/mês</span></div></section><section className="loginBox">
   {mode!=='reset'&&<div className="loginTabs"><button className={mode==='login'?'active':''} onClick={()=>{setMode('login');setErr('');setInfo('')}}>Entrar</button><button className={mode==='register'?'active':''} onClick={()=>{setMode('register');setErr('');setInfo('')}}>Criar conta</button></div>}
   {mode==='login'&&<><h2>Bem-vindo</h2><p>Acesse o painel da sua empresa.</p><Field label="E-mail"><input value={login.email} onChange={e=>setLogin({...login,email:e.target.value})}/></Field><Field label="Senha"><input type="password" value={login.password} onChange={e=>setLogin({...login,password:e.target.value})}/></Field><button className="loginForgot" onClick={()=>{setForgotEmail(login.email);setMode('forgot');setErr('');setInfo('')}}>Esqueci minha senha</button></>}
   {mode==='register'&&<><h2>Abra sua empresa no CDM</h2><p>O cliente cria a própria conta, testa por 7 dias e depois assina por R$ 350/mês. Os canais de venda são conectados pela própria empresa.</p><Field label="Nome da empresa"><input value={reg.company_name} onChange={e=>setReg({...reg,company_name:e.target.value})}/></Field><Field label="Seu nome"><input value={reg.name} onChange={e=>setReg({...reg,name:e.target.value})}/></Field><Field label="E-mail"><input value={reg.email} onChange={e=>setReg({...reg,email:e.target.value})}/></Field><Field label="Senha"><input type="password" value={reg.password} onChange={e=>setReg({...reg,password:e.target.value})}/></Field><div className="miniGrid"><Field label="CNPJ"><input value={reg.cnpj} onChange={e=>setReg({...reg,cnpj:e.target.value})}/></Field><Field label="Telefone"><input value={reg.phone} onChange={e=>setReg({...reg,phone:e.target.value})}/></Field></div></>}
   {mode==='forgot'&&<><h2>Recuperar acesso</h2><p>Informe o e-mail usado no CDM. Se a conta existir, enviaremos um link temporário.</p><Field label="E-mail"><input value={forgotEmail} onChange={e=>setForgotEmail(e.target.value)}/></Field><button className="loginBack" onClick={()=>{setMode('login');setErr('');setInfo('')}}>← Voltar para entrar</button></>}
   {mode==='reset'&&<><h2>Criar nova senha</h2><p>Use uma senha forte com pelo menos 10 caracteres.</p><Field label="Nova senha"><input type="password" value={newPassword} onChange={e=>setNewPassword(e.target.value)}/></Field></>}
   <button className="primary loginSubmit" disabled={busy} onClick={go}>{busy?'Aguarde...':mode==='login'?'Entrar no sistema →':mode==='register'?'Criar minha conta →':mode==='forgot'?'Enviar link de recuperação →':'Salvar nova senha →'}</button>
   {err&&<div className="error">{err}</div>}{info&&<div className="loginSuccess">{info}</div>}
   <small className="loginNote">Plano profissional: 7 dias de teste e depois R$ 350/mês. A cobrança recorrente é feita pelo Mercado Pago.</small><div className="loginLegal"><a href="/termos" target="_blank" rel="noreferrer">Termos de Uso</a><span>·</span><a href="/privacidade" target="_blank" rel="noreferrer">Privacidade</a></div>
 </section></div>
}

const Card=({icon,title,value,sub})=><div className="metric"><div className="metricIcon">{icon}</div><div><small>{title}</small><strong>{value}</strong><em>{sub}</em></div></div>

// CDM ONBOARDING V11
function OnboardingChecklist({v=[],p=[],s=[],marketplaces=[],session,setTab}){
 const [state,setState]=useState(null),[hidden,setHidden]=useState(false)
 useEffect(()=>{api.get('/onboarding').then(r=>setState(r.data)).catch(()=>{})},[v.length,p.length,s.length,marketplaces.map(x=>`${x.id}:${x.connected}`).join('|'),session?.company?.cnpj])
 const fallback=[
   {id:'company',label:'Dados da empresa',done:!!(session?.company?.trade_name&&session?.company?.cnpj),tab:'company',description:'CNPJ, endereço e contato.'},
   {id:'fiscal',label:'Nota fiscal',done:false,tab:'invoices',description:'Certificado e tributação.'},
   {id:'marketplaces',label:'Canais de venda',done:marketplaces.some(m=>m.connected),tab:'marketplaces',description:'Conecte suas contas.'},
   {id:'first_product',label:'Primeira peça',done:p.length>0,tab:'product-create',description:'Comece seu estoque.'}
 ]
 const steps=state?.steps||fallback, done=steps.filter(x=>x.done).length, pct=state?.percent??Math.round(done/steps.length*100)
 if(hidden)return null
 return <section className={'cdmOnboarding '+(done===steps.length?'complete':'')}>
   <div className="cdmOnboardingHead"><div><span>CONFIGURAÇÃO GUIADA</span><h3>{done===steps.length?'Seu CDM está pronto para operar 🎉':'Deixe sua empresa pronta sem depender de suporte'}</h3><p>{done} de {steps.length} etapas concluídas · {pct}% pronto.</p></div><button type="button" className="ghost cdmOnboardingHide" onClick={()=>setHidden(true)}>Ocultar</button></div>
   <div className="cdmOnboardingProgress"><i style={{width:`${pct}%`}}/></div>
   <div className="cdmOnboardingSteps">{steps.map((step,i)=><button type="button" key={step.id} className={step.done?'done':''} onClick={()=>setTab?.(step.tab)}><b>{step.done?'✓':i+1}</b><span>{step.label}<small>{step.description}</small></span><em>{step.done?'Concluído':'Configurar →'}</em></button>)}</div>
   {done!==steps.length&&<div className="cdmOnboardingTip"><b>Feito para ser sozinho:</b> cada etapa explica o que falta e leva direto para a tela certa. Suas senhas dos marketplaces nunca são entregues ao CDM.</div>}
 </section>
}

function Dashboard({v,p,s,f,marketplaces,session,setTab}){let receita=s.reduce((a,x)=>a+x.total,0),entr=f.filter(x=>x.kind==='income').reduce((a,x)=>a+x.amount,0),sai=f.filter(x=>x.kind==='expense').reduce((a,x)=>a+x.amount,0),stock=p.reduce((a,x)=>a+x.stock,0);return <><div className="pageTitle"><div><span>PAINEL OPERACIONAL</span><h2>{session?.company?.trade_name||'CDM Desmontes'}</h2><p>Acompanhe sua operação em tempo real.</p></div><div className="statusBadge">● Assinatura {statusPt(session?.subscription?.status)}</div></div><OnboardingChecklist v={v} p={p} s={s} marketplaces={marketplaces} session={session} setTab={setTab}/><div className="grid metrics"><Card icon="🚗" title="Sucatas cadastradas" value={v.length} sub="Base de desmontagem"/><Card icon="⚙" title="Peças em estoque" value={stock} sub={`${p.length} SKUs cadastrados`}/><Card icon="↗" title="Faturamento" value={money(receita)} sub={`${s.length} vendas registradas`}/><Card icon="▣" title="Saldo financeiro" value={money(entr-sai)} sub="Entradas menos saídas"/></div><div className="twoCols"><section className="panel"><PanelHead eyebrow="OPERAÇÃO" title="Estoque recente" text="Últimos itens cadastrados"/><Table rows={p.slice(0,6)} cols={['sku','name','price','stock']} format={{price:money}}/></section><section className="panel"><PanelHead eyebrow="CANAIS" title="Canais de venda" text="Conexões da sua empresa"/><div className="channelList">{marketplaces.map(m=><div className="channel" key={m.id}><MarketLogo id={m.id}/><div><b>{marketName(m.id)}</b><small>{m.connected?(m.account_name||'Conta conectada'):'Aguardando autorização'}</small></div><span className={m.connected?'pill success':'pill warn'}>{m.connected?'Conectado':'Conectar'}</span></div>)}</div></section></div></>}

function CompanyInfo({session,reload,notice}){
 const empty={trade_name:'',legal_name:'',cnpj:'',state_registration:'',tax_regime:'Simples Nacional',email:'',phone:'',responsible_name:'',rg:'',cpf:'',issuing_agency:'',cep:'',state:'RJ',city:'',address:'',number:'',complement:'',logo_url:''}
 const [form,setForm]=useState({...empty,...(session?.company||{})}),[lookupBusy,setLookupBusy]=useState(false)
 useEffect(()=>setForm({...empty,...(session?.company||{})}),[session])
 async function lookup(){const c=String(form.cnpj||'').replace(/\D/g,'');if(c.length!==14)return notice('Digite um CNPJ válido com 14 números');setLookupBusy(true);try{const r=await api.get(`/fiscal/cnpj/${c}`);setForm(v=>({...v,...Object.fromEntries(Object.entries(r.data||{}).filter(([,value])=>value!==''&&value!=null)),responsible_name:v.responsible_name,rg:v.rg,cpf:v.cpf,issuing_agency:v.issuing_agency}));notice('Dados públicos do CNPJ preenchidos. Confira e salve.')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível consultar o CNPJ')}finally{setLookupBusy(false)}}
 async function save(){try{await api.put('/company/me',form);await reload();notice('Informações da empresa atualizadas')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar')}}
 return <section className="panel companyPanel"><PanelHead eyebrow="EMPRESA" title="Informações da empresa" text="Comece pelo CNPJ. O CDM tenta preencher os dados públicos automaticamente e você só confere o restante."/>
 <div className="cnpjAssist"><div><b>Preenchimento rápido por CNPJ</b><span>Digite o CNPJ e deixe o CDM buscar razão social, nome fantasia e endereço.</span></div><button className="primary" disabled={lookupBusy} onClick={lookup}>{lookupBusy?'Buscando...':'Buscar dados pelo CNPJ'}</button></div>
 <div className="companyGrid">{[['Nome Fantasia','trade_name'],['Razão Social','legal_name'],['CNPJ','cnpj'],['Inscrição Estadual','state_registration'],['Regime de Tributação','tax_regime'],['E-mail','email'],['Telefone','phone'],['Nome do Responsável','responsible_name'],['RG','rg'],['CPF','cpf'],['Órgão Expedidor','issuing_agency'],['CEP','cep'],['UF','state'],['Cidade','city'],['Endereço','address'],['Número','number'],['Complemento','complement']].map(([label,key])=><Field key={key} label={label}><input value={form[key]||''} onChange={e=>setForm({...form,[key]:e.target.value})}/></Field>)}</div>
 <div className="subscriptionBox"><div><small>ASSINATURA</small><b>Plano {session?.subscription?.plan||'mensal'}</b><span>Situação: {statusPt(session?.subscription?.status)} · vencimento {fmtDate(session?.subscription?.expires_at)}</span></div><span className={['active','trial'].includes(session?.subscription?.status)?'pill success':'pill warn'}>{statusPt(session?.subscription?.status)}</span></div><button className="primary" onClick={save}>Salvar informações</button></section>
}

function BillingPage({billing,session,refresh,notice}){
 const price=Number(billing?.monthly_price||350),quote=billing?.quote||{},sub=billing?.subscription||session?.subscription||{}
 const founder=!!billing?.founder,fee=Number(billing?.implementation_fee||quote.implementation_fee||0),feeDue=Number(billing?.implementation_fee_due_now||quote.implementation_fee_due_now||0)
 const feeStatus=billing?.implementation_fee_status||quote.implementation_fee_status||'pending',stage=billing?.activation_stage||(feeDue>0?'implementation':'subscription'),active=!!billing?.active
 async function checkout(){try{const r=await api.post('/billing/checkout');if(r.data?.active){notice('Seu plano já está ativo');await refresh();return}if(!r.data?.checkout_url)return notice('O Mercado Pago não retornou o endereço de pagamento');location.href=r.data.checkout_url}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível abrir o pagamento')}}
 async function sync(){try{await api.post('/billing/sync');await refresh();notice('Pagamentos atualizados')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível atualizar agora')}}
 async function cancel(){if(!confirm('Cancelar a renovação desta assinatura?'))return;try{await api.post('/billing/cancel');await refresh();notice('Assinatura cancelada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível cancelar')}}
 const primaryLabel=active?'Plano ativo':stage==='implementation'?`Pagar implantação de ${money(feeDue)}`:`Ativar plano por ${money(price)} / mês`
 return <>
  <div className="pageTitle billingTitle"><div><span>PLANO CDM</span><h2>Ative seu acesso</h2><p>O CDM mostra somente o próximo passo. Pagamentos são processados pelo Mercado Pago.</p></div><span className={active?'statusBadge':'statusBadge bad'}>{active?'Ativo':'Configuração'}</span></div>
  <section className="panel billingV143">
   <div className="billingPlanIntro"><div><small>PLANO PROFISSIONAL</small><h2>{money(price)} <span>/ mês</span></h2><p>Estoque, veículos, vendas, financeiro, NF-e e integrações em uma conta por empresa.</p></div>{founder?<span className="billingFounder">★ Cliente fundador{billing?.founder_slot?` #${billing.founder_slot}`:''} · implantação grátis</span>:<span className={feeStatus==='paid'?'billingFee paid':'billingFee'}>{feeStatus==='paid'?'✓ Implantação paga':`Implantação única: ${money(fee)}`}</span>}</div>
   <div className="billingFlow">
    <article className={(founder||feeStatus==='paid'||feeDue===0)?'done':stage==='implementation'?'current':''}><b>{founder||feeStatus==='paid'||feeDue===0?'✓':'1'}</b><div><strong>Implantação</strong><span>{founder?'Grátis para os 10 primeiros clientes':feeStatus==='paid'?'Pagamento confirmado':`${money(fee)} uma única vez`}</span></div></article>
    <i/>
    <article className={active?'done':stage==='subscription'?'current':''}><b>{active?'✓':'2'}</b><div><strong>Mensalidade</strong><span>{active?'Assinatura ativa':`${money(price)} por mês`}</span></div></article>
    <i/>
    <article className={active?'done':''}><b>{active?'✓':'3'}</b><div><strong>Pronto</strong><span>{active?'Acesso liberado':'Liberação automática após confirmação'}</span></div></article>
   </div>
   {!billing?.checkout_provider_configured&&<div className="billingPlatformNotice"><b>Pagamento online em preparação</b><span>Você não precisa configurar nada. Assim que o Mercado Pago da plataforma estiver habilitado, este botão será liberado automaticamente.</span></div>}
   <div className="billingCheckoutBox"><div><small>PRÓXIMO PASSO</small><b>{active?'Nenhuma ação necessária':stage==='implementation'?'Pagar a implantação':'Ativar a assinatura mensal'}</b><span>{active?'Seu plano está funcionando normalmente.':stage==='implementation'?`Depois da confirmação, você segue para a mensalidade de ${money(price)}.`:'A renovação será mensal pelo Mercado Pago.'}</span></div><button className="primary" disabled={!billing?.checkout_provider_configured||active} onClick={checkout}>{primaryLabel} →</button></div>
   <div className="billingSafe"><span>🔒 O pagamento acontece no ambiente seguro do Mercado Pago.</span><button className="ghost" onClick={sync}>Atualizar pagamentos</button>{sub?.external_subscription_id&&<button className="ghost dangerOutline" onClick={cancel}>Cancelar renovação</button>}</div>
  </section>
 </>
}
// CDM QR CODE V2
function QRCodeModule({products=[],locations=[]}){
 const [mode,setMode]=useState('product'),[selectedId,setSelectedId]=useState(''),[search,setSearch]=useState('')
 const items=mode==='product'?products:locations
 const filtered=useMemo(()=>{
   const q=search.trim().toLowerCase()
   if(!q)return items
   return items.filter(x=>mode==='product'
     ? `${x.sku||''} ${x.name||''} ${x.brand||''} ${x.model||''} ${x.oem||''}`.toLowerCase().includes(q)
     : `${x.code||''} ${x.description||''} ${x.warehouse||''} ${x.aisle||''} ${x.shelf||''} ${x.bin||''}`.toLowerCase().includes(q))
 },[items,search,mode])

 useEffect(()=>{
   if(!items.length){setSelectedId('');return}
   if(!items.some(x=>String(x.id)===String(selectedId)))setSelectedId(String(items[0].id))
 },[mode,products,locations])

 const item=items.find(x=>String(x.id)===String(selectedId))
 const payload=item
   ? mode==='product'
     ? `CDM|PECA|${item.id}|${item.sku||''}|${item.name||''}`
     : `CDM|LOCAL|${item.id}|${item.code||''}|${item.description||''}`
   : 'CDM Desmontes'

 function copyCode(){
   if(!item)return
   navigator.clipboard?.writeText(payload)
 }

 function printQr(){if(item)window.print()}

 function downloadSvg(){
   if(!item)return
   const svg=document.querySelector('.qrAdvancedCode svg')
   if(!svg)return
   const xml=new XMLSerializer().serializeToString(svg)
   const blob=new Blob([xml],{type:'image/svg+xml;charset=utf-8'})
   const a=document.createElement('a')
   a.href=URL.createObjectURL(blob)
   const raw=mode==='product'?(item.sku||`peca-${item.id}`):(item.code||`local-${item.id}`)
   a.download=`QR-${String(raw).replace(/[^a-z0-9_-]+/gi,'-')}.svg`
   a.click()
   setTimeout(()=>URL.revokeObjectURL(a.href),500)
 }

 const locationText=item&&mode==='location'
   ? [item.warehouse,item.aisle,item.shelf,item.bin].filter(Boolean).join(' › ')
   : ''

 return <div className="qrAdvancedPage">
   <div className="pageTitle">
     <div><span>IDENTIFICAÇÃO INTELIGENTE</span><h2>Código QR</h2><p>Gere QR para peças e localizações do estoque, pronto para imprimir ou baixar.</p></div>
     <span className="pill neutral">{mode==='product'?`${products.length} peças`:`${locations.length} localizações`}</span>
   </div>

   <div className="qrModeTabs">
     <button className={mode==='product'?'active':''} onClick={()=>{setMode('product');setSearch('')}}>QR de peça</button>
     <button className={mode==='location'?'active':''} onClick={()=>{setMode('location');setSearch('')}}>QR de localização</button>
   </div>

   <div className="twoCols qrAdvancedLayout">
     <section className="panel qrControlPanel">
       <PanelHead eyebrow="SELEÇÃO" title={mode==='product'?'Escolha a peça':'Escolha a localização'} text="Pesquise e selecione o item que vai receber o código."/>
       <Field label="Pesquisar"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder={mode==='product'?'SKU, peça, marca, modelo ou OEM...':'Código, nome, depósito ou corredor...'}/></Field>
       <Field label={mode==='product'?'Peça':'Localização'}><select value={selectedId} onChange={e=>setSelectedId(e.target.value)}><option value="">Selecione...</option>{filtered.map(x=><option key={x.id} value={x.id}>{mode==='product'?`${x.sku||'#'+x.id} — ${x.name||'Peça'}`:`${x.code||'#'+x.id} — ${x.description||'Localização'}`}</option>)}</select></Field>

       <div className="qrUseCards">
         <div><b>1</b><span>Selecione</span><small>peça ou local</small></div>
         <div><b>2</b><span>Gere</span><small>QR exclusivo</small></div>
         <div><b>3</b><span>Imprima</span><small>e cole no estoque</small></div>
       </div>

       <div className="qrTips">
         <b>Uso recomendado</b>
         <span>• Identificação rápida de peças</span>
         <span>• Endereçamento de prateleiras e caixas</span>
         <span>• Conferência durante separação e expedição</span>
       </div>
     </section>

     <section className="panel qrPrintPanel">
       {!item?<div className="emptyState">Selecione um item para gerar o Código QR.</div>:<>
         <div className="qrAdvancedCard">
           <div className="qrAdvancedCode"><QRCodeSVG value={payload} size={220} level="M" includeMargin/></div>
           <div className="qrAdvancedData">
             <small>{mode==='product'?'PEÇA CDM':'LOCALIZAÇÃO CDM'}</small>
             <strong>{mode==='product'?(item.sku||`#${item.id}`):(item.code||`#${item.id}`)}</strong>
             <h3>{mode==='product'?(item.name||'Peça'):(item.description||'Localização')}</h3>
             {mode==='product'
               ? <><p>{[item.brand,item.model,item.year].filter(Boolean).join(' ')||'Veículo não informado'}</p>{item.oem&&<span>OEM: {item.oem}</span>}</>
               : <><p>{locationText||'Sem detalhamento de posição'}</p>{item.max_quantity>0&&<span>Limite: {item.max_quantity} peças</span>}</>}
           </div>
         </div>
         <div className="qrPayload"><small>CONTEÚDO DO QR</small><code>{payload}</code></div>
         <div className="qrActions">
           <button className="ghost" onClick={copyCode}>Copiar código</button>
           <button className="ghost" onClick={downloadSvg}>↓ Baixar SVG</button>
           <button className="primary" onClick={printQr}>▣ Imprimir QR</button>
         </div>
       </>}
     </section>
   </div>
 </div>
}

function CadastrosHome({setTab}){const cards=[['▰','Cadastro de Sucatas','vehicle-create'],['⚙','Cadastro de Peças','product-create'],['◆','Grupo de peças','part-groups'],['♣','Clientes','customers'],['●','Localizações','locations'],['▰','Transportadoras','carriers'],['♟','Vendedores','sellers'],['♙','Fornecedores','suppliers'],['⌁','Configuração Tributária','tax']];return <><div className="pageTitle"><div><span>BASE CADASTRAL</span><h2>Cadastros</h2><p>Organize todos os dados essenciais da operação.</p></div></div><div className="moduleCards">{cards.map(([i,t,k])=><button className="moduleCard clickable" key={k} onClick={()=>setTab(k)}><div className="moduleIcon">{i}</div><div><h3>{t}</h3><p>Abrir cadastro e gerenciamento.</p><span className="pill neutral">Acessar</span></div></button>)}</div></>}

function VehicleBrandModel({form,setForm,brands=[]}){const [models,setModels]=useState([]),[customModel,setCustomModel]=useState(false);const availableBrands=brands?.length?brands:FALLBACK_VEHICLE_BRANDS;useEffect(()=>{let active=true;setModels([]);if(!form.brand){return}api.get('/vehicle-catalog/models',{params:{brand:form.brand}}).then(r=>{if(active){setModels(r.data.models||[]);if(form.model&&!(r.data.models||[]).includes(form.model))setCustomModel(true)}}).catch(()=>{if(active)setModels([])});return()=>{active=false}},[form.brand]);return <><Field label="Marca"><select value={form.brand||''} onChange={e=>{setForm({...form,brand:e.target.value,model:''});setCustomModel(false)}}><option value="">Selecione a marca...</option>{availableBrands.map(b=><option key={b} value={b}>{b}</option>)}</select></Field><Field label="Modelo">{customModel?<div className="inlineInput"><input autoFocus value={form.model||''} onChange={e=>setForm({...form,model:e.target.value})} placeholder="Digite o modelo"/><button type="button" className="ghost mini" onClick={()=>{setCustomModel(false);setForm({...form,model:''})}}>Lista</button></div>:<select value={form.model||''} disabled={!form.brand} onChange={e=>{if(e.target.value==='__custom__'){setCustomModel(true);setForm({...form,model:''})}else setForm({...form,model:e.target.value})}}><option value="">{form.brand?'Selecione o modelo...':'Escolha a marca primeiro'}</option>{models.map(m=><option key={m} value={m}>{m}</option>)}<option value="__custom__">Outro / digitar manualmente...</option></select>}</Field></>}


function Vehicle360({vehicle,listings=[],onClose,refresh,notice}){
 const [info,setInfo]=useState(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[photos,setPhotos]=useState([]),[photoBusy,setPhotoBusy]=useState(false)
 const [expenseForm,setExpenseForm]=useState({category:'Guincho',description:'',amount:'',expense_date:''}),[expenseBusy,setExpenseBusy]=useState(false),[expenseError,setExpenseError]=useState('')
 useEffect(()=>{
   let active=true
   setBusy(true);setError('');setPhotos([])
   api.get(`/vehicles/${vehicle.id}/photos`).then(r=>{if(active)setPhotos(r.data||[])}).catch(()=>{})
   api.get(`/vehicles/${vehicle.id}/overview`).then(r=>{if(active)setInfo(r.data)}).catch(e=>{if(active)setError(erroPt(e.response?.data?.detail)||'Não foi possível carregar a visão 360')}).finally(()=>{if(active)setBusy(false)})
   return()=>{active=false}
 },[vehicle.id])
 async function reloadOverview(){
  const r=await api.get(`/vehicles/${vehicle.id}/overview`);setInfo(r.data)
 }
 async function reloadVehiclePhotos(){
  const r=await api.get(`/vehicles/${vehicle.id}/photos`)
  setPhotos(r.data||[])
 }
 async function addVehiclePhotos(e){
  const files=Array.from(e.target.files||[])
  e.target.value=''
  if(!files.length)return
  const currentCount=photos.length||(vehicle.photo_data?1:0)
  const slots=Math.max(0,15-currentCount)
  if(slots<=0){notice?.('Limite de 15 fotos por sucata atingido');return}
  if(files.length>slots)notice?.(`So cabem mais ${slots} foto(s).`)
  setPhotoBusy(true)
  try{
   const selected=files.slice(0,slots)
   let added=0
   for(const file of selected){
    if(!String(file.type||'').startsWith('image/'))continue
    const prepared=await prepareVehiclePhoto(file)
    await api.post(`/vehicles/${vehicle.id}/photos`,{photo_data:prepared})
    added++
   }
   await reloadVehiclePhotos()
   await reloadOverview()
   if(refresh)await refresh()
   notice?.(added===1?'1 foto adicionada à sucata':`${added} fotos adicionadas à sucata`)
  }catch(e){
   notice?.(erroPt(e.response?.data?.detail)||'Não foi possível adicionar as fotos')
  }finally{
   setPhotoBusy(false)
  }
 }
 async function removeSavedVehiclePhoto(photo){
  if(!confirm('Excluir esta foto da sucata?'))return
  setPhotoBusy(true)
  try{
   if(photo.legacy||!photo.id){
    await api.put(`/vehicles/${vehicle.id}/photo`,{photo_data:''})
   }else{
    await api.delete(`/vehicles/${vehicle.id}/photos/${photo.id}`)
   }
   await reloadVehiclePhotos()
   await reloadOverview()
   if(refresh)await refresh()
   notice?.('Foto excluída')
  }catch(e){
   notice?.(erroPt(e.response?.data?.detail)||'Não foi possível excluir a foto')
  }finally{
   setPhotoBusy(false)
  }
 }
 async function makeSavedVehiclePhotoPrimary(photo){
  if(photo.is_primary||photo.legacy||!photo.id)return
  setPhotoBusy(true)
  try{
   await api.put(`/vehicles/${vehicle.id}/photos/${photo.id}/primary`)
   await reloadVehiclePhotos()
   await reloadOverview()
   if(refresh)await refresh()
   notice?.('Foto principal atualizada')
  }catch(e){
   notice?.(erroPt(e.response?.data?.detail)||'Não foi possível definir a foto principal')
  }finally{
   setPhotoBusy(false)
  }
 }
 async function addVehicleExpense(){
  const amount=Number(expenseForm.amount||0)
  if(amount<=0){setExpenseError('Informe um valor maior que zero');return}
  setExpenseBusy(true);setExpenseError('')
  try{
   await api.post(`/vehicles/${vehicle.id}/expenses`,{...expenseForm,amount})
   await reloadOverview()
   setExpenseForm({category:'Guincho',description:'',amount:'',expense_date:''})
  }catch(e){setExpenseError(erroPt(e.response?.data?.detail)||'Não foi possível adicionar a despesa')}
  finally{setExpenseBusy(false)}
 }
 async function removeVehicleExpense(id){
  if(!confirm('Excluir esta despesa do veículo?'))return
  setExpenseBusy(true);setExpenseError('')
  try{await api.delete(`/vehicles/${vehicle.id}/expenses/${id}`);await reloadOverview()}
  catch(e){setExpenseError(erroPt(e.response?.data?.detail)||'Não foi possível excluir a despesa')}
  finally{setExpenseBusy(false)}
 }
 const r=info?.result||{},p=info?.parts||{},i=info?.investment||{},v=info?.vehicle||vehicle
 const gallery=photos.length?photos:(v.photo_data?[{id:0,photo_data:v.photo_data,is_primary:true,legacy:true}]:[])
 const primaryPhoto=gallery.find(x=>x.is_primary)?.photo_data||v.photo_data||gallery[0]?.photo_data||''
 const resultClass=Number(r.realized_result||0)>=0?'positive':'negative'
 const potentialClass=Number(r.potential_profit||0)>=0?'positive':'negative'
 const productIds=new Set((info?.products||[]).map(x=>Number(x.id)))
 const vehicleListings=(listings||[]).filter(x=>productIds.has(Number(x.product_id)))
 const publishedCount=vehicleListings.filter(x=>String(x.status||'').toLowerCase()==='published').length
 const hasListing=vehicleListings.length>0
 const dismantlingStatus=String(info?.dismantling?.status||'pending').toLowerCase()
 const flow=[
  {key:'buy',icon:'1',title:'Compra',done:true,active:false,text:money(i.acquisition_value||0)},
  {key:'dismantle',icon:'2',title:'Desmontagem',done:['completed','finished'].includes(dismantlingStatus),active:['in_progress','dismantling'].includes(dismantlingStatus),text:info?.dismantling?.status_label||'Pendente'},
  {key:'parts',icon:'3',title:'Cadastro das peças',done:Number(p.registered_skus||0)>0,active:false,text:`${Number(p.registered_skus||0)} SKU(s)`},
  {key:'stock',icon:'4',title:'Estoque',done:Number(p.registered_skus||0)>0,active:Number(p.stock_qty||0)>0,text:`${Number(p.stock_qty||0)} un.`},
  {key:'ads',icon:'5',title:'Anúncios',done:publishedCount>0,active:publishedCount===0&&hasListing,text:publishedCount>0?`${publishedCount} publicado(s)`:hasListing?'Em preparação':'Nenhum'},
  {key:'sales',icon:'6',title:'Venda',done:Number(p.sold_qty||0)>0,active:false,text:`${Number(p.sold_qty||0)} vendida(s)`},
  {key:'result',icon:'7',title:'Resultado',done:Number(r.revenue||0)>0||Number(r.estimated_stock_value||0)>0,active:false,text:money(r.revenue||0)}
 ]
 return <div className="modalBackdrop vehicle360Backdrop" onMouseDown={e=>e.target===e.currentTarget&&onClose()}>
  <div className="v8Modal vehicle360Modal">
   <div className="modalHead vehicle360Head"><div style={{display:'flex',alignItems:'center',gap:14,flexWrap:'wrap'}}>{primaryPhoto&&<img src={primaryPhoto} alt="Foto da sucata" style={{width:96,height:70,objectFit:'cover',borderRadius:12,border:'1px solid var(--border)'}}/>}<div><small>VISÃO 360 DO VEÍCULO</small><h2>{[v.brand,v.model,v.year].filter(Boolean).join(' ')||`Veículo #${v.id}`}</h2><p>{v.plate?`Placa ${v.plate} · `:''}{info?.vehicle?.status_label||statusPt(v.status)}</p></div></div><button className="iconClose" onClick={onClose}>×</button></div>
   <div className="modalBody vehicle360Body">
    {busy?<div className="vehicle360Loading">Calculando investimento, vendas e estoque...</div>:error?<div className="error">{error}</div>:<>
     <section style={{display:'grid',gap:10}}>
      <div className="vehicle360SectionTitle">
       <div><small>FOTOS DA SUCATA</small><h3>Gerenciar galeria</h3></div>
       <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
        <span>{gallery.length}/15 fotos</span>
        {gallery.length<15&&<label className="primary" style={{cursor:photoBusy?'wait':'pointer',padding:'9px 12px',display:'inline-flex',alignItems:'center',gap:6,opacity:photoBusy?.65:1}}>
         + Adicionar fotos
         <input type="file" accept="image/*" multiple disabled={photoBusy} onChange={addVehiclePhotos} style={{display:'none'}}/>
        </label>}
       </div>
      </div>
      {gallery.length?<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(155px,1fr))',gap:10}}>
       {gallery.map((photo,index)=><div key={photo.id||`legacy-${index}`} style={{position:'relative',border:'1px solid var(--border)',borderRadius:12,overflow:'hidden',background:'var(--panel)'}}>
        <img src={photo.photo_data} alt={`Foto ${index+1} da sucata`} style={{width:'100%',height:115,objectFit:'cover',display:'block'}}/>
        <div style={{padding:8,display:'grid',gap:6}}>
         <small style={{fontWeight:800}}>{photo.is_primary?'★ PRINCIPAL':`FOTO ${index+1}`}</small>
         <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
          {!photo.is_primary&&!photo.legacy&&<button type="button" className="ghost mini" disabled={photoBusy} onClick={()=>makeSavedVehiclePhotoPrimary(photo)}>★ Principal</button>}
          <button type="button" className="ghost mini dangerOutline" disabled={photoBusy} onClick={()=>removeSavedVehiclePhoto(photo)}>Excluir</button>
         </div>
        </div>
       </div>)}
      </div>:<div className="emptyState">Nenhuma foto cadastrada. Use “Adicionar fotos” para incluir imagens da sucata.</div>}
     </section>
     <div className="vehicle360Status">
      <div><small>SITUAÇÃO DO VEÍCULO</small><b>{info.vehicle.status_label}</b></div>
      <div><small>DESMONTAGEM</small><b>{info.dismantling.status_label}</b></div>
      <div><small>RECUPERADO DO INVESTIMENTO</small><b>{Number(r.recovery_percent||0).toLocaleString('pt-BR',{maximumFractionDigits:1})}%</b></div>
     </div>

     <div className="vehicle360SectionTitle"><div><small>FINANCEIRO</small><h3>Investimento e retorno</h3></div><span>Valores calculados automaticamente</span></div>
     <section className="vehicleFlowSection">
    <div className="vehicleFlowHead">
     <div><small>CICLO DO VEÍCULO</small><h3>Compra → Resultado</h3></div>
     <span>{flow.filter(x=>x.done).length} de {flow.length} etapas com movimentação</span>
    </div>
    <div className="vehicleFlow">
     {flow.map((step,idx)=><React.Fragment key={step.key}>
      <div className={'vehicleFlowStep '+(step.done?'done':step.active?'active':'pending')}>
       <div className="vehicleFlowCircle">{step.done?'✓':step.icon}</div>
       <div><b>{step.title}</b><small>{step.text}</small></div>
      </div>
      {idx<flow.length-1&&<div className={'vehicleFlowLine '+(step.done?'done':'')}></div>}
     </React.Fragment>)}
    </div>
    <p className="vehicleFlowNote">O fluxo é atualizado automaticamente conforme peças, anúncios e vendas deste veículo são registrados no CDM.</p>
   </section>
   <div className="vehicle360Metrics">
      <div><small>Valor de compra</small><b>{money(i.acquisition_value)}</b></div>
      <div><small>Outros custos do cadastro</small><b>{money(i.other_costs)}</b></div><div><small>Despesas lançadas</small><b>{money(i.vehicle_expenses)}</b></div>
      <div className="featured"><small>Total investido</small><b>{money(i.total_invested)}</b></div>
      <div><small>Faturamento gerado</small><b>{money(r.revenue)}</b></div>
      <div className={resultClass}><small>Resultado realizado</small><b>{money(r.realized_result)}</b><em>Faturamento - investimento</em></div>
      <div><small>Valor estimado do estoque</small><b>{money(r.estimated_stock_value)}</b></div>
      <div className="featured"><small>Retorno potencial total</small><b>{money(r.potential_total)}</b><em>Vendido + estoque atual</em></div>
      <div className={potentialClass}><small>Lucro potencial</small><b>{money(r.potential_profit)}</b><em>Potencial - investimento</em></div>
     </div>

     <section className="vehicleExpenseSection">
      <div className="vehicle360SectionTitle"><div><small>DESPESAS DO VEÍCULO</small><h3>Custos adicionais detalhados</h3></div><span>{info.expenses?.length||0} lançamento(s) · {money(i.vehicle_expenses||0)}</span></div>
      <div className="vehicleExpenseForm">
       <Field label="Categoria"><select value={expenseForm.category} onChange={e=>setExpenseForm({...expenseForm,category:e.target.value})}><option>Guincho</option><option>Combustível</option><option>Documentação</option><option>Mão de obra</option><option>Oficina</option><option>Transporte</option><option>Taxas</option><option>Limpeza</option><option>Outros</option></select></Field>
       <Field label="Descrição"><input value={expenseForm.description} onChange={e=>setExpenseForm({...expenseForm,description:e.target.value})} placeholder="Ex.: Guincho para buscar o veículo"/></Field>
       <Field label="Valor"><input type="number" min="0" step="0.01" value={expenseForm.amount} onChange={e=>setExpenseForm({...expenseForm,amount:e.target.value})} placeholder="0,00"/></Field>
       <Field label="Data"><input type="date" value={expenseForm.expense_date} onChange={e=>setExpenseForm({...expenseForm,expense_date:e.target.value})}/></Field>
       <button className="primary vehicleExpenseAdd" disabled={expenseBusy} onClick={addVehicleExpense}>{expenseBusy?'Salvando...':'+ Adicionar despesa'}</button>
      </div>
      {expenseError&&<div className="error vehicleExpenseError">{expenseError}</div>}
      {info.expenses?.length?<div className="vehicleExpenseList">
       {info.expenses.map(x=><div className="vehicleExpenseRow" key={x.id}>
        <div><b>{x.category}</b><small>{x.description||'Sem descrição'}{x.expense_date?` · ${x.expense_date.split('-').reverse().join('/')}`:''}</small></div>
        <strong>{money(x.amount)}</strong>
        <button className="ghost dangerOutline" disabled={expenseBusy} onClick={()=>removeVehicleExpense(x.id)}>Excluir</button>
       </div>)}
      </div>:<div className="vehicleExpenseEmpty">Nenhuma despesa detalhada lançada para este veículo.</div>}
      <p className="vehicleExpenseHelp">As despesas lançadas entram automaticamente no total investido, no resultado realizado e no lucro potencial da Visão 360.</p>
     </section>

     <div className="vehicle360SectionTitle"><div><small>PEÇAS</small><h3>Ciclo das peças deste veículo</h3></div><span>{p.registered_skus||0} SKUs vinculados</span></div>
     <div className="vehicle360PartMetrics">
      <div><span>▦</span><small>Peças cadastradas</small><b>{p.registered_units||0}</b></div>
      <div><span>✓</span><small>Peças vendidas</small><b>{p.sold_qty||0}</b></div>
      <div><span>●</span><small>Peças em estoque</small><b>{p.stock_qty||0}</b></div>
      <div><span>▤</span><small>SKUs com estoque</small><b>{p.skus_in_stock||0}</b></div>
     </div>

     <div className="vehicle360SectionTitle"><div><small>DETALHAMENTO</small><h3>Peças vinculadas ao veículo</h3></div><span>Preço atual usado na estimativa do estoque</span></div>
     {info.products?.length?<div className="vehicle360Parts">
      <div className="vehicle360PartsHead"><span>Peça</span><span>Vendidas</span><span>Estoque</span><span>Faturamento</span><span>Potencial estoque</span></div>
      {info.products.map(x=><div className="vehicle360PartRow" key={x.id}><div><b>{x.name}</b><small>SKU {x.sku||'—'} · {money(x.price)}</small></div><span>{x.sold_qty}</span><span>{x.stock}</span><strong>{money(x.revenue)}</strong><strong>{money(x.estimated_stock_value)}</strong></div>)}
     </div>:<div className="emptyState">Ainda não existem peças vinculadas a este veículo.</div>}

     <div className="vehicle360Note">O valor do estoque restante é uma estimativa baseada no preço de venda atual das peças. O resultado realizado considera o faturamento já gerado menos todo o investimento do veículo.</div>
    </>}
   </div>
   <div className="modalFoot"><button className="primary" onClick={onClose}>Fechar visão 360</button></div>
  </div>
 </div>
}

function VehicleEditModal({vehicle,brands,onClose,refresh,notice}){
 const [form,setForm]=useState({plate:vehicle.plate||'',brand:vehicle.brand||'',model:vehicle.model||'',year:vehicle.year||new Date().getFullYear(),vin:vehicle.vin||'',renavam:vehicle.renavam||'',fuel:vehicle.fuel||'Flex',transmission:vehicle.transmission||'Automático',color:vehicle.color||'',acquisition_value:vehicle.acquisition_value??'',other_costs:vehicle.other_costs??''})
 const [photos,setPhotos]=useState([]),[photosLoading,setPhotosLoading]=useState(true),[photosBusy,setPhotosBusy]=useState(false),[saving,setSaving]=useState(false)

 async function reloadPhotos(){
  try{
   const r=await api.get(`/vehicles/${vehicle.id}/photos`)
   setPhotos(r.data||[])
  }catch(e){
   notice(erroPt(e.response?.data?.detail)||'Não foi possível carregar as fotos da sucata')
  }finally{setPhotosLoading(false)}
 }
 useEffect(()=>{reloadPhotos()},[vehicle.id])

 async function addPhotos(e){
  const files=Array.from(e.target.files||[])
  e.target.value=''
  if(!files.length||photosBusy)return
  const slots=15-photos.length
  if(slots<=0){notice('Limite de 15 fotos por sucata atingido');return}
  if(files.length>slots)notice(`Só cabem mais ${slots} foto(s). As demais não serão adicionadas.`)
  setPhotosBusy(true)
  try{
   let added=0
   for(const file of files.slice(0,slots)){
    if(!String(file.type||'').startsWith('image/'))continue
    const prepared=await prepareVehiclePhoto(file)
    await api.post(`/vehicles/${vehicle.id}/photos`,{photo_data:prepared})
    added++
   }
   await reloadPhotos()
   await refresh()
   if(added)notice(`${added} foto(s) adicionada(s) com sucesso`)
  }catch(e){
   notice(erroPt(e.response?.data?.detail)||'Não foi possível adicionar as fotos')
  }finally{setPhotosBusy(false)}
 }

 async function makePrimary(photo){
  if(photo.is_primary||photosBusy)return
  setPhotosBusy(true)
  try{
   if(photo.legacy){
    notice('Esta foto já é a principal')
   }else{
    await api.put(`/vehicles/${vehicle.id}/photos/${photo.id}/primary`)
    await reloadPhotos();await refresh();notice('Foto principal atualizada')
   }
  }catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível definir a foto principal')}
  finally{setPhotosBusy(false)}
 }

 async function removePhoto(photo){
  if(photosBusy)return
  if(!confirm('Remover esta foto da sucata?'))return
  setPhotosBusy(true)
  try{
   if(photo.legacy)await api.put(`/vehicles/${vehicle.id}/photo`,{photo_data:''})
   else await api.delete(`/vehicles/${vehicle.id}/photos/${photo.id}`)
   await reloadPhotos();await refresh();notice('Foto removida')
  }catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível remover a foto')}
  finally{setPhotosBusy(false)}
 }

 async function save(){
  if(saving)return
  setSaving(true)
  try{
   const payload={plate:form.plate||'',vin:form.vin||'',renavam:form.renavam||'',brand:form.brand||'',model:form.model||'',year:form.year?Number(form.year):null,fuel:form.fuel||'',transmission:form.transmission||'',color:form.color||'',acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)}
   await api.put(`/vehicles/${vehicle.id}`,payload);await refresh();notice('Sucata atualizada com sucesso');onClose()
  }catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao atualizar sucata')}
  finally{setSaving(false)}
 }
 return <div className="modalBackdrop vehicleEditBackdrop" onMouseDown={e=>e.target===e.currentTarget&&onClose()}><div className="v8Modal large vehicleEditWithPhotos">
   <div className="modalHead"><div><small>EDIÇÃO DE SUCATA</small><h2>Editar veículo #{vehicle.id}</h2><p>Corrija os dados cadastrados e complete as fotos quando quiser.</p></div><button className="iconClose" onClick={onClose}>×</button></div>
   <div className="modalBody">
    <div className="formGrid three">
     <Field label="Placa"><input value={form.plate} onChange={e=>setForm({...form,plate:e.target.value.toUpperCase()})}/></Field><VehicleBrandModel form={form} setForm={setForm} brands={brands}/>
     <Field label="Ano"><input type="number" min="1971" max={new Date().getFullYear()+1} value={form.year} onChange={e=>setForm({...form,year:e.target.value})}/></Field>
     <Field label="Chassi / VIN"><input value={form.vin} onChange={e=>setForm({...form,vin:e.target.value.toUpperCase()})}/></Field><Field label="Renavam"><input value={form.renavam} onChange={e=>setForm({...form,renavam:e.target.value})}/></Field>
     <Field label="Combustível"><select value={form.fuel} onChange={e=>setForm({...form,fuel:e.target.value})}><option>Flex</option><option>Gasolina</option><option>Etanol</option><option>Diesel</option><option>Híbrido</option><option>Elétrico</option><option>GNV</option></select></Field>
     <Field label="Câmbio"><select value={form.transmission} onChange={e=>setForm({...form,transmission:e.target.value})}><option>Automático</option><option>Manual</option><option>CVT</option><option>Automatizado</option></select></Field>
     <Field label="Cor"><input value={form.color} onChange={e=>setForm({...form,color:e.target.value})}/></Field><Field label="Valor de aquisição"><input type="number" step="0.01" value={form.acquisition_value} onChange={e=>setForm({...form,acquisition_value:e.target.value})}/></Field><Field label="Outros custos"><input type="number" step="0.01" value={form.other_costs} onChange={e=>setForm({...form,other_costs:e.target.value})}/></Field>
    </div>

    <section className="vehicleEditPhotosSection">
     <div className="vehicleEditPhotosHead">
      <div><small>FOTOS DA SUCATA</small><h3>Galeria do veículo</h3><p>Adicione fotos a qualquer momento. Marque uma delas como principal para aparecer no card.</p></div>
      <span>{photos.length}/15</span>
     </div>

     {photosLoading?<div className="vehicleEditPhotosLoading">Carregando fotos...</div>:<>
      {photos.length<15&&<label className={`vehicleEditPhotoAdd ${photosBusy?'disabled':''}`}>
       <input type="file" accept="image/*" multiple disabled={photosBusy} onChange={addPhotos}/>
       <b>＋ {photosBusy?'Enviando fotos...':'Adicionar fotos'}</b>
       <span>Você pode selecionar várias imagens de uma vez</span>
      </label>}

      {!!photos.length?<div className="vehicleEditPhotoGrid">{photos.map((photo,index)=><article className={photo.is_primary?'primary':''} key={`${photo.id}-${index}`}>
       <div className="vehicleEditPhotoImage"><img src={photo.photo_data} alt={`Foto ${index+1} da sucata`}/>{photo.is_primary&&<span>Principal</span>}</div>
       <div className="vehicleEditPhotoActions">
        <button type="button" className="ghost" disabled={photosBusy||photo.is_primary} onClick={()=>makePrimary(photo)}>{photo.is_primary?'✓ Principal':'☆ Tornar principal'}</button>
        <button type="button" className="ghost danger" disabled={photosBusy} onClick={()=>removePhoto(photo)}>Remover</button>
       </div>
      </article>)}</div>:<div className="vehicleEditNoPhotos"><b>Nenhuma foto cadastrada</b><span>Use o botão acima para adicionar a primeira foto deste veículo.</span></div>}
     </>}
    </section>
   </div>
   <div className="modalFoot"><button className="ghost" onClick={onClose}>Cancelar</button><button className="primary" disabled={saving||photosBusy} onClick={save}>{saving?'Salvando...':'Salvar alterações'}</button></div>
  </div></div>
}


async function prepareVehiclePhoto(file){
 const src=await new Promise((resolve,reject)=>{
  const r=new FileReader()
  r.onload=()=>resolve(r.result)
  r.onerror=()=>reject(new Error('Nao foi possivel ler a foto'))
  r.readAsDataURL(file)
 })
 const img=await new Promise((resolve,reject)=>{
  const el=new Image()
  el.onload=()=>resolve(el)
  el.onerror=()=>reject(new Error('Foto invalida'))
  el.src=src
 })
 const max=1000
 const scale=Math.min(1,max/Math.max(img.width,img.height))
 const w=Math.max(1,Math.round(img.width*scale))
 const h=Math.max(1,Math.round(img.height*scale))
 const canvas=document.createElement('canvas')
 canvas.width=w
 canvas.height=h
 const ctx=canvas.getContext('2d')
 ctx.imageSmoothingEnabled=true
 ctx.imageSmoothingQuality='high'
 ctx.drawImage(img,0,0,w,h)
 return canvas.toDataURL('image/jpeg',0.75)
}

function Vehicles({data,refresh,notice,brands=[],listings=[],createOnly=false}){
 const empty={plate:'',brand:'',model:'',year:new Date().getFullYear(),vin:'',renavam:'',fuel:'Flex',transmission:'Automático',color:'',acquisition_value:'',other_costs:''}
 const [form,setForm]=useState(empty),[overview,setOverview]=useState(null),[search,setSearch]=useState(''),[editVehicle,setEditVehicle]=useState(null),[saving,setSaving]=useState(false),[photoData,setPhotoData]=useState([]),[photoBusy,setPhotoBusy]=useState(false)
 const filtered=useMemo(()=>{const q=search.trim().toLowerCase();if(!q)return data;return data.filter(v=>[v.plate,v.brand,v.model,v.year,v.status].some(x=>String(x||'').toLowerCase().includes(q)))},[data,search])
 const totalInvested=Number(form.acquisition_value||0)+Number(form.other_costs||0)

 async function chooseVehiclePhoto(e){
  const files=Array.from(e.target.files||[])
  e.target.value=''
  if(!files.length)return
  const slots=15-photoData.length
  if(slots<=0){notice('Voce ja adicionou o limite de 15 fotos');return}
  if(files.length>slots)notice(`So cabem mais ${slots} foto(s). As demais nao serao adicionadas.`)
  const selected=files.slice(0,slots)
  setPhotoBusy(true)
  try{
   const prepared=[]
   for(const file of selected){
    if(!String(file.type||'').startsWith('image/'))continue
    const data=await prepareVehiclePhoto(file)
    if(data.length<=1500000)prepared.push(data)
   }
   setPhotoData(current=>[...current,...prepared].slice(0,15))
   if(!prepared.length)notice('Nenhuma imagem valida foi adicionada')
  }catch(err){
   notice(err?.message||'Nao foi possivel preparar as fotos')
  }finally{
   setPhotoBusy(false)
  }
 }

 function removeVehiclePhoto(index){
  setPhotoData(current=>current.filter((_,i)=>i!==index))
 }

 async function add(){
  if(saving)return
  if(!form.brand){notice('Selecione a marca do veículo');return}
  if(!form.model){notice('Selecione ou informe o modelo do veículo');return}
  setSaving(true)
  try{
   const created=await api.post('/vehicles',{...form,year:form.year?Number(form.year):null,acquisition_value:Number(form.acquisition_value||0),other_costs:Number(form.other_costs||0)})
   if(photoData.length&&created?.data?.id){
    for(const photo of photoData){
     await api.post(`/vehicles/${created.data.id}/photos`,{photo_data:photo})
    }
   }
   setForm({...empty,year:new Date().getFullYear()});setPhotoData([])
   await refresh()
   notice('Sucata cadastrada com sucesso')
  }catch(e){
   const detail=e.response?.data?.detail
   const msg=typeof detail==='string'?detail:(Array.isArray(detail)?detail.map(x=>x.msg).filter(Boolean).join(' · '):'')
   notice(msg||erroPt(detail)||`Erro ao cadastrar sucata${e.response?.status?` (HTTP ${e.response.status})`:''}`)
  }finally{setSaving(false)}
 }

 return <>
  <section className="panel vehicleRegisterPanel">
   <div className="vehicleRegisterHero">
    <div>
     <span>CADASTRO DE SUCATA</span>
     <h2>Novo veículo</h2>
     <p>Preencha os dados principais da sucata. O cadastro foi reorganizado para ficar mais rápido e fácil de conferir.</p>
    </div>
    <div className="vehicleRegisterHeroBadge"><b>Cadastro rápido</b><small>Dados + fotos + custos</small></div>
   </div>

   <div className="vehicleFormSection">
    <div className="vehicleFormSectionHead">
     <div className="vehicleFormIndex">01</div>
     <div><b>Dados do veículo</b><span>Informações principais para identificar a sucata.</span></div>
    </div>
    <div className="vehicleFormGrid vehicleFormGridMain">
     <Field label="Placa"><input placeholder="ABC1D23" value={form.plate} onChange={e=>setForm({...form,plate:e.target.value.toUpperCase()})}/></Field>
     <VehicleBrandModel form={form} setForm={setForm} brands={brands}/>
     <Field label="Ano"><input type="number" min="1971" max={new Date().getFullYear()+1} value={form.year} onChange={e=>setForm({...form,year:e.target.value})}/></Field>
     <Field label="Cor"><input placeholder="Ex.: Prata" value={form.color} onChange={e=>setForm({...form,color:e.target.value})}/></Field>
    </div>
   </div>

   <div className="vehicleFormSection">
    <div className="vehicleFormSectionHead">
     <div className="vehicleFormIndex">02</div>
     <div><b>Identificação e características</b><span>Documentos e configuração do veículo.</span></div>
    </div>
    <div className="vehicleFormGrid">
     <Field label="Chassi / VIN"><input placeholder="Informe o chassi" value={form.vin} onChange={e=>setForm({...form,vin:e.target.value.toUpperCase()})}/></Field>
     <Field label="Renavam"><input placeholder="Informe o Renavam" value={form.renavam} onChange={e=>setForm({...form,renavam:e.target.value})}/></Field>
     <Field label="Combustível"><select value={form.fuel} onChange={e=>setForm({...form,fuel:e.target.value})}><option>Flex</option><option>Gasolina</option><option>Etanol</option><option>Diesel</option><option>Híbrido</option><option>Elétrico</option><option>GNV</option></select></Field>
     <Field label="Câmbio"><select value={form.transmission} onChange={e=>setForm({...form,transmission:e.target.value})}><option>Automático</option><option>Manual</option><option>CVT</option><option>Automatizado</option></select></Field>
    </div>
   </div>

   <div className="vehicleFormSection">
    <div className="vehicleFormSectionHead">
     <div className="vehicleFormIndex">03</div>
     <div><b>Compra e custos</b><span>Valores usados na Visão 360 e no cálculo de retorno da sucata.</span></div>
    </div>
    <div className="vehicleFinanceGrid">
     <Field label="Valor de aquisição"><div className="moneyInput"><span>R$</span><input type="number" step="0.01" placeholder="0,00" value={form.acquisition_value} onChange={e=>setForm({...form,acquisition_value:e.target.value})}/></div></Field>
     <Field label="Outros custos"><div className="moneyInput"><span>R$</span><input type="number" step="0.01" placeholder="0,00" value={form.other_costs} onChange={e=>setForm({...form,other_costs:e.target.value})}/></div></Field>
     <div className="vehicleInvestedBox"><small>TOTAL INVESTIDO</small><b>{money(totalInvested)}</b><span>Compra + custos adicionais</span></div>
    </div>
   </div>

   <div className="vehicleFormSection vehiclePhotoSection">
    <div className="vehicleFormSectionHead">
     <div className="vehicleFormIndex">04</div>
     <div><b>Fotos da sucata</b><span>A primeira imagem será a principal. Você pode adicionar até 15 fotos.</span></div>
     <strong>{photoData.length}/15</strong>
    </div>

    <div className="vehiclePhotoWorkspace">
     {photoData.length<15&&<label className="vehiclePhotoDrop">
      <input type="file" accept="image/*" multiple onChange={chooseVehiclePhoto}/>
      <div className="vehiclePhotoDropIcon">＋</div>
      <b>{photoData.length?'Adicionar mais fotos':'Adicionar fotos do veículo'}</b>
      <span>Selecione várias imagens de uma vez</span>
      <small>JPG, PNG ou fotos da câmera</small>
     </label>}

     {photoBusy&&<div className="vehiclePhotoPreparing">Preparando fotos...</div>}

     {!!photoData.length&&<div className="vehiclePhotoGrid">
      {photoData.map((src,index)=><article className={index===0?'principal':''} key={index}>
       <img src={src} alt={`Foto ${index+1} da sucata`}/>
       <div><b>{index===0?'Foto principal':`Foto ${index+1}`}</b><button type="button" onClick={()=>removeVehiclePhoto(index)}>×</button></div>
      </article>)}
     </div>}
    </div>
   </div>

   <div className="vehicleRegisterFooter">
    <div><b>Pronto para cadastrar?</b><span>Depois você poderá editar os dados e acompanhar tudo pela Visão 360.</span></div>
    <button className="primary vehicleRegisterButton" disabled={saving||photoBusy} onClick={add}>{saving?'Salvando...':'+ Cadastrar sucata'}</button>
   </div>
  </section>

  {!createOnly&&<section className="panel vehicleManagementPanel vehicleManagementModern vehicleCardsSection">
   <div className="vehicleManagementHead vehicleCardsHead">
    <div><small>SUCATAS CADASTRADAS</small><h2>Veículos no estoque</h2><p>Acompanhe cada veículo desde a entrada até o retorno das peças.</p></div>
    <div><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar placa, marca ou modelo..."/><span>{filtered.length} de {data.length}</span></div>
   </div>
   {filtered.length?<div className="vehicleCardsGrid">{filtered.map(v=>{
    const title=[v.brand,v.model,v.year].filter(Boolean).join(' ')||'Veículo sem identificação'
    const statusLabel=statusPt(v.status)
    const location=v.location||v.stock_location||v.yard_location||'Pátio'
    return <article className="vehicleStockCard" key={v.id}>
     <div className="vehicleStockPhotoWrap">
      {v.photo_data?<img className="vehicleStockPhoto" src={v.photo_data} alt="Foto da sucata"/>:<div className="vehicleStockPhotoPlaceholder"><b>{title}</b><small>Sem foto cadastrada</small></div>}
      <span className={`vehicleStockStatus ${String(v.status||'').toLowerCase()}`}>{statusLabel}</span>
     </div>
     <div className="vehicleStockBody">
      <h3>{title}</h3>
      <div className="vehicleStockTags">
       <span>{v.plate||'Sem placa'}</span>
       <span>{location}</span>
      </div>
      <div className="vehicleStockSub">{v.fuel||'Combustível não informado'} · {v.transmission||'Câmbio não informado'}</div>
      <div className="vehicleStockMeta">
       <div><small>Compra</small><b>{money(v.acquisition_value)}</b></div>
       <div><small>Custos</small><b>{money(v.other_costs)}</b></div>
      </div>
      <div className="vehicleStockActions">
       <button className="ghost editRegisterBtn" onClick={()=>setEditVehicle(v)}>✎ Editar</button>
       <button className="primary vehicle360Btn" onClick={()=>setOverview(v)}>◉ Visão 360</button>
      </div>
     </div>
    </article>
   })}</div>:<div className="emptyState">Nenhum veículo encontrado.</div>}
  </section>}

  {overview&&<Vehicle360 vehicle={overview} listings={listings} onClose={()=>setOverview(null)}/>}
  {editVehicle&&<VehicleEditModal vehicle={editVehicle} brands={brands} onClose={()=>setEditVehicle(null)} refresh={refresh} notice={notice}/>}
 </>
}

const productEmpty={sku:'',name:'',category:'',part_group:'',brand:'',model:'',year:'',oem:'',condition:'used',side:'',position:'',cost:'',price:'',stock:1,location_id:null,vehicle_id:null,description:'',compatibility:'',image_urls:'',weight:1,package_length:20,package_width:20,package_height:20,ml_category_id:'',ml_listing_type:'gold_special',shopee_category_id:'',shopee_logistic_id:'',shopee_image_ids:'',olx_category_id:'',publish_mercadolivre:true,publish_shopee:true,publish_olx:true,ml_has_warranty:false,ml_warranty_text:'',ml_shipping_mode:'',ml_free_shipping:false,ml_local_pickup:true,ml_attributes_json:'{}',ml_store_id:'',ml_network_node_id:'',quality_grade:'B',quality_notes:'',warranty_days:90,public_catalog:true,auto_publish:false}

function imageList(value){const v=value||'';return (v.includes('data:image/')?v.split(/\n/):v.split(/\n|,/)).map(x=>x.trim()).filter(Boolean)}
function readFileAsDataUrl(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)})}
function loadImage(src){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=src})}
async function optimizeProductImageUpload(file){
  try{
    if(!file||!file.type?.startsWith('image/'))return file
    const src=await readFileAsDataUrl(file)
    const img=await loadImage(src)

    // V41: preserva muito mais detalhe para a IA. Só reduz fotos realmente enormes.
    const max=3600
    const scale=Math.min(1,max/Math.max(img.width,img.height))
    const shouldOptimize=scale<0.999||file.size>8*1024*1024
    if(!shouldOptimize)return file

    const w=Math.max(1,Math.round(img.width*scale))
    const h=Math.max(1,Math.round(img.height*scale))
    const canvas=document.createElement('canvas')
    canvas.width=w;canvas.height=h
    const ctx=canvas.getContext('2d')
    ctx.imageSmoothingEnabled=true
    ctx.imageSmoothingQuality='high'
    ctx.drawImage(img,0,0,w,h)

    const blob=await new Promise((resolve,reject)=>
      canvas.toBlob(
        b=>b?resolve(b):reject(new Error('Falha ao preparar imagem')),
        'image/jpeg',
        .95
      )
    )
    return new File(
      [blob],
      String(file.name||'produto').replace(/\.[^.]+$/,'')+'-cdm.jpg',
      {type:'image/jpeg'}
    )
  }catch(e){
    console.warn('CDM preparação V41:',e)
    return file
  }
}

// CDM AI FAST V15.4
async function prepareAiAnalysisImage(src,max=1100,quality=.78){
  try{
    const img=await loadImage(src)
    const scale=Math.min(1,max/Math.max(img.width,img.height))
    const w=Math.max(1,Math.round(img.width*scale))
    const h=Math.max(1,Math.round(img.height*scale))
    const out=document.createElement('canvas')
    out.width=w
    out.height=h
    const ctx=out.getContext('2d')
    ctx.imageSmoothingEnabled=true
    ctx.imageSmoothingQuality='high'
    ctx.drawImage(img,0,0,w,h)
    return out.toDataURL('image/jpeg',quality)
  }catch(e){
    console.warn('CDM IA: cópia leve não criada',e)
    return src
  }
}

// CDM PHOTO PRO V15.5
function fileToDataUrlMaybe(file){
  if(typeof file==='string')return Promise.resolve(file)
  return new Promise((resolve,reject)=>{
    const reader=new FileReader()
    reader.onload=()=>resolve(String(reader.result||''))
    reader.onerror=()=>reject(new Error('Falha ao ler a imagem'))
    reader.readAsDataURL(file)
  })
}

async function analyzeCatalogSubject(src){
  const img=await loadImage(src)
  const canvas=document.createElement('canvas')
  canvas.width=img.width
  canvas.height=img.height
  const ctx=canvas.getContext('2d',{willReadFrequently:true})
  ctx.drawImage(img,0,0)
  const raw=ctx.getImageData(0,0,canvas.width,canvas.height).data
  let minX=canvas.width,minY=canvas.height,maxX=-1,maxY=-1,white=0
  for(let y=0;y<canvas.height;y++){
    for(let x=0;x<canvas.width;x++){
      const i=(y*canvas.width+x)*4
      const r=raw[i],g=raw[i+1],b=raw[i+2],a=raw[i+3]
      const nearWhite=a>235&&r>244&&g>244&&b>244
      if(nearWhite)white++
      const subject=a>18&&(!nearWhite||(r+g+b)<735)
      if(subject){
        if(x<minX)minX=x
        if(y<minY)minY=y
        if(x>maxX)maxX=x
        if(y>maxY)maxY=y
      }
    }
  }
  if(maxX<0||maxY<0){
    return {hasSubject:false,coverage:0,whiteRatio:white/(canvas.width*canvas.height),width:canvas.width,height:canvas.height}
  }
  const boxW=maxX-minX+1,boxH=maxY-minY+1
  const area=boxW*boxH
  const total=canvas.width*canvas.height
  return {
    hasSubject:true,
    minX,minY,maxX,maxY,boxW,boxH,
    coverage:area/Math.max(1,total),
    whiteRatio:white/Math.max(1,total),
    edgeTouch:minX<=2||minY<=2||maxX>=canvas.width-3||maxY>=canvas.height-3,
    width:canvas.width,
    height:canvas.height
  }
}

async function placeSubjectOnCatalogWhite(src,metrics=null){
  const m=metrics||await analyzeCatalogSubject(src)
  if(!m.hasSubject)return src
  const img=await loadImage(src)
  const padX=Math.max(14,Math.round(m.boxW*0.14))
  const padY=Math.max(14,Math.round(m.boxH*0.14))
  const sx=Math.max(0,m.minX-padX)
  const sy=Math.max(0,m.minY-padY)
  const sw=Math.min(m.width-sx,m.boxW+padX*2)
  const sh=Math.min(m.height-sy,m.boxH+padY*2)
  const size=Math.max(1200,Math.min(1800,Math.round(Math.max(sw,sh)*1.22)))
  const out=document.createElement('canvas')
  out.width=size
  out.height=size
  const ctx=out.getContext('2d')
  ctx.fillStyle='#ffffff'
  ctx.fillRect(0,0,size,size)
  const target=Math.round(size*0.82)
  const scale=Math.min(target/sw,target/sh)
  const dw=Math.round(sw*scale)
  const dh=Math.round(sh*scale)
  const dx=Math.round((size-dw)/2)
  const dy=Math.round((size-dh)/2)
  ctx.imageSmoothingEnabled=true
  ctx.imageSmoothingQuality='high'
  ctx.drawImage(img,sx,sy,sw,sh,dx,dy,dw,dh)
  return out.toDataURL('image/jpeg',.92)
}

async function buildConservativeWhitePhoto(file){
  const src=await fileToDataUrlMaybe(file)
  const img=await loadImage(src)
  const w=img.width,h=img.height
  const scan=document.createElement('canvas')
  scan.width=w
  scan.height=h
  const sctx=scan.getContext('2d',{willReadFrequently:true})
  sctx.drawImage(img,0,0)
  const raw=sctx.getImageData(0,0,w,h).data

  const sample=(x,y)=>{
    const i=(Math.max(0,Math.min(h-1,y))*w+Math.max(0,Math.min(w-1,x)))*4
    return [raw[i],raw[i+1],raw[i+2]]
  }
  const corners=[sample(3,3),sample(w-4,3),sample(3,h-4),sample(w-4,h-4)]
  const bg=[0,1,2].map(k=>corners.reduce((acc,v)=>acc+v[k],0)/corners.length)

  let minX=w,minY=h,maxX=-1,maxY=-1
  for(let y=0;y<h;y++){
    for(let x=0;x<w;x++){
      const i=(y*w+x)*4
      const r=raw[i],g=raw[i+1],b=raw[i+2],a=raw[i+3]
      if(a<15)continue
      const delta=Math.abs(r-bg[0])+Math.abs(g-bg[1])+Math.abs(b-bg[2])
      const dark=(r+g+b)<705
      const strong=delta>54||dark
      if(strong){
        if(x<minX)minX=x
        if(y<minY)minY=y
        if(x>maxX)maxX=x
        if(y>maxY)maxY=y
      }
    }
  }
  if(maxX<0||maxY<0)return src

  const boxW=maxX-minX+1,boxH=maxY-minY+1
  const padX=Math.max(16,Math.round(boxW*0.12))
  const padY=Math.max(16,Math.round(boxH*0.12))
  const sx=Math.max(0,minX-padX)
  const sy=Math.max(0,minY-padY)
  const sw=Math.min(w-sx,boxW+padX*2)
  const sh=Math.min(h-sy,boxH+padY*2)
  const size=Math.max(1200,Math.min(1800,Math.round(Math.max(sw,sh)*1.22)))

  const out=document.createElement('canvas')
  out.width=size
  out.height=size
  const ctx=out.getContext('2d')
  ctx.fillStyle='#ffffff'
  ctx.fillRect(0,0,size,size)
  const target=Math.round(size*0.82)
  const scale=Math.min(target/sw,target/sh)
  const dw=Math.round(sw*scale)
  const dh=Math.round(sh*scale)
  const dx=Math.round((size-dw)/2)
  const dy=Math.round((size-dh)/2)
  ctx.imageSmoothingEnabled=true
  ctx.imageSmoothingQuality='high'
  ctx.drawImage(img,sx,sy,sw,sh,dx,dy,dw,dh)
  return out.toDataURL('image/jpeg',.92)
}

async function scorePreparedPhoto(src){
  const m=await analyzeCatalogSubject(src)
  if(!m.hasSubject)return {score:-999,src,metrics:m}
  let score=0
  score+=Math.min(m.coverage,.55)*220
  if(m.coverage<.02)score-=40
  if(m.coverage>.78)score-=28
  if(m.edgeTouch)score-=24
  score-=Math.abs(.32-m.coverage)*48
  score-=Math.max(0,m.whiteRatio-.985)*150
  return {score,src,metrics:m}
}

async function prepareProductImage(file,removeBg=true,mode='basic'){
  const candidates=[]
  try{candidates.push(await prepareProductImageCore(file,removeBg,mode))}catch(e){console.warn('CDM Foto: tentativa principal falhou',e)}
  if(mode!=='pro'){
    try{candidates.push(await prepareProductImageCore(file,removeBg,'pro'))}catch(e){console.warn('CDM Foto: tentativa pro falhou',e)}
  }
  try{candidates.push(await buildConservativeWhitePhoto(file))}catch(e){console.warn('CDM Foto: fallback conservador falhou',e)}

  let best=null
  for(const candidate of candidates.filter(Boolean)){
    let normalized=candidate
    try{
      normalized=await placeSubjectOnCatalogWhite(candidate)
    }catch(e){}
    const scored=await scorePreparedPhoto(normalized)
    if(!best||scored.score>best.score)best=scored
  }

  if(best&&best.src)return best.src
  if(candidates[0])return candidates[0]
  return await buildConservativeWhitePhoto(file)
}

// CDM AI RETRY V15.5
async function analyzeProductPhotosWithRetry({aiImages,vehicleId,context,notice}){
  try{
    return await api.post('/intelligence/product-photo-analysis',{
      images:aiImages,
      vehicle_id:vehicleId,
      context
    },{timeout:52000})
  }catch(error){
    const status=Number(error?.response?.status||0)
    const detail=String(error?.response?.data?.detail||'').toLowerCase()
    const transient=[408,429,500,502,503,504].includes(status)||/oscil|demor|tempo|timeout|ocupad/.test(detail)
    if(!transient)throw error
    try{notice&&notice('A IA oscilou. O CDM está tentando novamente automaticamente...')}catch(_){}
    await new Promise(resolve=>setTimeout(resolve,900))
    const retryImages=await Promise.all(aiImages.slice(0,1).map(src=>prepareAiAnalysisImage(src,900,.72)))
    return await api.post('/intelligence/product-photo-analysis',{
      images:retryImages,
      vehicle_id:vehicleId,
      context
    },{timeout:28000})
  }
}

async function prepareProductImageCore(file,removeBg=true,mode='basic'){
  if(removeBg){
    const formData=new FormData()
    const uploadFile=await optimizeProductImageUpload(file)
    formData.append('file',uploadFile,uploadFile.name||'produto.jpg')
    formData.append('mode',mode||'auto')

    try{
      const response=await api.post('/products/remove-background',formData,{
        responseType:'arraybuffer',
        timeout:80000
      })
      const contentType=response.headers?.['content-type']||'image/jpeg'
      window.__cdmLastPhotoEngine=response.headers?.['x-cdm-photo-ai']||''
      const blob=new Blob([response.data],{type:contentType})
      if(!blob.size)throw new Error('Imagem processada vazia')
      return await new Promise((resolve,reject)=>{
        const reader=new FileReader()
        reader.onload=()=>resolve(reader.result)
        reader.onerror=reject
        reader.readAsDataURL(blob)
      })
    }catch(e){
      console.error('CDM Fundo Branco Pro V47:',e)
      throw new Error('O Fundo Branco CDM Pro não conseguiu tratar esta foto')
    }
  }

  const src=await readFileAsDataUrl(file)
  const img=await loadImage(src)
  const max=1800
  const scale=Math.min(1,max/Math.max(img.width,img.height))
  const w=Math.max(1,Math.round(img.width*scale))
  const h=Math.max(1,Math.round(img.height*scale))

  const out=document.createElement('canvas')
  out.width=w
  out.height=h
  const ctx=out.getContext('2d')
  ctx.imageSmoothingEnabled=true
  ctx.imageSmoothingQuality='high'
  ctx.drawImage(img,0,0,w,h)

  return out.toDataURL('image/jpeg',.94)
}

function parseMlAttrs(value){try{const x=JSON.parse(value||'{}');return x&&typeof x==='object'&&!Array.isArray(x)?x:{}}catch{return {}}}

function mlVehicleType(form){
  const attrs=parseMlAttrs(form?.ml_attributes_json)
  const saved=String(attrs._CDM_VEHICLE_SEGMENT||'')
  if(saved==='car_pickup'||saved==='truck')return saved
  const legacy=String(attrs.VEHICLE_TYPE||'').toLowerCase()
  if(legacy.includes('caminhão')||legacy.includes('caminhao')||legacy.includes('linha pesada'))return 'truck'
  if(legacy.includes('carro')||legacy.includes('caminhonete'))return 'car_pickup'
  return ''
}
function mlResetCategoryAttrs(form,segment){
  return JSON.stringify({_CDM_VEHICLE_SEGMENT:segment||mlVehicleType(form)})
}
function setMlVehicleType(form,setForm,segment){
  setForm({
    ...form,
    category:'',
    ml_category_id:'',
    ml_attributes_json:mlResetCategoryAttrs(form,segment)
  })
}


function mlManagedAttributeValue(form,id){
  if(id==='BRAND')return String(form?.brand||'').trim()
  if(id==='MODEL')return String(form?.model||'').trim()
  if(id==='PART_NUMBER'||id==='OEM')return String(form?.oem||'').trim()
  if(id==='ITEM_CONDITION')return form?.condition==='new'?'Novo':form?.condition==='reconditioned'?'Recondicionado':'Usado'
  return null
}
function mlIsManagedAttribute(id){
  return ['BRAND','MODEL','PART_NUMBER','OEM','ITEM_CONDITION'].includes(String(id||''))
}

function MarketplaceConfigModal({market,form,setForm,onClose,brands=[]}){
  const [requiredAttrs,setRequiredAttrs]=useState([]),[attrsBusy,setAttrsBusy]=useState(false),[storesInfo,setStoresInfo]=useState({warehouse_management:false,multiwarehouse:false,stores:[]}),[mlConnection,setMlConnection]=useState(null)
  const [shopeeSetup,setShopeeSetup]=useState({connected:false,categories:[],logistics:[],enabled_logistics:[]}),[shopeeBusy,setShopeeBusy]=useState(false),[shopeeError,setShopeeError]=useState('')
  useEffect(()=>{let alive=true;if(market!=='mercadolivre'){setStoresInfo({warehouse_management:false,multiwarehouse:false,stores:[]});return}api.get('/marketplaces/mercadolivre/stores').then(r=>alive&&setStoresInfo(r.data||{warehouse_management:false,multiwarehouse:false,stores:[]})).catch(()=>alive&&setStoresInfo({warehouse_management:false,multiwarehouse:false,stores:[]}));return()=>{alive=false}},[market])
  useEffect(()=>{let alive=true;if(market!=='mercadolivre'){setMlConnection(null);return}api.get('/marketplaces/mercadolivre/connection-check').then(r=>alive&&setMlConnection(r.data||null)).catch(()=>alive&&setMlConnection(null));return()=>{alive=false}},[market])
  useEffect(()=>{let alive=true;if(market!=='mercadolivre'||!form.ml_category_id){setRequiredAttrs([]);return}setAttrsBusy(true);api.get(`/marketplaces/mercadolivre/category/${form.ml_category_id}/attributes`).then(r=>alive&&setRequiredAttrs(r.data||[])).catch(()=>alive&&setRequiredAttrs([])).finally(()=>alive&&setAttrsBusy(false));return()=>{alive=false}},[market,form.ml_category_id])
  useEffect(()=>{let alive=true;if(market!=='shopee'){setShopeeSetup({connected:false,categories:[],logistics:[],enabled_logistics:[]});setShopeeError('');return}setShopeeBusy(true);setShopeeError('');api.get('/marketplaces/shopee/setup-options').then(r=>{if(!alive)return;const data=r.data||{};setShopeeSetup(data);const enabled=data.enabled_logistics||[];if(!form.shopee_logistic_id&&enabled.length===1)setForm(f=>({...f,shopee_logistic_id:String(enabled[0].id)}))}).catch(e=>{if(!alive)return;setShopeeSetup({connected:false,categories:[],logistics:[],enabled_logistics:[]});setShopeeError(erroPt(e.response?.data?.detail)||'Conecte sua loja Shopee na Central de Integrações')}).finally(()=>alive&&setShopeeBusy(false));return()=>{alive=false}},[market])
  if(!market)return null
  return <div className={'modalBackdrop '+(market==='mercadolivre'?'marketplaceModalBackdrop':'')} onMouseDown={e=>e.target===e.currentTarget&&onClose()}><div className={'marketConfigModal '+(market==='mercadolivre'?'marketConfigModalML':'')}><div className="modalHead"><div><small>{market==='mercadolivre'?'PUBLICAÇÃO • MERCADO LIVRE':'CONFIGURAÇÃO DO CANAL'}</small><h2>{market==='mercadolivre'?'Mercado Livre':marketName(market)}</h2><p>{market==='mercadolivre'?'Preencha as informações específicas para o Mercado Livre, bem como os detalhes da publicação.':'Preencha apenas o que esse canal precisa para publicar esta peça.'}</p></div><button className="iconClose" onClick={onClose}>×</button></div>
    {market==='mercadolivre'&&<div className="modalBody mlProfessionalBody"><div className={'videoMlAccount '+(mlConnection?.ok?'connected':'pending')}><div className="videoMlAccountLogo">ML</div><div><small>PUBLICAÇÃO</small><b>{mlConnection?.account?.nickname||mlConnection?.nickname||'Mercado Livre'}</b><span>{mlConnection?.ok?'Conta conectada e pronta para publicar':'Conexão será validada antes da publicação'}</span></div><div className="videoMlAccountMeta"><small>Site</small><b>{mlConnection?.site_id||mlConnection?.account?.site_id||'MLB'}</b></div></div><div className="videoMlTitleField"><label><span>Título *</span><div><input value={form.name||''} maxLength="60" onChange={e=>setForm({...form,name:e.target.value})} placeholder="Título do anúncio"/><small>{String(form.name||'').length}/60</small></div></label></div><div className="mlPremiumHero"><div className="mlPremiumHeroMain"><span>MERCADO LIVRE • PUBLICAÇÃO</span><strong>{form.name||'Peça sem nome'}</strong><small>{[form.brand,form.model,form.year].filter(Boolean).join(' ')||'Aplicação do veículo ainda não informada'}</small></div><div className="mlPremiumHeroStat"><span>SKU</span><b>{form.sku||'—'}</b><small>Identificação interna</small></div><div className="mlPremiumHeroStat"><span>Preço</span><b>{form.price?money(form.price):'—'}</b><small>Preço de venda</small></div><div className="mlPremiumHeroStat"><span>Estoque</span><b>{Number(form.stock||0)} un.</b><small>Disponível para anúncio</small></div><div className="mlPremiumHeroStat"><span>OEM / Código</span><b>{form.oem||'—'}</b><small>Referência da peça</small></div></div><div className="mlConfigSummary"><div className="mlConfigSummaryLead"><span>CONFIGURAÇÃO ASSISTIDA</span><strong>Anúncio organizado em etapas</strong><small>Escolha as opções abaixo e o CDM prepara os dados obrigatórios do Mercado Livre sem misturar peças de carro/caminhonete com linha pesada.</small></div><div className={'mlSummaryItem '+(mlVehicleType(form)?'ok':'pending')}><small>Segmento</small><b>{mlVehicleType(form)==='truck'?'Caminhão / Linha Pesada':mlVehicleType(form)==='car_pickup'?'Carro / Caminhonete':'Pendente'}</b></div><div className={'mlSummaryItem '+(form.ml_category_id?'ok':'pending')}><small>Categoria</small><b>{form.ml_category_id?'Configurada':'Pendente'}</b></div><div className="mlSummaryItem ok"><small>Condição</small><b>{form.condition==='new'?'Novo':form.condition==='reconditioned'?'Recondicionado':'Usado'}</b></div></div><h3 className="formSectionTitle">Tipo de veículo</h3><div className="optionGrid two"><label className={'choiceCard '+(mlVehicleType(form)==='car_pickup'?'selected':'')}><input type="radio" name="mlVehicleSegment" checked={mlVehicleType(form)==='car_pickup'} onChange={()=>setMlVehicleType(form,setForm,'car_pickup')}/><b>🚗 Carro / Caminhonete</b><small>Peças para carros, utilitários e caminhonetes.</small></label><label className={'choiceCard '+(mlVehicleType(form)==='truck'?'selected':'')}><input type="radio" name="mlVehicleSegment" checked={mlVehicleType(form)==='truck'} onChange={()=>setMlVehicleType(form,setForm,'truck')}/><b>🚛 Caminhão</b><small>Peças para caminhões e linha pesada.</small></label></div><p className="fieldHelp">Escolha o tipo antes da categoria. O CDM envia automaticamente o Tipo de veículo aceito pela categoria do Mercado Livre.</p><h3 className="formSectionTitle">Condição</h3><div className="optionGrid"><label className={'choiceCard '+(form.condition==='new'?'selected':'')}><input type="radio" name="cond" checked={form.condition==='new'} onChange={()=>setForm({...form,condition:'new'})}/><b>Novo</b><small>Peça sem uso.</small></label><label className={'choiceCard '+(form.condition==='used'?'selected':'')}><input type="radio" name="cond" checked={form.condition==='used'} onChange={()=>setForm({...form,condition:'used'})}/><b>Usado</b><small>Peça usada/desmontada.</small></label><label className={'choiceCard '+(form.condition==='reconditioned'?'selected':'')}><input type="radio" name="cond" checked={form.condition==='reconditioned'} onChange={()=>setForm({...form,condition:'reconditioned'})}/><b>Recondicionado</b><small>Peça revisada.</small></label></div><h3 className="formSectionTitle">Garantia</h3><div className="optionGrid two"><label className={'choiceCard '+(form.ml_has_warranty?'selected':'')}><input type="radio" checked={form.ml_has_warranty} onChange={()=>setForm({...form,ml_has_warranty:true})}/><b>Possui garantia</b><small>Informe a garantia abaixo.</small></label><label className={'choiceCard '+(!form.ml_has_warranty?'selected':'')}><input type="radio" checked={!form.ml_has_warranty} onChange={()=>setForm({...form,ml_has_warranty:false,ml_warranty_text:''})}/><b>Não possui garantia</b><small>Sem garantia associada.</small></label></div>{form.ml_has_warranty&&<Field label="Texto da garantia"><input placeholder="Ex.: 90 dias de garantia" value={form.ml_warranty_text} onChange={e=>setForm({...form,ml_warranty_text:e.target.value})}/></Field>}<h3 className="formSectionTitle">Listagem</h3><div className="optionGrid two"><label className={'choiceCard '+(form.ml_listing_type==='gold_pro'?'selected':'')}><input type="radio" checked={form.ml_listing_type==='gold_pro'} onChange={()=>setForm({...form,ml_listing_type:'gold_pro'})}/><b>Maior exposição</b><small>Maior destaque quando disponível.</small></label><label className={'choiceCard '+(form.ml_listing_type==='gold_special'?'selected':'')}><input type="radio" checked={form.ml_listing_type==='gold_special'} onChange={()=>setForm({...form,ml_listing_type:'gold_special'})}/><b>Clássica</b><small>Listagem padrão.</small></label></div><h3 className="formSectionTitle">Frete</h3><div className="optionGrid three"><label className={'choiceCard '+(form.ml_shipping_mode===''?'selected':'')}><input type="radio" checked={form.ml_shipping_mode===''} onChange={()=>setForm({...form,ml_shipping_mode:''})}/><b>Automático</b><small>Usar configuração da conta/categoria.</small></label><label className={'choiceCard '+(form.ml_shipping_mode==='me2'?'selected':'')}><input type="radio" checked={form.ml_shipping_mode==='me2'} onChange={()=>setForm({...form,ml_shipping_mode:'me2'})}/><b>Mercado Envios</b><small>Quando elegível para a conta.</small></label><label className={'choiceCard '+(form.ml_shipping_mode==='custom'?'selected':'')}><input type="radio" checked={form.ml_shipping_mode==='custom'} onChange={()=>setForm({...form,ml_shipping_mode:'custom'})}/><b>A combinar</b><small>Frete combinado com o comprador.</small></label></div><div className="switchRows"><label><input type="checkbox" checked={form.ml_free_shipping} onChange={e=>setForm({...form,ml_free_shipping:e.target.checked})}/><span><b>Frete grátis</b><small>Marque somente se sua operação oferecer frete grátis.</small></span></label><label><input type="checkbox" checked={form.ml_local_pickup} onChange={e=>setForm({...form,ml_local_pickup:e.target.checked})}/><span><b>Retirada pessoalmente</b><small>Permitir retirada da peça na loja física.</small></span></label></div>{storesInfo.warehouse_management&&<><h3 className="formSectionTitle">Depósito do Mercado Livre</h3><Field label={storesInfo.multiwarehouse?"Depósito que representa este estoque":"Depósito de estoque"}><select value={form.ml_store_id||''} onChange={e=>{const st=storesInfo.stores.find(x=>String(x.id)===String(e.target.value));setForm({...form,ml_store_id:e.target.value,ml_network_node_id:st?.network_node_id||''})}}><option value="">{storesInfo.stores.length===1?"Usar depósito disponível":"Selecione o depósito..."}</option>{storesInfo.stores.map(st=><option key={st.id} value={st.id}>{st.description} — {st.city}{st.state?`/${st.state}`:''}</option>)}</select></Field><p className="fieldHelp">Esta conta usa estoque por depósito. O CDM sincroniza a quantidade desta peça com o depósito selecionado.</p></>}<h3 className="formSectionTitle">Atributos obrigatórios da categoria</h3>{mlVehicleType(form)&&<div className="mlAutoSourceBar"><span className="mlAutoSourceBadge">✓ Automático</span><span>Tipo de veículo: <b>{mlVehicleType(form)==='truck'?'Caminhão / Linha Pesada':'Carro / Caminhonete'}</b></span></div>}{attrsBusy?<p className="fieldHelp">Carregando campos do Mercado Livre...</p>:requiredAttrs.filter(a=>a.id!=='VEHICLE_TYPE').length?<div className="mlAttributeGrid">{requiredAttrs.filter(a=>a.id!=='VEHICLE_TYPE').map(a=>{const id=String(a.id||'');const managed=mlIsManagedAttribute(id);const autoValue=mlManagedAttributeValue(form,id);const current=parseMlAttrs(form.ml_attributes_json)[id]||'';if(id==='BRAND'){const availableBrands=brands?.length?brands:FALLBACK_VEHICLE_BRANDS;return <div className="mlManagedField" key={id}><Field label={`${a.name} *`}><select value={form.brand||''} onChange={e=>setForm({...form,brand:e.target.value,model:e.target.value===form.brand?form.model:''})}><option value="">Selecione a marca...</option>{availableBrands.map(b=><option key={b} value={b}>{b}</option>)}</select></Field><div className="mlManagedHint"><span>✓ Preenchido pelo cadastro da peça</span><small>É a mesma marca usada no cadastro principal.</small></div></div>}if(id==='MODEL'){return <div className="mlManagedField" key={id}><Field label={`${a.name} *`}><input value={form.model||''} onChange={e=>setForm({...form,model:e.target.value})} placeholder="Modelo da aplicação"/></Field><div className="mlManagedHint"><span>✓ Sincronizado com o cadastro</span><small>Alterações aqui também atualizam o modelo da peça.</small></div></div>}if(id==='PART_NUMBER'||id==='OEM'){return <div className="mlManagedField" key={id}><Field label={`${a.name} *`}><input value={form.oem||''} onChange={e=>setForm({...form,oem:e.target.value})} placeholder="Código/OEM da peça"/></Field><div className="mlManagedHint"><span>✓ Preenchido pelo código/OEM</span><small>Você não precisa digitar o número da peça duas vezes.</small></div></div>}if(id==='ITEM_CONDITION'){return <div className="mlManagedField readOnly" key={id}><Field label={`${a.name} *`}><input value={autoValue||''} readOnly/></Field><div className="mlManagedHint"><span>✓ Definido pela condição da peça</span><small>Use a seção Condição acima para alterar.</small></div></div>}return <Field key={id} label={`${a.name} *`}>{a.values?.length?<select value={current} onChange={e=>{const m=parseMlAttrs(form.ml_attributes_json);m[id]=e.target.value;setForm({...form,ml_attributes_json:JSON.stringify(m)})}}><option value="">Selecione...</option>{a.values.map(v=><option key={v.id||v.name} value={v.name}>{v.name}</option>)}</select>:<input value={current} onChange={e=>{const m=parseMlAttrs(form.ml_attributes_json);m[id]=e.target.value;setForm({...form,ml_attributes_json:JSON.stringify(m)})}}/>}</Field>})}</div>:form.ml_category_id?<p className="fieldHelp">Nenhum outro atributo obrigatório para preencher manualmente.</p>:<p className="fieldHelp">Escolha uma categoria para carregar os atributos exigidos pelo Mercado Livre.</p>}</div>}
    {market==='shopee'&&<div className="modalBody">
      <div className={'videoMlAccount '+(shopeeSetup?.connected?'connected':'pending')}>
        <div className="videoMlAccountLogo">SH</div>
        <div><small>PUBLICAÇÃO • SHOPEE</small><b>{shopeeSetup?.account_name||'Sua loja Shopee'}</b><span>{shopeeSetup?.connected?'Conta conectada · opções carregadas diretamente da Shopee':'Conecte a loja na Central de Integrações'}</span></div>
        <div className="videoMlAccountMeta"><small>Loja</small><b>{shopeeSetup?.shop_id||'—'}</b></div>
      </div>

      {shopeeBusy?<p className="fieldHelp">Carregando categorias e logística da sua loja Shopee...</p>:shopeeError?<div className="error">{shopeeError}</div>:<>
        <div className="mlConfigSummary">
          <div className="mlConfigSummaryLead"><span>CONFIGURAÇÃO ASSISTIDA</span><strong>O CDM busca os dados da sua loja</strong><small>Categoria, logística e imagens deixam de ser códigos manuais. As fotos do cadastro são enviadas automaticamente na publicação.</small></div>
          <div className={'mlSummaryItem '+(form.shopee_category_id?'ok':'pending')}><small>Categoria</small><b>{form.shopee_category_id?'Configurada':'Pendente'}</b></div>
          <div className={'mlSummaryItem '+(form.shopee_logistic_id?'ok':'pending')}><small>Logística</small><b>{form.shopee_logistic_id?'Configurada':'Pendente'}</b></div>
          <div className={'mlSummaryItem '+(imageList(form.image_urls).length?'ok':'pending')}><small>Fotos</small><b>{imageList(form.image_urls).length?`${imageList(form.image_urls).length} pronta(s)`:'Pendente'}</b></div>
        </div>

        <h3 className="formSectionTitle">Categoria Shopee</h3>
        <Field label="Categoria para publicação">
          <select value={form.shopee_category_id||''} onChange={e=>setForm({...form,shopee_category_id:e.target.value})}>
            <option value="">Selecione a categoria...</option>
            {(shopeeSetup.categories||[]).filter(x=>!x.has_children).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
        {!(shopeeSetup.categories||[]).some(x=>!x.has_children)&&<p className="fieldHelp">A Shopee não retornou categorias finais nesta consulta. Vamos ajustar conforme a resposta real da sua conta no primeiro teste.</p>}

        <h3 className="formSectionTitle">Logística da loja</h3>
        <Field label="Canal de envio">
          <select value={form.shopee_logistic_id||''} onChange={e=>setForm({...form,shopee_logistic_id:e.target.value})}>
            <option value="">Selecione a logística...</option>
            {(shopeeSetup.logistics||[]).filter(x=>x.enabled).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
        <p className="fieldHelp">Mostramos somente os canais de envio habilitados na própria loja Shopee.</p>

        <h3 className="formSectionTitle">Embalagem</h3>
        <div className="formGrid three">
          <Field label="Peso (kg)"><input type="number" min="0.01" step="0.01" value={form.weight??''} onChange={e=>setForm({...form,weight:e.target.value})}/></Field>
          <Field label="Comprimento (cm)"><input type="number" min="1" value={form.package_length??''} onChange={e=>setForm({...form,package_length:e.target.value})}/></Field>
          <Field label="Largura (cm)"><input type="number" min="1" value={form.package_width??''} onChange={e=>setForm({...form,package_width:e.target.value})}/></Field>
          <Field label="Altura (cm)"><input type="number" min="1" value={form.package_height??''} onChange={e=>setForm({...form,package_height:e.target.value})}/></Field>
        </div>

        <div className="mlAutoSourceBar"><span className="mlAutoSourceBadge">✓ Automático</span><span>As imagens do CDM Pro serão enviadas automaticamente para a Shopee. Você não precisa copiar IDs de imagem.</span></div>
      </>}
    </div>}
    {market==='olx'&&<div className="modalBody"><Field label="ID da categoria OLX"><input value={form.olx_category_id} onChange={e=>setForm({...form,olx_category_id:e.target.value})}/></Field><p className="fieldHelp">A OLX também utiliza telefone e CEP cadastrados nas Informações da Empresa e exige conta/plano compatível com a integração.</p></div>}
    <div className="modalFoot"><div className="modalFootInfo">{market==='mercadolivre'&&<><b>Configuração do Mercado Livre</b><small>Revise os campos e depois salve a peça no cadastro.</small></>}</div><button className="ghost" onClick={onClose}>Fechar</button><button className="primary" onClick={onClose}>Concluir configuração</button></div></div></div>
}


// CDM RACE PHOTO LOADER V11
function RacePhotoLoader({progress=0,elapsed=0,text='Processando foto...'}){
 const pct=Math.max(3,Math.min(100,Number(progress)||0))
 return <div className={'cdmRaceLoader '+(pct>=100?'finished':'')} role="status" aria-live="polite">
   <div className="cdmRaceLoaderHead">
     <div>
       <span>TRATAMENTO DE IMAGEM</span>
       <b>{pct>=100?'Foto pronta!':text}</b>
     </div>
     <strong>{pct>=100?'🏁':`${elapsed}s`}</strong>
   </div>
   <div className="cdmRaceStage">
     <div className="cdmRaceRoad">
       <div className="cdmRaceFill" style={{width:`${pct}%`}}/>
       <div className="cdmRaceCar" style={{left:`calc(${Math.min(pct,94)}% - 23px)`}}>
         <svg viewBox="0 0 90 48" aria-hidden="true">
           <path className="carBody" d="M12 29l8-13c2-4 6-6 11-6h24c5 0 9 2 12 6l7 8 8 3c3 1 5 4 5 7v4H6v-4c0-3 2-5 6-5z"/>
           <path className="carWindow" d="M29 15h25c4 0 6 1 9 5l3 4H22l5-7c1-1 1-2 2-2z"/>
           <circle cx="24" cy="38" r="7" className="carWheel"/><circle cx="69" cy="38" r="7" className="carWheel"/>
           <circle cx="24" cy="38" r="3" className="carHub"/><circle cx="69" cy="38" r="3" className="carHub"/>
           <path d="M76 28h8" className="carLight"/>
         </svg>
       </div>
       <div className="cdmRaceFlag" aria-hidden="true"><i/><span>🏁</span></div>
     </div>
   </div>
   <div className="cdmRaceMeta">
     <span>{pct<30?'Preparando sua foto…':pct<75?'Separando a peça do fundo…':pct<100?'Quase lá, finalizando…':'Concluído!'}</span>
     <b>{Math.round(pct)}%</b>
   </div>
 </div>
}

// CDM PRODUCT IMAGES V2
function ProductImages({form,setForm,notice}){
 const [busy,setBusy]=useState(false),[zoom,setZoom]=useState(null),[elapsed,setElapsed]=useState(0),[raceDone,setRaceDone]=useState(false)
 const [pendingPreviews,setPendingPreviews]=useState([])
 const images=imageList(form.image_urls)
 const zoomIndex=zoom?images.findIndex(x=>x===zoom):-1
 const progress=raceDone?100:Math.min(94,18+(elapsed*18))
 const progressText=raceDone?'Fotos prontas!':elapsed<1?'Preparando as fotos...':'CDM Pro removendo o fundo e refinando...'

 useEffect(()=>{
   if(!busy){setElapsed(0);return}
   setElapsed(0)
   const timer=setInterval(()=>setElapsed(v=>v+1),1000)
   return()=>clearInterval(timer)
 },[busy])

 function stepZoom(dir){
   if(!images.length)return
   const current=zoomIndex>=0?zoomIndex:0
   const next=(current+dir+images.length)%images.length
   setZoom(images[next])
 }

 useEffect(()=>{
   if(!zoom)return
   function onKey(e){
     if(e.key==='Escape')setZoom(null)
     if(e.key==='ArrowLeft')stepZoom(-1)
     if(e.key==='ArrowRight')stepZoom(1)
   }
   window.addEventListener('keydown',onKey)
   return()=>window.removeEventListener('keydown',onKey)
 },[zoom,images.length])

 function save(next){setForm({...form,image_urls:next.join('\n')})}

 async function upload(files){
   if(!files?.length)return
   const remaining=Math.max(0,8-images.length)
   if(!remaining)return notice('Limite de 8 fotos atingido')

   const selected=Array.from(files).filter(f=>f.type.startsWith('image/')).slice(0,remaining)
   if(!selected.length)return notice('Selecione uma imagem válida')

   const stamp=Date.now()
   const previews=selected.map((file,i)=>({id:`${stamp}-${i}`,url:URL.createObjectURL(file),name:file.name||`Foto ${i+1}`}))
   setPendingPreviews(previews)
   setBusy(true)
   setRaceDone(false)

   const completed=[]
   let failed=0
   try{
     for(let i=0;i<selected.length;i++){
       const file=selected[i]
       const preview=previews[i]
       try{
         const out=await prepareProductImage(file,true,'basic')
         completed.push(out)
         save([...images,...completed])
       }catch(e){
         failed++
         console.error('CDM Pro não concluiu o tratamento da foto:',e)
       }finally{
         setPendingPreviews(current=>current.filter(item=>item.id!==preview.id))
       }
     }

     setRaceDone(true)
     await new Promise(r=>setTimeout(r,220))
     notice(failed?`${completed.length} foto(s) adicionada(s) pelo CDM Pro. ${failed} foto(s) não foram concluídas.`:`${completed.length} foto(s) tratada(s) pelo CDM Pro`)
   }catch(e){
     notice('Não foi possível carregar esta foto')
   }finally{
     setPendingPreviews([])
     window.setTimeout(()=>previews.forEach(item=>URL.revokeObjectURL(item.url)),500)
     setBusy(false)
     setRaceDone(false)
   }
 }

 function remove(i){
   const removed=images[i]
   const next=images.filter((_,idx)=>idx!==i)
   save(next)
   if(zoom===removed)setZoom(null)
 }

 function principal(i){
   if(i===0)return
   const next=[...images]
   const chosen=next.splice(i,1)[0]
   next.unshift(chosen)
   save(next)
   notice('Foto principal atualizada')
 }

 function move(i,dir){
   const to=i+dir
   if(to<0||to>=images.length)return
   const next=[...images]
   const temp=next[i]
   next[i]=next[to]
   next[to]=temp
   save(next)
 }

 return <div className="productImagesV2">
   <div className="mediaStudioHeader">
     <div>
       <span>MÍDIA</span>
       <h3>Fotos da peça</h3>
       <p>Organize as imagens que serão usadas no estoque e nos canais de venda.</p>
     </div>
   </div>

   {busy&&<RacePhotoLoader progress={progress} elapsed={elapsed} text={progressText}/>}

   <div className="cdmProOnlyCard">
     <div className="cdmProOnlyBrand">
       <span className="cdmProOnlyBadge">CDM</span>
       <div className="cdmProOnlyCopy">
         <b>CDM Pro</b>
         <span>Recorte inteligente local, fundo branco puro e enquadramento profissional, sem cobrança por foto.</span>
       </div>
     </div>
     <div className="cdmProOnlyFeatures">
       <span>⚡ Prévia imediata</span>
       <span>✓ Fundo branco automático</span>
       <span>∞ Ilimitado</span>
     </div>
   </div>

   <div className="mediaStudioGrid">
     <section className="mediaPhotoBox">
       <div className="mediaThumbRail">
         {images.map((src,i)=><article className={'mediaThumbCard '+(i===0?'principal':'')} key={`${i}-${src.slice(0,28)}`}>
           <button type="button" className="mediaThumbImage" onClick={()=>setZoom(src)} title="Ampliar foto">
             <img src={src} alt={`Foto ${i+1} da peça`}/>
             {i===0&&<span className="mediaPrincipalBadge">Principal</span>}
             <span className="mediaThumbIndex">{i+1}</span>
           </button>

           <button type="button" className="mediaDeletePhoto" onClick={()=>remove(i)} title="Excluir foto">×</button>

           <div className="mediaThumbTools">
             <button type="button" onClick={()=>setZoom(src)} title="Ampliar">⌕</button>
             {i!==0&&<button type="button" onClick={()=>principal(i)} title="Usar como principal">★</button>}
           </div>

           <div className="mediaThumbOrder">
             <button type="button" disabled={i===0} onClick={()=>move(i,-1)}>←</button>
             <button type="button" disabled={i===images.length-1} onClick={()=>move(i,1)}>→</button>
           </div>
         </article>)}

         {pendingPreviews.map((item,i)=><article className="mediaThumbCard mediaPendingCard" key={item.id}>
           <div className="mediaThumbImage mediaPendingImage">
             <img src={item.url} alt={`Prévia ${i+1} em processamento`}/>
             <span className="mediaPendingOverlay">CDM Pro processando...</span>
           </div>
         </article>)}

         <label className={'mediaAddTile '+(busy||images.length>=8?'disabled':'')}>
           <span className="mediaAddIcon">＋</span>
           <b>{busy?'Processando...':'Adicionar fotos'}</b>
           <small>{images.length}/8 imagens</small>
           <input type="file" accept="image/*" multiple disabled={busy||images.length>=8} onChange={e=>{upload(e.target.files);e.target.value=''}}/>
         </label>
       </div>

       <div className="mediaRailHelp">
         <span>Clique na foto para ampliar</span>
         <span>★ define a principal</span>
         <span>← → altera a ordem</span>
       </div>
     </section>

     <aside className="mediaVideoBox">
       <div className="mediaVideoIcon">▶</div>
       <b>Vídeo do produto</b>
       <p>Área preparada para vídeo da peça.</p>
       <span className="pill neutral">Integração de vídeo depois</span>
       <small>O vídeo será ativado quando adicionarmos o campo próprio no produto e nos canais de venda.</small>
     </aside>
   </div>

   {!images.length&&<div className="mediaEmptyNote">
     <b>Nenhuma foto cadastrada ainda</b>
     <span>Use “Adicionar fotos” para começar. A primeira imagem ficará como principal.</span>
   </div>}
   <details className="imageUrlsAdvanced"><summary>Opção avançada: endereços das imagens</summary><textarea value={form.image_urls||''} onChange={e=>setForm({...form,image_urls:e.target.value})}/></details>

   {zoom&&<div className="modalBackdrop imageZoomBackdrop" onMouseDown={e=>e.target===e.currentTarget&&setZoom(null)}>
     <div className="imageViewerModal imageViewerVideoStyle">
       <div className="imageViewerSimpleTitle">Imagens</div>

       <div className="imageViewerVideoStage">
         <button type="button" className="imageViewerVideoArrow prev" onClick={()=>stepZoom(-1)} disabled={images.length<2} aria-label="Foto anterior">‹</button>

         <div className="imageViewerWhiteFrame">
           <img src={zoom} alt={`Foto ${(zoomIndex>=0?zoomIndex:0)+1} da peça`}/>
           <div className="imageViewerBars">
             {images.map((src,i)=><button type="button" key={`bar-${i}`} className={src===zoom?'active':''} onClick={()=>setZoom(src)} aria-label={`Abrir foto ${i+1}`}/>)}
           </div>
         </div>

         <button type="button" className="imageViewerVideoArrow next" onClick={()=>stepZoom(1)} disabled={images.length<2} aria-label="Próxima foto">›</button>
       </div>

       <div className="imageViewerVideoFoot">
         <span>{(zoomIndex>=0?zoomIndex:0)+1} / {images.length}</span>
         <button type="button" className="ghost" onClick={()=>setZoom(null)}>Fechar</button>
       </div>
     </div>
   </div>}
 </div>
}

function ProductForm({refresh,notice,groups=[],brands=[],vehicles=[],locations=[],initialProduct=null,onClose=null}){
  // CDM DUPLICATE DETECTION V1
  const [duplicateCheck,setDuplicateCheck]=useState({loading:false,items:[],checked:false})
  const editing=!!initialProduct,[form,setForm]=useState({...productEmpty,...(initialProduct||{}),auto_publish:false}),[mlSuggestions,setMlSuggestions]=useState([]),[findingCategory,setFindingCategory]=useState(false),[marketModal,setMarketModal]=useState(null),[step,setStep]=useState('cadastro'),[categoryOpen,setCategoryOpen]=useState(false),[categoryQuery,setCategoryQuery]=useState(''),[categoryResults,setCategoryResults]=useState([]),[categoryBusy,setCategoryBusy]=useState(false),[aiBusy,setAiBusy]=useState(false),[aiResult,setAiResult]=useState(null)
  const [aiUsage,setAiUsage]=useState(null),[aiStage,setAiStage]=useState(0)
  const aiStages=['Preparando as fotos','Lendo códigos e detalhes','Identificando a peça','Montando o cadastro']
  useEffect(()=>{
    if(!aiBusy){setAiStage(0);return}
    const timer=setInterval(()=>setAiStage(v=>Math.min(v+1,aiStages.length-1)),2200)
    return()=>clearInterval(timer)
  },[aiBusy])
  useEffect(()=>{setForm({...productEmpty,...(initialProduct||{}),auto_publish:false});setStep('cadastro');if(!initialProduct)loadNextSku()},[initialProduct?.id])
  useEffect(()=>{loadAiUsage()},[])
  async function loadAiUsage(){
    try{const r=await api.get('/intelligence/product-photo-analysis-status');setAiUsage(r.data||null)}catch(e){}
  }
  async function analyzeProductPhotos(files){
    if(!files?.length||aiBusy)return
    if(aiUsage?.configured===false){notice('Cadastro de Peça com IA ainda não está configurado no servidor');return}
    if(aiUsage&&Number(aiUsage.remaining||0)<=0){notice(`Limite mensal de ${aiUsage.limit||200} Cadastros com IA atingido. O cadastro manual continua liberado.`);return}
    setAiBusy(true);setAiResult(null)
    try{
      const selected=Array.from(files).slice(0,3).filter(f=>f.type?.startsWith('image/'))
      const prepared=await Promise.all(selected.map(f=>prepareProductImage(f,false)))
      if(!prepared.length){notice('Selecione pelo menos uma foto da peça');return}
      const current=imageList(form.image_urls)
      setForm(f=>({...f,image_urls:[...prepared,...current].slice(0,8).join('\n')}))

      const aiImages=await Promise.all(prepared.map(src=>prepareAiAnalysisImage(src,1100,.78)))
      const r=await analyzeProductPhotosWithRetry({
        aiImages,
        vehicleId:form.vehicle_id?Number(form.vehicle_id):null,
        context:{name:form.name||'',brand:form.brand||'',model:form.model||'',year:form.year||'',groups:groups.map(g=>g.name)},
        notice
      })
      setAiResult(r.data)
      if(r.data?.usage)setAiUsage(r.data.usage)
      notice('IA analisou a peça. Revise as sugestões antes de aplicar')
    }catch(e){
      notice(erroPt(e.response?.data?.detail)||'Não foi possível analisar a peça por foto')
    }finally{setAiBusy(false)}
  }
  function applyAiProductSuggestions(){
    if(!aiResult)return
    const groupExists=groups.some(g=>(g.name||'').trim().toLowerCase()===(aiResult.part_group||'').trim().toLowerCase())
    setForm(f=>({...f,
      name:aiResult.marketplace_title||aiResult.name||f.name,
      category:aiResult.category||f.category,
      part_group:groupExists?aiResult.part_group:f.part_group,
      side:aiResult.side||f.side,
      position:aiResult.position||f.position,
      condition:aiResult.condition||f.condition,
      oem:aiResult.oem||f.oem,
      brand:aiResult.brand||f.brand,
      model:aiResult.model||f.model,
      year:aiResult.year||f.year,
      compatibility:aiResult.compatibility||f.compatibility,
      description:aiResult.description||f.description,
      quality_notes:aiResult.quality_notes||f.quality_notes
    }))
    notice('Sugestões da IA aplicadas. Confira os dados antes de salvar')
  }
  async function checkDuplicates(silent=false){
    const name=String(form.name||'').trim(),oem=String(form.oem||'').trim()
    if(name.length<3&&oem.length<3){setDuplicateCheck({loading:false,items:[],checked:false});return}
    setDuplicateCheck(v=>({...v,loading:true}))
    try{
      const r=await api.get('/products/duplicates',{params:{
        name,oem,
        brand:String(form.brand||'').trim(),
        model:String(form.model||'').trim(),
        year:form.year?Number(form.year):undefined,
        vehicle_id:form.vehicle_id?Number(form.vehicle_id):undefined,
        exclude_id:editing?initialProduct?.id:undefined
      }})
      const items=r.data?.items||[]
      setDuplicateCheck({loading:false,items,checked:true})
      if(!silent)notice(items.length?`${items.length} possível(is) duplicidade(s) encontrada(s)`:'Nenhuma peça duplicada encontrada')
    }catch(e){
      setDuplicateCheck(v=>({...v,loading:false}))
      if(!silent)notice('Não foi possível verificar duplicidade agora')
    }
  }
  useEffect(()=>{
    const name=String(form.name||'').trim(),oem=String(form.oem||'').trim()
    if(name.length<3&&oem.length<3){setDuplicateCheck({loading:false,items:[],checked:false});return}
    const timer=setTimeout(()=>checkDuplicates(true),700)
    return()=>clearTimeout(timer)
  },[form.name,form.oem,form.brand,form.model,form.year,form.vehicle_id,initialProduct?.id])

  async function suggestMl(){if(!form.name.trim())return notice('Informe o nome da peça primeiro');const vehicleType=mlVehicleType(form);if(!vehicleType)return notice('Escolha Carro/Caminhonete ou Caminhão primeiro');setFindingCategory(true);try{const r=await api.get('/marketplaces/mercadolivre/category-suggestions',{params:{q:`${form.name} ${form.brand} ${form.model}`.trim(),limit:3,vehicle_type:vehicleType}});setMlSuggestions(r.data||[]);if(r.data?.[0])setForm(f=>({...f,ml_category_id:r.data[0].category_id,ml_attributes_json:mlResetCategoryAttrs(f,vehicleType)}));notice(r.data?.length?'Categoria sugerida pelo Mercado Livre':'Nenhuma categoria encontrada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Conecte o Mercado Livre para sugerir categoria')}finally{setFindingCategory(false)}}
  function chooseVehicle(id){const v=vehicles.find(x=>x.id===+id);if(!v){setForm({...form,vehicle_id:null});return}setForm({...form,vehicle_id:v.id,brand:v.brand||'',model:v.model||'',year:v.year||'',compatibility:form.compatibility||`${v.brand||''} ${v.model||''} ${v.year||''}`.trim()})}
  async function loadNextSku(){if(editing)return;try{const r=await api.get('/products/next-sku');setForm(f=>({...f,sku:String(r.data?.sku||'')}))}catch(e){notice('Não foi possível gerar o próximo SKU automaticamente')}}
  async function searchCategory(){const q=String(categoryQuery||form.name||'').trim();if(!q)return notice('Digite o nome da peça ou da categoria');const vehicleType=mlVehicleType(form);if(!vehicleType)return notice('Escolha Carro/Caminhonete ou Caminhão primeiro');setCategoryBusy(true);try{const r=await api.get('/marketplaces/mercadolivre/category-suggestions',{params:{q,limit:8,vehicle_type:vehicleType}});setCategoryResults(r.data||[]);if(!(r.data||[]).length)notice('Nenhuma categoria encontrada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível pesquisar as categorias do Mercado Livre')}finally{setCategoryBusy(false)}}
  function chooseCategory(item){setForm({...form,category:item.category_name||'',ml_category_id:item.category_id||'',ml_attributes_json:mlResetCategoryAttrs(form,mlVehicleType(form))});setCategoryOpen(false);setCategoryQuery('')}
  function applyMarkup(percent){const c=Number(form.cost||0);if(!c)return notice('Informe o custo primeiro');setForm({...form,price:(c*(1+percent/100)).toFixed(2)})}
  async function save(autoPublish=false){try{if(!String(form.sku||'').trim()||!String(form.name||'').trim())return notice('Informe SKU e nome da peça');const payload={...form,auto_publish:autoPublish,price:Number(form.price||0),cost:Number(form.cost||0),stock:Number(form.stock||0),weight:Number(form.weight||0),package_length:Number(form.package_length||0),package_width:Number(form.package_width||0),package_height:Number(form.package_height||0),year:form.year?+form.year:null,vehicle_id:form.vehicle_id?+form.vehicle_id:null,location_id:form.location_id?+form.location_id:null};if(editing)await api.put(`/products/${initialProduct.id}`,payload);else await api.post('/products',payload);await refresh();notice(editing?(autoPublish?'Peça atualizada e canais ativos processados':'Peça atualizada'):(autoPublish?'Peça cadastrada e canais ativos processados':'Peça cadastrada'));if(editing){onClose?.()}else{setForm({...productEmpty});setStep('cadastro');loadNextSku()}}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar a peça')}}
  const channel=(id,label,field,desc)=><div className={'videoChannelRow '+(form[field]?'enabled':'disabled')}>
    <div className="videoChannelIdentity"><MarketLogo id={id}/><div><b>{label}</b><small>{form[field]?'Canal ativado para esta peça':desc}</small></div></div>
    <div className="videoChannelPrice"><small>Preço de venda</small><div><span>R$</span><input type="number" step="0.01" value={form.price??''} onChange={e=>setForm({...form,price:e.target.value})} placeholder="0,00"/></div></div>
    <label className="switch videoChannelSwitch"><input type="checkbox" checked={!!form[field]} onChange={e=>setForm({...form,[field]:e.target.checked})}/><i/></label>
    <button type="button" className="videoChannelAction" disabled={!form[field]} onClick={()=>setMarketModal(id)}>{form[field]?'Personalizar':'Ative o canal'}</button>
  </div>
  const steps=[['cadastro','Cadastro'],['midia','Mídia'],['publicacao','Publicação'],['precificacao','Precificação']]
  const price=Number(form.price||0),cost=Number(form.cost||0),profit=price-cost,margin=price>0?(profit/price)*100:0
  const publicationChecks=[!!String(form.name||'').trim(),!!String(form.sku||'').trim(),!!String(form.brand||'').trim(),!!String(form.model||'').trim(),Number(form.stock||0)>0,Number(form.price||0)>0,imageList(form.image_urls).length>0,!!(form.publish_mercadolivre||form.publish_shopee||form.publish_olx)]
  const publicationScore=Math.round((publicationChecks.filter(Boolean).length/publicationChecks.length)*100)
  return <section className={(editing?'productEditorBody':'panel productRegisterPage')+' videoExactPage'}>
    <div className="videoExactTitle">
      <div>
        <span>CADASTRO DE PEÇA</span>
        <h2>{editing?`Editar peça #${initialProduct.id}`:'Cadastro da peça'}</h2>
        <p>Cadastre todas as informações da peça de forma simples e rápida.</p>
      </div>
      <div className="videoExactTitleMeta">
        <div><small>SKU</small><b>{form.sku||'—'}</b></div>
        <div><small>Peça</small><b>{form.name||'Não informada'}</b></div>
      </div>
    </div>

    <div className="videoExactShell">
      <main className="videoExactMain">

        <section id="cdm-piece-cadastro" className="videoExactSection">
          <div className="videoExactSectionHead">
            <div><h3>Cadastro da peça</h3><p>Dados básicos e identificação da peça.</p></div>
          </div>

          <div className="videoExactSectionBody">
            <div className="videoExactQuickFlags">
              <label className="videoExactFlag fixed"><input type="checkbox" checked readOnly/><span><b>SKU automático</b><small>Sequencial gerado pelo CDM</small></span></label>
              <label className="videoExactFlag"><input type="checkbox" checked={form.public_catalog!==false} onChange={e=>setForm({...form,public_catalog:e.target.checked})}/><span><b>Catálogo público</b><small>Disponibilizar no catálogo da empresa</small></span></label>
            </div>

            <div className="videoExactInnovation ai">
              <div className="productAiPhoto" data-feature="CDM_AI_PHOTO_PANEL">
                <div className="productAiPhotoHead"><div><span className="aiNewBadge">NOVO · IA</span><h4>Cadastro de peça por foto</h4><p>Tire ou envie até 3 fotos. A IA identifica a peça, monta o título e sugere os dados para você revisar.</p></div><label className={'primary aiPhotoButton '+(aiBusy||aiUsage?.configured===false||Number(aiUsage?.remaining??1)<=0?'disabled':'')}>{aiBusy?'IA trabalhando...':aiUsage?.configured===false?'IA aguardando configuração':Number(aiUsage?.remaining??1)<=0?'Limite mensal atingido':'📷 Tirar ou enviar fotos'}<input type="file" accept="image/*" capture="environment" multiple disabled={aiBusy||aiUsage?.configured===false||Number(aiUsage?.remaining??1)<=0} onChange={e=>{analyzeProductPhotos(e.target.files);e.target.value=''}}/></label></div>
                {aiBusy&&<div className="aiProcessing" role="status" aria-live="polite">
                  <div className="aiProcessingTrack"><span className="aiProcessingCar">🚗</span><i/></div>
                  <div className="aiProcessingCopy"><b>{aiStages[aiStage]}</b><span>A análise continua enquanto o CDM prepara o cadastro.</span></div>
                  <div className="aiProcessingSteps">{aiStages.map((label,i)=><span key={label} className={i<=aiStage?'done':''}><i>{i<aiStage?'✓':i+1}</i>{label}</span>)}</div>
                </div>}
                <small className="aiPrivacyNote">Somente as fotos escolhidas são enviadas para análise. Confira aplicação e código OEM antes de publicar.</small>{aiUsage&&<small className="aiPrivacyNote"><b>Cadastro IA:</b> {aiUsage.used}/{aiUsage.limit} usados neste mês · {aiUsage.remaining} restantes{aiUsage.configured===false?' · aguardando chave da IA':''}</small>}
                {aiResult&&<div className="aiPhotoResult">
                  <div className="aiPhotoResultTop"><div><b>{aiResult.name||'Peça identificada parcialmente'}</b><span className={'aiConfidence '+(aiResult.confidence||'baixa')}>Confiança: {aiResult.confidence||'baixa'}</span></div><button type="button" className="primary" onClick={applyAiProductSuggestions}>✓ Aplicar sugestões</button></div>
                  <div className="aiSuggestionGrid">
                    <div><small>Categoria</small><b>{aiResult.category||'—'}</b></div>
                    <div><small>Lado / posição</small><b>{[aiResult.side,aiResult.position].filter(Boolean).join(' · ')||'—'}</b></div>
                    <div><small>OEM visível</small><b>{aiResult.oem||'Não identificado'}</b></div>
                    <div><small>Marca / modelo</small><b>{[aiResult.brand,aiResult.model,aiResult.year].filter(Boolean).join(' ')||'Não confirmado'}</b></div>
                  </div>
                  {aiResult.marketplace_title&&<div className="aiTextSuggestion"><small>TÍTULO SUGERIDO PARA ANÚNCIO</small><p>{aiResult.marketplace_title}</p></div>}
                  {aiResult.compatibility&&<div className="aiTextSuggestion"><small>APLICAÇÕES POSSÍVEIS</small><p>{aiResult.compatibility}</p></div>}
                  {!!aiResult.keywords?.length&&<div className="aiKeywords">{aiResult.keywords.map((x,i)=><span key={i}>{x}</span>)}</div>}
                  {!!aiResult.warnings?.length&&<div className="aiWarnings"><b>Confira antes de salvar:</b>{aiResult.warnings.map((x,i)=><span key={i}>• {x}</span>)}</div>}
                </div>}
              </div>
            </div>

            <div className="videoExactInnovation duplicate">
              <div className={'duplicateDetector '+(duplicateCheck.items.some(x=>x.strong)?'strong':'')}>
                <div className="duplicateDetectorHead">
                  <div><b>Detector de peça duplicada</b><small>Compara nome, OEM, marca, modelo, ano e veículo dentro da sua empresa.</small></div>
                  <button type="button" className="ghost" onClick={()=>checkDuplicates(false)} disabled={duplicateCheck.loading}>{duplicateCheck.loading?'Verificando...':'Verificar agora'}</button>
                </div>
                {duplicateCheck.items.length>0&&<div className="duplicateMatches">
                  <div className="duplicateWarning">Aviso: encontramos peça(s) parecida(s). Confira antes de cadastrar outra.</div>
                  {duplicateCheck.items.map(x=><div className="duplicateMatch" key={x.id}>
                    <div><b>SKU {x.sku||'—'} · {x.name}</b><small>{[x.brand,x.model,x.year].filter(Boolean).join(' ')}{x.oem?` · OEM ${x.oem}`:''}</small><small>{(x.reasons||[]).join(' · ')}</small></div>
                    <div className="duplicateScore"><strong>{x.score}%</strong><small>{x.strong?'Alta chance':'Possível'}</small><em>Estoque: {x.stock||0}</em></div>
                  </div>)}
                </div>}
                {duplicateCheck.checked&&!duplicateCheck.loading&&duplicateCheck.items.length===0&&<div className="duplicateClear">Nenhuma duplicidade encontrada com os dados atuais.</div>}
              </div>
            </div>

            <div className="videoExactFormGrid">
              <div className="span2"><Field label="Nome do produto *"><input value={form.name||''} onChange={e=>setForm({...form,name:e.target.value})} placeholder="Nome da peça"/></Field></div>
              <Field label="SKU"><input className="skuSequentialInput" value={form.sku||''} readOnly/></Field>
              <Field label="Quantidade"><input type="number" min="0" value={form.stock??1} onChange={e=>setForm({...form,stock:e.target.value})}/></Field>

              <VehicleBrandModel form={form} setForm={setForm} brands={brands}/>
              <Field label="Ano"><input list="cdm-product-years-v38" inputMode="numeric" maxLength="4" value={form.year||''} onChange={e=>setForm({...form,year:e.target.value.replace(/\D/g,'').slice(0,4)})} placeholder="Ex.: 2020"/><datalist id="cdm-product-years-v38">{Array.from({length:new Date().getFullYear()-1969},(_,i)=>new Date().getFullYear()+1-i).map(y=><option key={y} value={y}/>)}</datalist></Field>
              <Field label="Condição"><select value={form.condition||'used'} onChange={e=>setForm({...form,condition:e.target.value})}><option value="used">Usado</option><option value="new">Novo</option><option value="reconditioned">Recondicionado</option></select></Field>

              <Field label="Categoria"><div className="categoryField"><input value={form.category||''} onChange={e=>setForm({...form,category:e.target.value})} placeholder="Digite ou pesquise"/><button type="button" className="ghost categorySearchBtn" onClick={()=>{setCategoryQuery(form.name||form.category||'');setCategoryResults([]);setCategoryOpen(true)}}>⌕</button></div></Field>
              <Field label="Grupo"><select value={form.part_group||''} onChange={e=>setForm({...form,part_group:e.target.value})}><option value="">Selecione...</option>{groups.map(g=><option key={g.id}>{g.name}</option>)}</select></Field>
              <Field label="Código OEM / Part number"><input value={form.oem||''} onChange={e=>setForm({...form,oem:e.target.value})}/></Field>
              <Field label="Localização"><select value={form.location_id||''} onChange={e=>setForm({...form,location_id:e.target.value})}><option value="">Sem localização</option>{locations.map(l=><option key={l.id} value={l.id}>{l.code||`LOC-${l.id}`} · {l.description||l.warehouse||'Local'}</option>)}</select></Field>

              <div className="span2"><Field label="Sucata / veículo de origem"><select value={form.vehicle_id||''} onChange={e=>chooseVehicle(e.target.value)}><option value="">Sem vínculo / peça avulsa</option>{vehicles.map(v=><option key={v.id} value={v.id}>#{v.id} · {v.plate||'sem placa'} · {v.brand} {v.model} {v.year||''}</option>)}</select></Field></div>
              <Field label="Qualidade"><select value={form.quality_grade||'B'} onChange={e=>setForm({...form,quality_grade:e.target.value})}><option value="A">A — excelente</option><option value="B">B — boa</option><option value="C">C — com marcas/uso</option></select></Field>
              <Field label="Garantia (dias)"><input type="number" min="0" value={form.warranty_days??90} onChange={e=>setForm({...form,warranty_days:e.target.value})}/></Field>

              <div className="span4"><Field label="Informações adicionais"><textarea value={form.quality_notes||''} onChange={e=>setForm({...form,quality_notes:e.target.value})} placeholder="Observações da peça"/></Field></div>
            </div>
          </div>
        </section>

        <section id="cdm-piece-midia" className="videoExactSection">
          <div className="videoExactSectionHead"><div><h3>Mídia</h3><p>Vídeos e fotos da peça.</p></div></div>
          <div className="videoExactSectionBody videoExactMediaBody">
            <ProductImages form={form} setForm={setForm} notice={notice}/>
          </div>
        </section>

        <section id="cdm-piece-publicacao" className="videoExactSection">
          <div className="videoExactSectionHead"><div><h3>Publicação</h3><p>Preencha categoria, descrição e informações adicionais para os canais de venda.</p></div></div>
          <div className="videoExactSectionBody">
            <Field label="Descrição"><textarea className="videoExactDescription" value={form.description||''} onChange={e=>setForm({...form,description:e.target.value})} placeholder="Preencher aqui a descrição do anúncio, que será usada como descrição padrão da configuração."/></Field>

            <details className="videoExactCollapse">
              <summary>Dados da Embalagem <span>●</span></summary>
              <div className="videoExactCollapseBody dimensions">
                <Field label="Peso (kg)"><input type="number" step="0.01" value={form.weight??''} onChange={e=>setForm({...form,weight:e.target.value})}/></Field>
                <Field label="Comprimento (cm)"><input type="number" value={form.package_length??''} onChange={e=>setForm({...form,package_length:e.target.value})}/></Field>
                <Field label="Largura (cm)"><input type="number" value={form.package_width??''} onChange={e=>setForm({...form,package_width:e.target.value})}/></Field>
                <Field label="Altura (cm)"><input type="number" value={form.package_height??''} onChange={e=>setForm({...form,package_height:e.target.value})}/></Field>
              </div>
            </details>

            <details className="videoExactCollapse">
              <summary>Compatibilidade <span>●</span></summary>
              <div className="videoExactCollapseBody"><Field label="Aplicações da peça"><textarea value={form.compatibility||''} onChange={e=>setForm({...form,compatibility:e.target.value})} placeholder="Ex.: Corolla 2015 a 2019"/></Field></div>
            </details>

            <div className="videoExactReadiness">
              <div className="videoExactReadyHead"><div><h4>Prontidão para publicação</h4><p>Confira o que já está pronto e quais integrações precisam de ajustes antes da publicação.</p></div><b>{publicationScore}%</b></div>
              <div className="videoExactReadyBar"><i style={{width:`${publicationScore}%`}}/></div>
              <div className="videoExactReadyLegend"><span className="ok">● OK {publicationScore}%</span><span className="optional">● Opcional</span><span className="adjust">● Precisa de ajuste {100-publicationScore}%</span></div>
            </div>

            <div className="videoExactChannelList">
              <div className="videoExactChannel sale">
                <div className="videoExactChannelIdentity"><div className="videoExactChannelIcon">$</div><div><b>Venda balcão</b><span>Preço padrão do produto</span></div></div>
                <div className="videoExactChannelPrice"><small>Preço de venda:</small><div><span>R$</span><input type="number" step="0.01" value={form.price??''} onChange={e=>setForm({...form,price:e.target.value})} placeholder="0,00"/></div></div>
                <button type="button" className="videoExactManage">Gerenciar</button>
              </div>

              <div className={'videoExactChannel ml '+(form.publish_mercadolivre?'enabled':'')}>
                <div className="videoExactChannelIdentity"><MarketLogo id="mercadolivre"/><div><b>Mercado Livre</b><span>{form.publish_mercadolivre?'Canal ativado':'Não será publicado — informações pendentes'}</span></div></div>
                <div className="videoExactChannelPrice"><small>Preço de venda:</small><div><span>R$</span><input type="number" step="0.01" value={form.price??''} onChange={e=>setForm({...form,price:e.target.value})} placeholder="0,00"/></div></div>
                <label className="switch"><input type="checkbox" checked={!!form.publish_mercadolivre} onChange={e=>setForm({...form,publish_mercadolivre:e.target.checked})}/><i/></label>
                <button type="button" className="videoExactManage" disabled={!form.publish_mercadolivre} onClick={()=>setMarketModal('mercadolivre')}>Ajustar</button>
              </div>

              <div className={'videoExactChannel shopee '+(form.publish_shopee?'enabled':'')}>
                <div className="videoExactChannelIdentity"><MarketLogo id="shopee"/><div><b>Shopee</b><span>{form.publish_shopee?'Canal ativado':'Não será publicado — configuração opcional'}</span></div></div>
                <div className="videoExactChannelPrice"><small>Preço de venda:</small><div><span>R$</span><input type="number" step="0.01" value={form.price??''} onChange={e=>setForm({...form,price:e.target.value})} placeholder="0,00"/></div></div>
                <label className="switch"><input type="checkbox" checked={!!form.publish_shopee} onChange={e=>setForm({...form,publish_shopee:e.target.checked})}/><i/></label>
                <button type="button" className="videoExactManage" disabled={!form.publish_shopee} onClick={()=>setMarketModal('shopee')}>Ajustar</button>
              </div>

              <div className={'videoExactChannel olx '+(form.publish_olx?'enabled':'')}>
                <div className="videoExactChannelIdentity"><MarketLogo id="olx"/><div><b>OLX</b><span>{form.publish_olx?'Canal ativado':'Não será publicado — configuração opcional'}</span></div></div>
                <div className="videoExactChannelPrice"><small>Preço de venda:</small><div><span>R$</span><input type="number" step="0.01" value={form.price??''} onChange={e=>setForm({...form,price:e.target.value})} placeholder="0,00"/></div></div>
                <label className="switch"><input type="checkbox" checked={!!form.publish_olx} onChange={e=>setForm({...form,publish_olx:e.target.checked})}/><i/></label>
                <button type="button" className="videoExactManage" disabled={!form.publish_olx} onClick={()=>setMarketModal('olx')}>Ajustar</button>
              </div>
            </div>

            {form.publish_mercadolivre&&<div className="videoExactMlSuggest"><button type="button" className="ghost" onClick={suggestMl} disabled={findingCategory}>{findingCategory?'Buscando...':'Sugerir categoria do Mercado Livre'}</button>{mlSuggestions.length>0&&<select value={form.ml_category_id||''} onChange={e=>setForm({...form,ml_category_id:e.target.value})}>{mlSuggestions.map(x=><option key={x.category_id} value={x.category_id}>{x.category_name} · {x.category_id}</option>)}</select>}</div>}
          </div>
        </section>

        <section id="cdm-piece-precificacao" className="videoExactSection">
          <div className="videoExactSectionHead"><div><h3>Precificação</h3><p>Precificação da peça.</p></div></div>
          <div className="videoExactSectionBody">
            <div className="videoExactPricingInputs">
              <Field label="Custo de compra"><input type="number" step="0.01" value={form.cost??''} onChange={e=>setForm({...form,cost:e.target.value})} placeholder="R$ 0,00"/></Field>
              <Field label="Preço de venda"><input type="number" step="0.01" value={form.price??''} onChange={e=>setForm({...form,price:e.target.value})} placeholder="R$ 0,00"/></Field>
            </div>

            <div className="videoExactPriceRecommendation">
              <div><small>Preço mínimo</small><b>{cost?money(cost*1.30):'—'}</b><span>Referência +30%</span></div>
              <div className="recommended"><small>Preço médio</small><b>{cost?money(cost*1.50):'—'}</b><span>Referência +50%</span></div>
              <div><small>Preço máximo</small><b>{cost?money(cost*1.80):'—'}</b><span>Referência +80%</span></div>
              <div><small>Rentabilidade</small><b>{price>0?`${margin.toFixed(1)}%`:'—'}</b><span>{money(profit)} de lucro</span></div>
            </div>

            <div className="videoExactMarkup"><span>Aplicar margem:</span>{[30,50,80,100].map(v=><button type="button" key={v} onClick={()=>applyMarkup(v)}>+{v}%</button>)}</div>
          </div>
        </section>
      </main>

      <aside className="videoExactSide">
        <div className="videoExactSideNav">
          <button type="button" onClick={()=>{setStep('cadastro');document.getElementById('cdm-piece-cadastro')?.scrollIntoView({behavior:'smooth',block:'start'})}}><span>1</span>Cadastro</button>
          <button type="button" onClick={()=>{setStep('midia');document.getElementById('cdm-piece-midia')?.scrollIntoView({behavior:'smooth',block:'start'})}}><span>2</span>Mídia</button>
          <button type="button" onClick={()=>{setStep('publicacao');document.getElementById('cdm-piece-publicacao')?.scrollIntoView({behavior:'smooth',block:'start'})}}><span>3</span>Publicação</button>
          <button type="button" onClick={()=>{setStep('precificacao');document.getElementById('cdm-piece-precificacao')?.scrollIntoView({behavior:'smooth',block:'start'})}}><span>4</span>Precificação</button>
        </div>

        <div className="videoExactSideSummary">
          <small>RESUMO</small>
          <b>{form.name||'Nova peça'}</b>
          <span>SKU {form.sku||'—'}</span>
          <div><em>Qtd.</em><strong>{form.stock||0}</strong></div>
          <div><em>Preço</em><strong>{form.price?money(form.price):'—'}</strong></div>
        </div>

        <div className="videoExactSideActions">
          {editing&&<button className="ghost" onClick={onClose}>Cancelar</button>}
          <button className="ghost strong" onClick={()=>save(false)}>{editing?'Salvar alterações':'Salvar peça'}</button>
          <button className="primary" onClick={()=>save(true)}>{editing?'Salvar e sincronizar':'Salvar e publicar'}</button>
        </div>
      </aside>
    </div>

    {categoryOpen&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&setCategoryOpen(false)}><div className="v8Modal medium categoryPickerModal"><div className="modalHead"><div><small>CATEGORIAS</small><h2>Pesquisar Categoria</h2><p>Pesquise e selecione uma categoria do Mercado Livre.</p></div><button className="iconClose" onClick={()=>setCategoryOpen(false)}>×</button></div><div className="modalBody"><div className="categorySearchBar"><input autoFocus value={categoryQuery} onChange={e=>setCategoryQuery(e.target.value)} onKeyDown={e=>e.key==='Enter'&&searchCategory()} placeholder="Pesquise categorias do Mercado Livre"/><button type="button" className="primary" onClick={searchCategory} disabled={categoryBusy}>{categoryBusy?'Buscando...':'Buscar'}</button></div>{categoryResults.length>0?<div className="categoryResults"><div className="categoryResultsHead">CATEGORIAS MERCADO LIVRE</div>{categoryResults.map(item=><button type="button" key={item.category_id} onClick={()=>chooseCategory(item)}><div><strong>{item.category_name||'Categoria'}</strong><span>{item.domain_name||item.domain_id||''}</span></div><small>{item.category_id}</small></button>)}</div>:<div className="categoryEmpty">Digite o nome da peça ou categoria e clique em Buscar.</div>}</div></div></div>}
    <MarketplaceConfigModal market={marketModal} form={form} setForm={setForm} brands={brands} onClose={()=>setMarketModal(null)}/>
  </section>
}

function LabelPrintOverlay({products=[],company}){if(!products.length)return null;return <div className="printOverlay"><div className="printLabelSheet">{products.map(p=><div className="stockLabel" key={p.id}><div className="labelQr"><QRCodeSVG value={`${location.origin}/?produto=${p.id}&sku=${encodeURIComponent(p.sku||'')}`} size={122}/><small>{location.host}</small></div><div className="labelData"><b className="labelCompany">{company?.trade_name||'CDM DESMONTES'}</b><strong className="labelCode">{p.id}</strong><div className="labelDescription">{p.name}</div><div className="labelVehicle">{[p.brand,p.model,p.year].filter(Boolean).join(' ')}{p.oem?` · OEM ${p.oem}`:''}</div><div className="labelBottom"><span>{p.condition==='new'?'NOVO':'USADO'}</span><b>{p.sku}</b></div></div></div>)}</div></div>}

function PhotoViewer({product,index=0,onClose,onEdit}){const images=imageList(product?.image_urls),[pos,setPos]=useState(index),[zoom,setZoom]=useState(1);useEffect(()=>setPos(Math.min(index,Math.max(0,images.length-1))),[index,product?.id]);if(!product||!images.length)return null;const prev=()=>{setZoom(1);setPos(p=>(p-1+images.length)%images.length)},next=()=>{setZoom(1);setPos(p=>(p+1)%images.length)};return <div className="photoViewer" onMouseDown={e=>e.target===e.currentTarget&&onClose()}><div className="photoViewerStage"><img src={images[pos]} alt={product.name} style={{transform:`scale(${zoom})`}}/><div className="photoViewerTop"><button onClick={()=>setZoom(z=>Math.max(.6,z-.2))}>−</button><span>{pos+1} / {images.length}</span><button onClick={()=>setZoom(z=>Math.min(3,z+.2))}>＋</button><button onClick={onClose}>×</button></div>{images.length>1&&<><button className="photoNav left" onClick={prev}>‹</button><button className="photoNav right" onClick={next}>›</button></>}<div className="photoViewerBottom"><div><b>{product.name}</b><span>{product.sku} · {product.brand} {product.model}</span></div><button className="primary" onClick={()=>{onClose();onEdit()}}>Editar imagens</button></div></div></div>}

function ProductHistory({product,onClose}){const [rows,setRows]=useState([]),[busy,setBusy]=useState(true);useEffect(()=>{api.get('/stock/movements',{params:{limit:300,product_id:product.id}}).then(r=>setRows(r.data||[])).finally(()=>setBusy(false))},[product.id]);return <div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&onClose()}><div className="v8Modal medium"><div className="modalHead"><div><small>HISTÓRICO</small><h2>{product.name}</h2><p>Movimentações de estoque da peça {product.sku}.</p></div><button className="iconClose" onClick={onClose}>×</button></div><div className="modalBody">{busy?<p>Carregando...</p>:<Table rows={rows} cols={['created_at','kind','quantity_delta','balance_after','reference']} format={{created_at:v=>v?new Date(v).toLocaleString('pt-BR'):'—',kind:v=>({sale:'Venda',marketplace:'Canal de venda',adjustment:'Ajuste'}[v]||v)}}/>}</div></div></div>}

function PublicationInfo({product,listings,onClose}){const rows=listings.filter(x=>x.product_id===product.id);return <div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&onClose()}><div className="v8Modal medium"><div className="modalHead"><div><small>PUBLICAÇÕES</small><h2>{product.name}</h2><p>Situação da peça nos canais de venda.</p></div><button className="iconClose" onClick={onClose}>×</button></div><div className="modalBody publicationRows">{['mercadolivre','shopee','olx'].map(m=>{const r=rows.find(x=>x.marketplace===m);return <div className="publicationRow" key={m}><MarketLogo id={m}/><div><b>{marketName(m)}</b><span>{r?statusPt(r.status):'Ainda não publicada'}</span>{r?.external_id&&<small>Código externo: {r.external_id}</small>}{r?.error_message&&<em>{erroPt(r.error_message)}</em>}</div></div>})}</div></div></div>}

function Inventory({data,listings,refresh,notice,groups=[],brands=[],vehicles=[],locations=[],company}){
 const [q,setQ]=useState(''),[limit,setLimit]=useState(12),[showFilters,setShowFilters]=useState(false),[selected,setSelected]=useState([]),[editing,setEditing]=useState(null),[printItems,setPrintItems]=useState([]),[view,setView]=useState('card'),[viewer,setViewer]=useState(null),[history,setHistory]=useState(null),[publication,setPublication]=useState(null)
 // CDM SMART STOCK V1
 const [smartStock,setSmartStock]=useState(null),[smartBusy,setSmartBusy]=useState(true),[showSmart,setShowSmart]=useState(true)
 async function loadSmartStock(){setSmartBusy(true);try{const r=await api.get('/intelligence/smart-stock');setSmartStock(r.data||null)}catch(e){setSmartStock(null)}finally{setSmartBusy(false)}}
 useEffect(()=>{loadSmartStock()},[data.length])
 const rows=useMemo(()=>data.filter(p=>`${p.sku} ${p.name} ${p.brand} ${p.model}`.toLowerCase().includes(q.toLowerCase())).slice(0,limit),[data,q,limit])
 useEffect(()=>{const term=q.trim();if(term.length<2)return;const count=data.filter(p=>`${p.sku} ${p.name} ${p.brand} ${p.model}`.toLowerCase().includes(term.toLowerCase())).length;const t=setTimeout(()=>api.post('/intelligence/search-event',{query:term,results_count:count,source:'estoque'}).catch(()=>{}),900);return()=>clearTimeout(t)},[q])
 async function publish(id){try{await api.post(`/marketplaces/products/${id}/publish-all`);await refresh();notice('Canais ativos processados e sincronizados')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao publicar')}}
 async function removeOne(p){if(!confirm(`Excluir a peça ${p.name}?`))return;try{await api.delete(`/products/${p.id}`);await refresh();notice('Peça excluída')}catch(e){notice('Não foi possível excluir a peça')}}
 async function removeSelected(){if(!selected.length)return;if(!confirm(`Arquivar ${selected.length} produto(s) selecionado(s)?`))return;try{for(const id of selected)await api.delete(`/products/${id}`);setSelected([]);await refresh();notice('Produtos arquivados')}catch(e){notice('Não foi possível excluir todos os produtos')}}
 function toggle(id){setSelected(v=>v.includes(id)?v.filter(x=>x!==id):[...v,id])}
 function printLabels(items){if(!items.length)return notice('Selecione pelo menos um produto');setPrintItems(items);setTimeout(()=>window.print(),180)}
 function exportCsv(){const csv=['SKU;Produto;Marca;Modelo;Preço;Estoque;Mercado Livre;Shopee;OLX',...data.map(p=>[p.sku,p.name,p.brand,p.model,p.price,p.stock,p.publish_mercadolivre?'SIM':'NÃO',p.publish_shopee?'SIM':'NÃO',p.publish_olx?'SIM':'NÃO'].join(';'))].join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='estoque-cdm.csv';a.click()}
 function share(p){const text=`${p.name} - ${money(p.price)} - SKU ${p.sku}`;if(navigator.share)navigator.share({title:p.name,text}).catch(()=>{});else navigator.clipboard?.writeText(text).then(()=>notice('Dados da peça copiados'))}
 const locationName=p=>{const l=locations.find(x=>x.id===p.location_id);return l?(l.code||l.description||l.warehouse):p.location_id?`Local #${p.location_id}`:'Sem local'}
 return <><section className="smartStockPanel">
   <div className="smartStockHeader">
     <div><span>ESTOQUE INTELIGENTE</span><h3>Visão rápida do estoque</h3><p>Mostra peças paradas, estoque baixo, margem e sugestões de preço usando os dados da sua própria empresa.</p></div>
     <div className="smartStockHeaderActions"><button className="ghost" onClick={loadSmartStock} disabled={smartBusy}>{smartBusy?'Atualizando...':'↻ Atualizar'}</button><button className="ghost" onClick={()=>setShowSmart(!showSmart)}>{showSmart?'Ocultar':'Mostrar'}</button></div>
   </div>
   {showSmart&&<div className="smartStockBody">
     {smartBusy&&!smartStock?<div className="smartStockLoading">Analisando o estoque...</div>:smartStock?<>
       <div className="smartStockSummary">
         <div><small>Peças analisadas</small><strong>{smartStock.summary?.products_analyzed||0}</strong></div>
         <div className={(smartStock.summary?.low_stock||0)>0?'warn':''}><small>Estoque baixo / zerado</small><strong>{smartStock.summary?.low_stock||0}</strong></div>
         <div className={(smartStock.summary?.stale_120||0)>0?'warn':''}><small>Paradas há 120+ dias</small><strong>{smartStock.summary?.stale_120||0}</strong></div>
         <div><small>Valor de venda em estoque</small><strong>{money(smartStock.summary?.stock_sale_value)}</strong></div>
         <div><small>Margem estimada do estoque</small><strong>{money(smartStock.summary?.estimated_stock_margin)}</strong></div>
       </div>
       <div className="smartStockList">
         {(smartStock.items||[]).filter(x=>x.status!=='saudavel').slice(0,6).map(x=>{
           const product=data.find(p=>p.id===x.id)
           return <div className={'smartStockItem '+x.status} key={x.id}>
             <div className="smartStockItemMain"><b>SKU {x.sku||'—'} · {x.name}</b><small>{[x.brand,x.model,x.year].filter(Boolean).join(' ')||'Sem aplicação informada'}</small><span>{x.action}</span></div>
             <div className="smartStockMetrics">
               <span><small>Estoque</small><b>{x.stock} un.</b></span>
               <span><small>Parada</small><b>{x.age_days} dias</b></span>
               <span><small>Vendas 90d</small><b>{x.sold_90}</b></span>
               <span><small>Margem</small><b>{Number(x.margin_percent||0).toFixed(1)}%</b></span>
               {x.suggested_discount_percent>0&&<span className="priceSuggestion"><small>Sugestão</small><b>{money(x.suggested_price)}</b><em>-{x.suggested_discount_percent}%</em></span>}
             </div>
             {product&&<button className="ghost" onClick={()=>setEditing(product)}>Editar peça</button>}
           </div>
         })}
         {!(smartStock.items||[]).some(x=>x.status!=='saudavel')&&<div className="smartStockClear">✓ Nenhum alerta importante no estoque neste momento.</div>}
       </div>
     </>:<div className="smartStockLoading">Não foi possível carregar a análise agora.</div>}
   </div>}
 </section><div className="inventoryActions"><div><button className="labelBtn" disabled={!selected.length} onClick={()=>printLabels(data.filter(p=>selected.includes(p.id)))}>▣ Gerar etiquetas ({selected.length})</button><button className="ghost" disabled={!selected.length} onClick={removeSelected}>🗑 Excluir selecionados</button><button className="ghost" onClick={()=>setSelected(selected.length===rows.length?[]:rows.map(p=>p.id))}>{selected.length===rows.length&&rows.length?'Limpar seleção':'Selecionar visíveis'}</button></div><div><button className="ghost" onClick={()=>window.print()}>▤ Exportar PDF</button><button className="excelBtn" onClick={exportCsv}>↓ Exportar planilha</button></div></div><div className="inventoryViewBar"><span>Visualização:</span><label><input type="radio" checked={view==='card'} onChange={()=>setView('card')}/> Cartões</label><label><input type="radio" checked={view==='list'} onChange={()=>setView('list')}/> Lista</label><span className="stockMode">◉ Estoque atual</span></div><section className="panel inventoryPanel"><div className="inventoryToolbar"><label>Mostrando: <select value={limit} onChange={e=>setLimit(+e.target.value)}><option>12</option><option>24</option><option>48</option></select></label><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Pesquise pela descrição, marca, modelo ou SKU"/><button className="filterBtn" onClick={()=>setShowFilters(!showFilters)}>⌁ Mais filtros</button></div>{showFilters&&<div className="filterStrip"><span>Use a pesquisa para descrição, SKU, marca e modelo. Filtros por preço, local e quantidade entram nesta mesma tela.</span></div>}{view==='card'?<div className="productCards">{rows.map(p=><ProductCard key={p.id} p={p} listings={listings} publish={publish} selected={selected.includes(p.id)} toggle={()=>toggle(p.id)} edit={()=>setEditing(p)} print={()=>printLabels([p])} openPhoto={()=>setViewer({product:p,index:0})} history={()=>setHistory(p)} publication={()=>setPublication(p)} share={()=>share(p)} remove={()=>removeOne(p)} locationName={locationName(p)}/>)}</div>:<div className="inventoryList">{rows.map(p=><div className={'inventoryRow '+(selected.includes(p.id)?'selected':'')} key={p.id}><input type="checkbox" checked={selected.includes(p.id)} onChange={()=>toggle(p.id)}/><button className="rowImage" onClick={()=>setViewer({product:p,index:0})}>{imageList(p.image_urls)[0]?<img src={imageList(p.image_urls)[0]} alt={p.name}/>:<span>Sem foto</span>}</button><div className="rowGrow"><b>#{p.id} · {p.name}</b><small>{p.brand} {p.model} {p.year||''} · {p.sku} · {locationName(p)}</small></div><strong>{money(p.price)}</strong><span>{p.stock} un.</span><button className="ghost" onClick={()=>setEditing(p)}>Editar</button><button className="ghost" onClick={()=>printLabels([p])}>Etiqueta</button></div>)}</div>}{!rows.length&&<div className="emptyState">Nenhuma peça encontrada.</div>}</section>{editing&&<div className="modalBackdrop editorBackdrop"><div className="productEditModal"><button className="iconClose floating" onClick={()=>setEditing(null)}>×</button><ProductForm initialProduct={editing} refresh={refresh} notice={notice} groups={groups} brands={brands} vehicles={vehicles} locations={locations} onClose={()=>setEditing(null)}/></div></div>}{viewer&&<PhotoViewer product={viewer.product} index={viewer.index} onClose={()=>setViewer(null)} onEdit={()=>setEditing(viewer.product)}/>} {history&&<ProductHistory product={history} onClose={()=>setHistory(null)}/>} {publication&&<PublicationInfo product={publication} listings={listings} onClose={()=>setPublication(null)}/>}<LabelPrintOverlay products={printItems} company={company}/></>
}

function ProductCard({p,listings,publish,selected,toggle,edit,print,openPhoto,history,publication,share,remove,locationName}){
 const [tab,setTab]=useState('data'),[menu,setMenu]=useState(false),img=imageList(p.image_urls)[0]
 return <article className={'productCard v8ProductCard '+(selected?'selected':'')}>
  <div className="cardControlRow">
   <label className="productSelect"><input type="checkbox" checked={selected} onChange={toggle}/><span>Selecionar</span></label>
   <button className="cardMenuBtn" title="Mais ações" onClick={()=>setMenu(!menu)}>⋮</button>
   {menu&&<div className="cardMenu">
    <button onClick={()=>{edit();setMenu(false)}}>✎ Editar</button>
    <button onClick={()=>{publish(p.id);setMenu(false)}}>↻ Anunciar novamente</button>
    <button onClick={()=>{publication();setMenu(false)}}>◉ Ver publicação</button>
    <button onClick={()=>{edit();setMenu(false)}}>↗ Vincular peça</button>
    <button onClick={()=>{share();setMenu(false)}}>⌁ Compartilhar</button>
    <button onClick={()=>{history();setMenu(false)}}>↺ Histórico</button>
    <button onClick={()=>{print();setMenu(false)}}>▣ Imprimir etiqueta</button>
    <button onClick={()=>{publish(p.id);setMenu(false)}}>⟳ Publicar / sincronizar</button>
    <button className="dangerText" onClick={()=>{remove();setMenu(false)}}>🗑 Excluir</button>
   </div>}
  </div>
  <div className="cardTabs"><button className={tab==='data'?'active':''} onClick={()=>setTab('data')}>Dados</button><button className={tab==='compat'?'active':''} onClick={()=>setTab('compat')}>Compatibilidade</button></div>
  {tab==='data'?<>
   <div className="productName"><strong>{p.id} - {p.name}</strong><small>{p.brand} {p.model} {p.year||''}</small></div>
   <button className="productImage" onClick={openPhoto}>{img?<img src={img} alt={p.name}/>:<div className="noImage">PRODUTO<br/><b>SEM IMAGEM</b></div>}{img&&<span className="photoEye">◉ Ver foto</span>}</button>
   <div className="productMeta three"><div><small>Preço</small><b>{money(p.price)}</b></div><div><small>Estoque</small><b>{p.stock} un.</b></div><div><small>Local</small><b>{locationName}</b></div></div>
   <ListingBadges product={p} listings={listings}/>
  </>:<div className="compatibilityBody"><b>Veículos compatíveis</b><p>{p.compatibility||'Nenhuma compatibilidade cadastrada para esta peça.'}</p><small>OEM: {p.oem||'não informado'}</small></div>}
  <div className="productActions">
   <button title="Editar produto" onClick={edit}>✎ <span>Editar</span></button>
   <button title="Imprimir etiqueta" onClick={print}>▣ <span>Etiqueta</span></button>
   <button title="Publicar e sincronizar" onClick={()=>publish(p.id)}>↻ <span>Sincronizar</span></button>
  </div>
 </article>
}
function ListingBadges({product,listings}){const rows=listings.filter(x=>x.product_id===product.id),enabled={mercadolivre:product.publish_mercadolivre,shopee:product.publish_shopee,olx:product.publish_olx};return <div className="badges">{['mercadolivre','shopee','olx'].map(m=>{const r=rows.find(x=>x.marketplace===m),off=!enabled[m],ok=r?.status==='published',label=off?'Desativado':r?statusPt(r.status):'Não publicado';return <span key={m} title={off?'Canal desativado para esta peça':erroPt(r?.error_message)||label} className={'mini '+(off?'off':ok?'ok':r?'warn':'')}>{m==='mercadolivre'?'ML':m==='shopee'?'SH':'OLX'} · {label}</span>})}</div>}



function UsersPermissions({notice}){
 const [rows,setRows]=useState([]),[form,setForm]=useState({name:'',email:'',password:'',role:'cashier'})
 const roles=[['owner','Dono'],['admin','Administrador'],['manager','Gerente'],['stock','Estoque'],['cashier','Vendedor / Caixa'],['user','Somente leitura']]
 async function load(){try{setRows((await api.get('/catalog/users')).data||[])}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao carregar usuários')}}
 useEffect(()=>{load()},[])
 async function add(){try{await api.post('/catalog/users',form);setForm({name:'',email:'',password:'',role:'cashier'});await load();notice('Usuário criado')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao criar usuário')}}
 async function upd(r,p){try{await api.put(`/catalog/users/${r.id}`,{name:r.name,role:p.role??r.role,active:p.active??r.active});await load();notice('Usuário atualizado')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao atualizar')}}
 async function pass(r){const v=prompt('Nova senha (mínimo 8 caracteres)');if(!v)return;try{await api.post(`/catalog/users/${r.id}/password`,{password:v});notice('Senha alterada e sessões antigas encerradas')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao alterar senha')}}
 return <><div className="pageTitle"><div><span>EQUIPE</span><h2>Usuários e permissões</h2><p>Controle quem pode administrar, vender, gerenciar estoque ou apenas consultar.</p></div></div>
 <section className="panel"><PanelHead eyebrow="NOVO USUÁRIO" title="Adicionar acesso" text="Cada pessoa entra com seu próprio e-mail."/><div className="formGrid"><Field label="Nome"><input value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field><Field label="E-mail"><input value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></Field><Field label="Senha"><input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></Field><Field label="Perfil"><select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>{roles.map(x=><option key={x[0]} value={x[0]}>{x[1]}</option>)}</select></Field></div><button className="primary" onClick={add}>Criar usuário</button></section>
 <section className="panel"><PanelHead eyebrow="ACESSOS" title="Equipe da empresa" text="Desativar um acesso impede novos usos do sistema."/><div className="v12Users">{rows.map(r=><div className="v12User" key={r.id}><div><b>{r.name}</b><span>{r.email}</span><small>{r.last_login_at?new Date(r.last_login_at).toLocaleString('pt-BR'):'Ainda não acessou'}</small></div><select value={r.role} onChange={e=>upd(r,{role:e.target.value})}>{roles.map(x=><option key={x[0]} value={x[0]}>{x[1]}</option>)}</select><button className="ghost" onClick={()=>pass(r)}>Nova senha</button><button className={r.active?'v12Active':'v12Inactive'} onClick={()=>upd(r,{active:!r.active})}>{r.active?'Ativo':'Inativo'}</button></div>)}</div></section></>
}

function PlatformAdminV2({notice}){
 const [data,setData]=useState({summary:{},companies:[],recent_logs:[],automation:{}}),
       [filter,setFilter]=useState('all'),
       [query,setQuery]=useState(''),
       [busy,setBusy]=useState(false),
       [lastUpdate,setLastUpdate]=useState(null)
 const s=data.summary||{}, rows=data.companies||[], logs=data.recent_logs||[]
 const statusMeta={active:['Ativa','success'],trial:['Teste','info'],past_due:['Atrasada','danger'],blocked:['Bloqueada','dark'],canceled:['Cancelada','muted'],inactive:['Inativa','muted']}

 async function load(silent=false){
   if(!silent)setBusy(true)
   try{
     const r=await api.get('/admin/dashboard-v2')
     setData(r.data||{})
     setLastUpdate(new Date())
   }catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao carregar Painel SaaS do Dono')}
   finally{if(!silent)setBusy(false)}
 }
 useEffect(()=>{load();const t=setInterval(()=>load(true),60000);return()=>clearInterval(t)},[])

 async function act(c,action){
   try{
     if(action==='trial')await api.post(`/admin/companies/${c.id}/trial?days=7`)
     if(action==='active')await api.post(`/admin/companies/${c.id}/activate?days=31`)
     if(action==='past_due')await api.post(`/admin/companies/${c.id}/past-due`)
     if(action==='cancel')await api.post(`/admin/companies/${c.id}/cancel`)
     if(action==='block')await api.post(`/admin/companies/${c.id}/block`)
     if(action==='unblock')await api.post(`/admin/companies/${c.id}/unblock`)
     notice('Empresa atualizada');await load(true)
   }catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível atualizar a empresa')}
 }
 async function removeCompany(c){
   if(!confirm(`Excluir ${c.trade_name}?

Só será permitido se a empresa não possuir dados operacionais.`))return
   try{await api.delete(`/admin/companies/${c.id}`);notice('Empresa excluída');await load(true)}
   catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível excluir a empresa')}
 }
 const shown=rows.filter(c=>{
   const byStatus=filter==='all'||c.visual_status===filter
   const q=query.trim().toLowerCase()
   const byText=!q||[c.trade_name,c.legal_name,c.cnpj,c.email].some(v=>(v||'').toLowerCase().includes(q))
   return byStatus&&byText
 })
 function statusBadge(c){const [label,kind]=statusMeta[c.visual_status]||[c.visual_status||'Inativa','muted'];return <span className={`v122Status ${kind}`}><i/>{label}</span>}
 function expiry(c){
   if(!c.expires_at)return 'Sem vencimento'
   const d=new Date(c.expires_at).toLocaleDateString('pt-BR')
   if(c.visual_status==='past_due')return `Venceu em ${d}`
   if(c.days_remaining===0)return `Vence hoje · ${d}`
   if(c.days_remaining!=null&&c.days_remaining>0)return `${c.days_remaining} dia(s) · ${d}`
   return d
 }

 return <div className="v122Owner">
   <section className="v122Hero"><div><span className="v122Eyebrow">ADMINISTRAÇÃO DA PLATAFORMA</span><h2>Painel SaaS do Dono</h2><p>Clientes, assinaturas, acessos e saúde da operação em uma visão única.</p></div><div className="v122HeroActions"><span className="v122Auto"><i/> Automação ativa</span><button className="ghost" disabled={busy} onClick={()=>load()}>{busy?'Atualizando...':'↻ Atualizar'}</button></div></section>

   <section className="v122Automation"><div><b>Automático</b><span>Assinaturas vencidas mudam para <strong>Atrasada</strong> na sincronização.</span></div><div><b>Pagamento real</b><span>Quando o webhook do Mercado Pago estiver concluído, pagamento aprovado poderá reativar automaticamente.</span></div><small>{lastUpdate?`Última atualização: ${lastUpdate.toLocaleTimeString('pt-BR')}`:'Carregando...'}</small></section>

   <div className="v122Metrics">
     <div><span>EMPRESAS</span><b>{s.companies_total||0}</b><small>Total cadastrado</small></div>
     <div><span>ATIVAS</span><b>{s.active||0}</b><small>Pagantes ativas</small></div>
     <div><span>EM TESTE</span><b>{s.trial||0}</b><small>Período grátis</small></div>
     <div><span>ATRASADAS</span><b>{s.past_due||0}</b><small>Precisam atenção</small></div>
     <div><span>BLOQUEADAS</span><b>{s.blocked||0}</b><small>Sem acesso</small></div>
     <div><span>MRR PREVISTO</span><b>{money(s.projected_mrr||0)}</b><small>Base: {money(s.monthly_price||350)}/mês</small></div>
   </div>

   <section className="panel v122CompaniesPanel">
     <div className="v122PanelHead"><div><span>CLIENTES SaaS</span><h3>Empresas cadastradas</h3><p>Controle automático com intervenção manual quando você precisar.</p></div><div className="v122Search"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar empresa, CNPJ ou e-mail..."/></div></div>
     <div className="v122Filters">{[['all','Todas',s.companies_total],['active','Ativas',s.active],['trial','Teste',s.trial],['past_due','Atrasadas',s.past_due],['blocked','Bloqueadas',s.blocked],['canceled','Canceladas',s.canceled]].map(([k,l,n])=><button key={k} className={filter===k?'active':''} onClick={()=>setFilter(k)}>{l}<b>{n||0}</b></button>)}</div>
     <div className="v122CompanyTable">
       <div className="v122CompanyRow head"><span>Empresa</span><span>Status</span><span>Vencimento</span><span>Uso</span><span>Ações</span></div>
       {shown.map(c=><div className="v122CompanyRow" key={c.id}>
         <div className="v122CompanyIdentity"><b>{c.trade_name}</b><span>{c.email||c.cnpj||'Sem contato cadastrado'}</span><small>Empresa #{c.id}</small></div>
         <div>{statusBadge(c)}</div>
         <div className="v122Expiry"><b>{expiry(c)}</b><small>{c.subscription_status||'inactive'}</small></div>
         <div className="v122Usage"><span><b>{c.users}</b> usuários</span><span><b>{c.products}</b> peças</span><span><b>{c.sales}</b> vendas</span></div>
         <div className="v122Actions"><select defaultValue="" onChange={e=>{const v=e.target.value;e.target.value='';if(v)act(c,v)}}><option value="">Alterar situação...</option><option value="trial">Dar teste · 7 dias</option><option value="active">Ativar · 31 dias</option><option value="past_due">Marcar como atrasada</option><option value="cancel">Cancelar assinatura</option>{c.active?<option value="block">Bloquear acesso</option>:<option value="unblock">Liberar acesso</option>}</select><button className="v122Delete" onClick={()=>removeCompany(c)} title="Só exclui empresa sem dados operacionais">Excluir</button></div>
       </div>)}
       {!shown.length&&<div className="v122Empty">Nenhuma empresa encontrada com esse filtro.</div>}
     </div>
   </section>

   <div className="v122BottomGrid">
     <section className="panel"><div className="v122PanelHead"><div><span>MONITORAMENTO</span><h3>Atividades recentes</h3><p>Últimas ações registradas na plataforma.</p></div></div><div className="v122Logs">{logs.slice(0,30).map(x=><div key={x.id}><i/><div><b>{x.action}</b><span>{x.entity||'sistema'} {x.entity_id||''}</span></div><small>{x.created_at?new Date(x.created_at).toLocaleString('pt-BR'):'—'}</small></div>)}{!logs.length&&<div className="v122Empty">Nenhum log recente.</div>}</div></section>
     <section className="panel"><div className="v122PanelHead"><div><span>RESUMO OPERACIONAL</span><h3>Uso da plataforma</h3><p>Visão rápida da base inteira.</p></div></div><div className="v122Ops"><div><span>Usuários</span><b>{s.users_total||0}</b></div><div><span>Peças cadastradas</span><b>{s.products_total||0}</b></div><div><span>Vendas registradas</span><b>{s.sales_total||0}</b></div><div><span>Sincronizados agora</span><b>{s.synced_now||0}</b></div></div></section>
   </div>
 </div>
}

function CatalogModule({tab,data,refresh,notice}){if(tab==='tax')return <TaxConfig data={data.tax} refresh={refresh} notice={notice}/>;if(tab==='suppliers')return <SuppliersModule rows={data.suppliers||[]} refresh={refresh} notice={notice}/>;if(tab==='customers')return <CustomersModule rows={data.customers||[]} refresh={refresh} notice={notice}/>;if(tab==='carriers')return <CarriersModule rows={data.carriers||[]} refresh={refresh} notice={notice}/>;if(tab==='sellers')return <SellersModule rows={data.sellers||[]} refresh={refresh} notice={notice}/>;if(tab==='part-groups')return <PartGroupsModule rows={data.partGroups||[]} refresh={refresh} notice={notice}/>;if(tab==='locations')return <LocationsModule rows={data.locations||[]} refresh={refresh} notice={notice}/>;const cfg={customers:{title:'Clientes',endpoint:'customers',fields:['name','cpf_cnpj','phone','email','address']},carriers:{title:'Transportadoras',endpoint:'carriers',fields:['name','cnpj','phone','email']},sellers:{title:'Vendedores',endpoint:'sellers',fields:['name','email','phone','commission_rate']},'part-groups':{title:'Grupo de peças',endpoint:'part-groups',fields:['name','description']}}[tab],arr=tab==='part-groups'?data.partGroups:data[tab]||[];return <GenericCrud cfg={cfg} rows={arr} refresh={refresh} notice={notice}/>}

function CustomersModule({rows,refresh,notice}){
 const empty={name:'',cpf_cnpj:'',phone:'',email:'',cep:'',address:'',neighborhood:'',city:'',state:'RJ',number:'',complement:''}
 const [open,setOpen]=useState(false),[form,setForm]=useState(empty),[search,setSearch]=useState(''),[cepBusy,setCepBusy]=useState(false),[editingId,setEditingId]=useState(null)
 const filtered=useMemo(()=>{const q=search.trim().toLowerCase();if(!q)return rows;return rows.filter(x=>[x.name,x.cpf_cnpj,x.phone,x.email,x.address].some(v=>String(v||'').toLowerCase().includes(q)))},[rows,search])
 const maskDoc=v=>{const d=String(v||'').replace(/\D/g,'').slice(0,14);if(d.length<=11)return d.replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d{1,2})$/,'$1-$2');return d.replace(/^(\d{2})(\d)/,'$1.$2').replace(/^(\d{2})\.(\d{3})(\d)/,'$1.$2.$3').replace(/\.(\d{3})(\d)/,'.$1/$2').replace(/(\d{4})(\d{1,2})$/,'$1-$2')}
 const maskPhone=v=>{const d=String(v||'').replace(/\D/g,'').slice(0,11);return d.length<=10?d.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{4})(\d)/,'$1-$2'):d.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{5})(\d)/,'$1-$2')}
 const maskCep=v=>String(v||'').replace(/\D/g,'').slice(0,8).replace(/(\d{5})(\d)/,'$1-$2')
 function splitAddress(value){
   const parts=String(value||'').split(' · ').map(x=>x.trim()).filter(Boolean)
   let address=parts[0]||'',number='',neighborhood=parts[1]||'',city='',state='RJ',cep='',complement=''
   const mFirst=address.match(/^(.*),\s*([^,]+)$/)
   if(mFirst){address=mFirst[1].trim();number=mFirst[2].trim()}
   const cityPart=parts[2]||''
   const mCity=cityPart.match(/^(.*?)(?:\s*-\s*([A-Za-z]{2}))?$/)
   if(mCity){city=(mCity[1]||'').trim();state=(mCity[2]||'RJ').toUpperCase()}
   const cepIndex=parts.findIndex(x=>/^CEP\s+/i.test(x))
   if(cepIndex>=0)cep=parts[cepIndex].replace(/^CEP\s+/i,'').trim()
   const known=new Set([0,1,2,cepIndex])
   complement=parts.filter((_,idx)=>idx>2&&!known.has(idx)).join(' · ')
   return {address,number,neighborhood,city,state,cep,complement}
 }
 function newCustomer(){setEditingId(null);setForm(empty);setOpen(true)}
 function editCustomer(row){
   const addr=splitAddress(row.address)
   setEditingId(row.id)
   setForm({...empty,...addr,name:row.name||'',cpf_cnpj:row.cpf_cnpj||'',phone:row.phone||'',email:row.email||''})
   setOpen(true)
 }
 async function buscarCep(raw=form.cep){
   const cep=String(raw||'').replace(/\D/g,'')
   if(cep.length!==8)return
   setCepBusy(true)
   try{
     const r=await fetch(`https://viacep.com.br/ws/${cep}/json/`)
     const d=await r.json()
     if(d.erro)return notice('CEP não encontrado')
     setForm(f=>({...f,address:d.logradouro||'',neighborhood:d.bairro||'',city:d.localidade||'',state:d.uf||'RJ'}))
   }catch(e){notice('Não foi possível consultar o CEP')}finally{setCepBusy(false)}
 }
 useEffect(()=>{
   if(!open)return
   const cep=String(form.cep||'').replace(/\D/g,'')
   if(cep.length!==8)return
   const t=setTimeout(()=>buscarCep(cep),350)
   return ()=>clearTimeout(t)
 },[form.cep,open])
 async function save(){
   try{
     if(!form.name.trim())return notice('Informe o nome do cliente')
     const first=[form.address,form.number].filter(Boolean).join(', ')
     const cityState=[form.city,form.state].filter(Boolean).join(' - ')
     const fullAddress=[first,form.neighborhood,cityState,form.cep?`CEP ${form.cep}`:'',form.complement].filter(Boolean).join(' · ')
     const payload={name:form.name.trim(),cpf_cnpj:form.cpf_cnpj,phone:form.phone,email:form.email,address:fullAddress}
     const wasEditing=!!editingId
     if(wasEditing)await api.put(`/catalog/customers/${editingId}`,payload)
     else await api.post('/catalog/customers',payload)
     setForm(empty);setEditingId(null);setOpen(false);await refresh();notice(wasEditing?'Cliente atualizado com sucesso':'Cliente cadastrado com sucesso')
   }catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar cliente')}
 }
 return <>
  <div className="pageTitle"><div><span>CADASTROS</span><h2>Clientes</h2><p>Cadastre, encontre e corrija os dados dos clientes da sua empresa.</p></div><button className="primary" onClick={newCustomer}>＋ Cadastrar cliente</button></div>
  <section className="panel customersPanel">
   <div className="customerToolbar">
    <div><b>Clientes cadastrados</b><small>{rows.length} {rows.length===1?'cliente':'clientes'}</small></div>
    <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar por nome, CPF/CNPJ, telefone ou e-mail..."/>
   </div>
   {filtered.length?<div className="customerEditRows">
    <div className="customerEditHead"><span>Cliente</span><span>Documento</span><span>Contato</span><span>Endereço</span><span>Ações</span></div>
    {filtered.map(row=><div className="customerEditRow" key={row.id}>
      <div><b>{row.name||'—'}</b><small>#{row.id} · {row.email||'Sem e-mail'}</small></div>
      <span>{row.cpf_cnpj||'—'}</span><span>{row.phone||'—'}</span><span className="customerAddressCell">{row.address||'—'}</span>
      <button className="ghost editRegisterBtn" onClick={()=>editCustomer(row)}>✎ Editar</button>
    </div>)}
   </div>:<div className="emptyState">{search?'Nenhum cliente encontrado para essa busca.':'Nenhum cliente cadastrado ainda. Clique em “Cadastrar cliente” para começar.'}</div>}
  </section>
  {open&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&setOpen(false)}><div className="v8Modal large">
   <div className="modalHead"><div><small>{editingId?'EDIÇÃO DE CLIENTE':'NOVO CLIENTE'}</small><h2>{editingId?'Editar cliente':'Cadastrar cliente'}</h2><p>{editingId?'Corrija os dados necessários e salve as alterações.':'Preencha os dados principais. O endereço pode ser preenchido automaticamente pelo CEP.'}</p></div><button className="iconClose" onClick={()=>setOpen(false)}>×</button></div>
   <div className="modalBody"><div className="formGrid three">
     <Field label="Nome / Razão Social *"><input className={!form.name?'requiredInput':''} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field>
     <Field label="CPF / CNPJ"><input value={form.cpf_cnpj} onChange={e=>setForm({...form,cpf_cnpj:maskDoc(e.target.value)})}/></Field>
     <Field label="Telefone / WhatsApp"><input value={form.phone} onChange={e=>setForm({...form,phone:maskPhone(e.target.value)})}/></Field>
     <Field label="E-mail"><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></Field>
     <Field label="CEP"><div className="inputAction"><input value={form.cep} onChange={e=>setForm({...form,cep:maskCep(e.target.value)})} placeholder="00000-000"/><button type="button" className="ghost" onClick={()=>buscarCep()}>{cepBusy?'...':'Buscar'}</button></div></Field>
     <Field label="Logradouro"><input value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/></Field>
     <Field label="Número"><input value={form.number} onChange={e=>setForm({...form,number:e.target.value})}/></Field>
     <Field label="Bairro"><input value={form.neighborhood} onChange={e=>setForm({...form,neighborhood:e.target.value})}/></Field>
     <Field label="Cidade"><input value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/></Field>
     <Field label="UF"><input maxLength="2" value={form.state} onChange={e=>setForm({...form,state:e.target.value.toUpperCase()})}/></Field>
     <Field label="Complemento"><input value={form.complement} onChange={e=>setForm({...form,complement:e.target.value})}/></Field>
   </div></div>
   <div className="modalFoot"><button className="ghost" onClick={()=>setOpen(false)}>Cancelar</button><button className="primary" onClick={save}>{editingId?'Salvar alterações':'Salvar cliente'}</button></div>
  </div></div>}
 </>
}

function CarriersModule({rows,refresh,notice}){
 const empty={name:'',cnpj:'',phone:'',email:''}
 const [open,setOpen]=useState(false),[form,setForm]=useState(empty),[search,setSearch]=useState(''),[editingId,setEditingId]=useState(null)
 const filtered=useMemo(()=>{const q=search.trim().toLowerCase();if(!q)return rows;return rows.filter(x=>[x.name,x.cnpj,x.phone,x.email].some(v=>String(v||'').toLowerCase().includes(q)))},[rows,search])
 const maskCnpj=v=>{const d=String(v||'').replace(/\D/g,'').slice(0,14);return d.replace(/^(\d{2})(\d)/,'$1.$2').replace(/^(\d{2})\.(\d{3})(\d)/,'$1.$2.$3').replace(/\.(\d{3})(\d)/,'.$1/$2').replace(/(\d{4})(\d{1,2})$/,'$1-$2')}
 const maskPhone=v=>{const d=String(v||'').replace(/\D/g,'').slice(0,11);return d.length<=10?d.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{4})(\d)/,'$1-$2'):d.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{5})(\d)/,'$1-$2')}
 function novo(){setEditingId(null);setForm(empty);setOpen(true)}
 function editar(x){setEditingId(x.id);setForm({name:x.name||'',cnpj:x.cnpj||'',phone:x.phone||'',email:x.email||''});setOpen(true)}
 function fechar(){setOpen(false);setEditingId(null);setForm(empty)}
 async function save(){try{if(!form.name.trim())return notice('Informe o nome da transportadora');const editing=!!editingId;if(editing)await api.put(`/catalog/carriers/${editingId}`,form);else await api.post('/catalog/carriers',form);fechar();await refresh();notice(editing?'Transportadora atualizada com sucesso':'Transportadora cadastrada com sucesso')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar transportadora')}}
 return <>
  <div className="pageTitle"><div><span>CADASTROS</span><h2>Transportadoras</h2><p>Organize as transportadoras usadas nas entregas e expedições da empresa.</p></div><button className="primary" onClick={novo}>＋ Cadastrar transportadora</button></div>
  <section className="panel carriersPanel"><div className="carrierToolbar"><div><b>Transportadoras cadastradas</b><small>{rows.length} {rows.length===1?'transportadora':'transportadoras'}</small></div><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar por nome, CNPJ, telefone ou e-mail..."/></div>
   {filtered.length?<div className="catalogManageList">{filtered.map(x=><div className="catalogManageRow" key={x.id}><div><b>{x.name||'Sem nome'}</b><small>{[x.cnpj,x.phone,x.email].filter(Boolean).join(' · ')||'Sem dados adicionais'}</small></div><span>#{x.id}</span><button className="ghost editRegisterBtn" onClick={()=>editar(x)}>✎ Editar</button></div>)}</div>:<div className="emptyState">Nenhuma transportadora encontrada.</div>}</section>
  {open&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&fechar()}><div className="v8Modal medium carrierModal"><div className="modalHead"><div><small>TRANSPORTADORAS</small><h2>{editingId?'Editar transportadora':'Cadastrar transportadora'}</h2><p>{editingId?'Corrija os dados e salve as alterações.':'Informe os dados principais da transportadora.'}</p></div><button className="iconClose" onClick={fechar}>×</button></div><div className="modalBody"><div className="formGrid two"><Field label="Nome da transportadora *"><input autoFocus className={!form.name?'requiredInput':''} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field><Field label="CNPJ"><input value={form.cnpj} onChange={e=>setForm({...form,cnpj:maskCnpj(e.target.value)})}/></Field><Field label="Telefone / WhatsApp"><input value={form.phone} onChange={e=>setForm({...form,phone:maskPhone(e.target.value)})}/></Field><Field label="E-mail"><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></Field></div></div><div className="modalFoot"><button className="ghost" onClick={fechar}>Cancelar</button><button className="primary" onClick={save}>{editingId?'Salvar alterações':'Salvar transportadora'}</button></div></div></div>}
 </>
}

function SellersModule({rows,refresh,notice}){
 const empty={name:'',email:'',phone:'',commission_rate:''}
 const [open,setOpen]=useState(false),[form,setForm]=useState(empty),[search,setSearch]=useState(''),[editingId,setEditingId]=useState(null)
 const filtered=useMemo(()=>{const q=search.trim().toLowerCase();if(!q)return rows;return rows.filter(x=>[x.name,x.email,x.phone,x.commission_rate].some(v=>String(v??'').toLowerCase().includes(q)))},[rows,search])
 const maskPhone=v=>{const d=String(v||'').replace(/\D/g,'').slice(0,11);return d.length<=10?d.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{4})(\d)/,'$1-$2'):d.replace(/^(\d{2})(\d)/,'($1) $2').replace(/(\d{5})(\d)/,'$1-$2')}
 function novo(){setEditingId(null);setForm(empty);setOpen(true)}
 function editar(x){setEditingId(x.id);setForm({name:x.name||'',email:x.email||'',phone:x.phone||'',commission_rate:x.commission_rate??''});setOpen(true)}
 function fechar(){setOpen(false);setEditingId(null);setForm(empty)}
 async function save(){try{if(!form.name.trim())return notice('Informe o nome do vendedor');const rate=form.commission_rate===''?0:Number(form.commission_rate);if(Number.isNaN(rate)||rate<0||rate>100)return notice('A comissão deve ficar entre 0% e 100%');const editing=!!editingId,payload={...form,commission_rate:rate};if(editing)await api.put(`/catalog/sellers/${editingId}`,payload);else await api.post('/catalog/sellers',payload);fechar();await refresh();notice(editing?'Vendedor atualizado com sucesso':'Vendedor cadastrado com sucesso')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar vendedor')}}
 return <>
  <div className="pageTitle"><div><span>CADASTROS</span><h2>Vendedores</h2><p>Cadastre a equipe comercial e defina a comissão de cada vendedor.</p></div><button className="primary" onClick={novo}>＋ Cadastrar vendedor</button></div>
  <section className="panel sellersPanel"><div className="sellerToolbar"><div><b>Vendedores cadastrados</b><small>{rows.length} {rows.length===1?'vendedor':'vendedores'}</small></div><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar por nome, telefone ou e-mail..."/></div>
   {filtered.length?<div className="catalogManageList">{filtered.map(x=><div className="catalogManageRow" key={x.id}><div><b>{x.name||'Sem nome'}</b><small>{[x.phone,x.email].filter(Boolean).join(' · ')||'Sem contato'} · Comissão {Number(x.commission_rate||0).toLocaleString('pt-BR',{maximumFractionDigits:2})}%</small></div><span>#{x.id}</span><button className="ghost editRegisterBtn" onClick={()=>editar(x)}>✎ Editar</button></div>)}</div>:<div className="emptyState">Nenhum vendedor encontrado.</div>}</section>
  {open&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&fechar()}><div className="v8Modal medium sellerModal"><div className="modalHead"><div><small>VENDEDORES</small><h2>{editingId?'Editar vendedor':'Cadastrar vendedor'}</h2><p>{editingId?'Corrija os dados e a comissão do vendedor.':'Informe os dados do vendedor.'}</p></div><button className="iconClose" onClick={fechar}>×</button></div><div className="modalBody"><div className="formGrid two"><Field label="Nome do vendedor *"><input autoFocus className={!form.name?'requiredInput':''} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field><Field label="Telefone / WhatsApp"><input value={form.phone} onChange={e=>setForm({...form,phone:maskPhone(e.target.value)})}/></Field><Field label="E-mail"><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></Field><Field label="Comissão (%)"><div className="commissionInput"><input type="number" min="0" max="100" step="0.01" value={form.commission_rate} onChange={e=>setForm({...form,commission_rate:e.target.value})}/><span>%</span></div></Field></div></div><div className="modalFoot"><button className="ghost" onClick={fechar}>Cancelar</button><button className="primary" onClick={save}>{editingId?'Salvar alterações':'Salvar vendedor'}</button></div></div></div>}
 </>
}

function PartGroupsModule({rows,refresh,notice}){
 const empty={name:'',description:''}
 const [open,setOpen]=useState(false),[form,setForm]=useState(empty),[search,setSearch]=useState(''),[editingId,setEditingId]=useState(null)
 const filtered=useMemo(()=>{const q=search.trim().toLowerCase();if(!q)return rows;return rows.filter(x=>[x.name,x.description].some(v=>String(v||'').toLowerCase().includes(q)))},[rows,search])
 function novo(){setEditingId(null);setForm(empty);setOpen(true)}
 function editar(x){setEditingId(x.id);setForm({name:x.name||'',description:x.description||''});setOpen(true)}
 function fechar(){setOpen(false);setEditingId(null);setForm(empty)}
 async function save(){try{if(!form.name.trim())return notice('Informe o nome do grupo de peças');const editing=!!editingId,payload={name:form.name.trim(),description:form.description.trim()};if(editing)await api.put(`/catalog/part-groups/${editingId}`,payload);else await api.post('/catalog/part-groups',payload);fechar();await refresh();notice(editing?'Grupo de peças atualizado com sucesso':'Grupo de peças cadastrado com sucesso')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar grupo de peças')}}
 return <>
  <div className="pageTitle"><div><span>CADASTROS</span><h2>Grupo de peças</h2><p>Crie grupos para organizar melhor o cadastro, o estoque e a busca das peças.</p></div><button className="primary" onClick={novo}>＋ Novo grupo</button></div>
  <section className="panel partGroupsPanel"><div className="partGroupToolbar"><div><b>Grupos cadastrados</b><small>{rows.length} {rows.length===1?'grupo':'grupos'}</small></div><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar por nome ou descrição..."/></div>
   {filtered.length?<div className="partGroupList">{filtered.map(g=><div className="partGroupRow catalogEditableRow" key={g.id}><div className="partGroupIcon">▦</div><div><b>{g.name||'Grupo sem nome'}</b><small>{g.description||'Sem descrição cadastrada'}</small></div><span>#{g.id}</span><button className="ghost editRegisterBtn" onClick={()=>editar(g)}>✎ Editar</button></div>)}</div>:<div className="emptyState">Nenhum grupo encontrado.</div>}</section>
  {open&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&fechar()}><div className="v8Modal medium partGroupModal"><div className="modalHead"><div><small>GRUPO DE PEÇAS</small><h2>{editingId?'Editar grupo':'Novo grupo'}</h2><p>{editingId?'Corrija o nome ou a descrição do grupo.':'Use nomes simples para facilitar a organização.'}</p></div><button className="iconClose" onClick={fechar}>×</button></div><div className="modalBody"><div className="formGrid"><Field label="Nome do grupo *"><input autoFocus className={!form.name?'requiredInput':''} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field><Field label="Descrição"><textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></Field></div></div><div className="modalFoot"><button className="ghost" onClick={fechar}>Cancelar</button><button className="primary" onClick={save}>{editingId?'Salvar alterações':'Salvar grupo'}</button></div></div></div>}
 </>
}

function GenericCrud({cfg,rows,refresh,notice}){const initial=Object.fromEntries(cfg.fields.map(f=>[f,f==='commission_rate'?0:''])),[form,setForm]=useState(initial);async function add(){try{await api.post(`/catalog/${cfg.endpoint}`,form);setForm(initial);await refresh();notice(`${cfg.title}: cadastro salvo`)}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar')}}return <section className="panel"><PanelHead eyebrow="CADASTROS" title={cfg.title} text="Cadastro separado por empresa e usuário."/><div className="formGrid">{cfg.fields.map(f=><Field key={f} label={pretty(f)}>{f==='description'||f==='address'?<textarea value={form[f]} onChange={e=>setForm({...form,[f]:e.target.value})}/>:<input type={f==='commission_rate'?'number':'text'} value={form[f]} onChange={e=>setForm({...form,[f]:f==='commission_rate'?+e.target.value:e.target.value})}/>}</Field>)}</div><button className="primary" onClick={add}>+ Salvar cadastro</button><Table rows={rows} cols={['id',...cfg.fields]}/></section>}

function LocationsModule({rows,refresh,notice}){
 const empty={code:'',description:'',max_quantity:'',auto_generate:true,warehouse:'',aisle:'',shelf:'',bin:'',active:true}
 const [open,setOpen]=useState(false),[form,setForm]=useState(empty),[editingId,setEditingId]=useState(null)
 const path=[form.warehouse,form.aisle,form.shelf,form.bin].filter(Boolean).join(' › ')
 function novo(){setEditingId(null);setForm(empty);setOpen(true)}
 function editar(x){setEditingId(x.id);setForm({code:x.code||'',description:x.description||'',max_quantity:x.max_quantity||'',auto_generate:false,warehouse:x.warehouse||'',aisle:x.aisle||'',shelf:x.shelf||'',bin:x.bin||'',active:x.active!==false});setOpen(true)}
 function fechar(){setOpen(false);setEditingId(null);setForm(empty)}
 async function save(){try{if(!form.description.trim())return notice('Informe o nome da localização');const editing=!!editingId,payload={...form,auto_generate:!editing,code:editing?(form.code||''):'',max_quantity:Number(form.max_quantity||0)};if(editing)await api.put(`/catalog/locations/${editingId}`,payload);else await api.post('/catalog/locations',payload);fechar();await refresh();notice(editing?'Localização atualizada':'Localização cadastrada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar localização')}}
 return <>
  <div className="pageTitle"><div><span>CADASTROS</span><h2>Localizações do estoque</h2><p>Crie locais fáceis de entender, como Depósito 1 › Corredor A › Prateleira 2 › Posição 3.</p></div><button className="primary" onClick={novo}>＋ Nova localização</button></div>
  <section className="panel"><div className="locationList">{rows.length?rows.map(l=><div className="locationRow catalogEditableRow" key={l.id}><div className="locationCode">{l.code||`LOC-${l.id}`}</div><div><b>{l.description||'Localização'}</b><small>{[l.warehouse,l.aisle,l.shelf,l.bin].filter(Boolean).join(' › ')||'Sem detalhes adicionais'}</small></div><span>{l.max_quantity?`Limite: ${l.max_quantity}`:'Sem limite'}</span><span className={l.active!==false?'pill success':'pill neutral'}>{l.active!==false?'Ativa':'Inativa'}</span><button className="ghost editRegisterBtn" onClick={()=>editar(l)}>✎ Editar</button></div>):<div className="emptyState">Nenhuma localização cadastrada.</div>}</div></section>
  {open&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&fechar()}><div className="v8Modal locationEasyModal"><div className="modalHead"><div><small>ESTOQUE</small><h2>{editingId?'Editar localização':'Nova localização'}</h2><p>{editingId?'Atualize o local sem perder o código já usado no estoque.':'Você só precisa dar um nome. O código é criado automaticamente.'}</p></div><button className="iconClose" onClick={fechar}>×</button></div><div className="modalBody"><div className="locationSimpleGrid"><div className="locationNameField"><Field label="Nome da localização *"><input autoFocus className={!form.description?'requiredInput':''} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></Field></div><Field label="Depósito / Área"><input value={form.warehouse} onChange={e=>setForm({...form,warehouse:e.target.value})}/></Field><Field label="Corredor"><input value={form.aisle} onChange={e=>setForm({...form,aisle:e.target.value.toUpperCase()})}/></Field><Field label="Prateleira"><input value={form.shelf} onChange={e=>setForm({...form,shelf:e.target.value})}/></Field><Field label="Posição"><input value={form.bin} onChange={e=>setForm({...form,bin:e.target.value})}/></Field></div><div className="locationPreview"><small>COMO VAI APARECER</small><b>{form.description||'Nome da localização'}</b><span>{path||'Sem detalhes adicionais'}</span><em>{editingId?`Código mantido: ${form.code||'automático'}`:'O código será gerado automaticamente ao salvar.'}</em></div><details className="locationAdvanced"><summary>Opções avançadas</summary><div><Field label="Limite de peças (opcional)"><input type="number" min="0" value={form.max_quantity} onChange={e=>setForm({...form,max_quantity:e.target.value})}/></Field><label className="inlineCheck"><input type="checkbox" checked={form.active!==false} onChange={e=>setForm({...form,active:e.target.checked})}/><span>Localização ativa</span></label></div></details></div><div className="modalFoot"><button className="ghost" onClick={fechar}>Cancelar</button><button className="primary" onClick={save}>{editingId?'Salvar alterações':'Salvar localização'}</button></div></div></div>}
 </>
}

function SuppliersModule({rows,refresh,notice}){
 const empty={name:'',trade_name:'',cpf_cnpj:'',rg_ie:'',mobile:'',phone:'',cep:'',city:'',state:'RJ',number:'',address:'',neighborhood:'',complement:'',ibge:'',email:'',active:true}
 const [open,setOpen]=useState(false),[form,setForm]=useState(empty),[cepBusy,setCepBusy]=useState(false),[editingId,setEditingId]=useState(null)
 function novo(){setEditingId(null);setForm(empty);setOpen(true)}
 function editar(x){setEditingId(x.id);setForm({...empty,...x});setOpen(true)}
 function fechar(){setOpen(false);setEditingId(null);setForm(empty)}
 async function buscarCep(){const cep=String(form.cep||'').replace(/\D/g,'');if(cep.length!==8)return;setCepBusy(true);try{const r=await fetch(`https://viacep.com.br/ws/${cep}/json/`),d=await r.json();if(!d.erro)setForm(f=>({...f,address:d.logradouro||f.address,neighborhood:d.bairro||f.neighborhood,city:d.localidade||f.city,state:d.uf||f.state,ibge:d.ibge||f.ibge}))}catch(e){}finally{setCepBusy(false)}}
 async function save(){try{if(!form.cpf_cnpj.trim()||!form.name.trim())return notice('Preencha CPF / CNPJ e Razão Social / Nome');const editing=!!editingId,payload={name:form.name||'',trade_name:form.trade_name||'',cpf_cnpj:form.cpf_cnpj||'',rg_ie:form.rg_ie||'',mobile:form.mobile||'',phone:form.phone||'',cep:form.cep||'',city:form.city||'',state:form.state||'',number:form.number||'',address:form.address||'',neighborhood:form.neighborhood||'',complement:form.complement||'',ibge:form.ibge||'',email:form.email||'',active:form.active!==false};if(editing)await api.put(`/catalog/suppliers/${editingId}`,payload);else await api.post('/catalog/suppliers',payload);fechar();await refresh();notice(editing?'Fornecedor atualizado':'Fornecedor cadastrado')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar fornecedor')}}
 return <>
  <div className="pageTitle"><div><span>CADASTROS</span><h2>Fornecedores</h2><p>Dados comerciais, fiscais, contato e endereço em um único cadastro.</p></div><button className="primary" onClick={novo}>＋ Adicionar fornecedor</button></div>
  <section className="panel">{rows.length?<div className="catalogManageList">{rows.map(x=><div className="catalogManageRow" key={x.id}><div><b>{x.name||'Sem nome'}{x.trade_name?` · ${x.trade_name}`:''}</b><small>{[x.cpf_cnpj,x.mobile||x.phone,[x.city,x.state].filter(Boolean).join('/')].filter(Boolean).join(' · ')}</small></div><span className={x.active!==false?'pill success':'pill neutral'}>{x.active!==false?'Ativo':'Inativo'}</span><button className="ghost editRegisterBtn" onClick={()=>editar(x)}>✎ Editar</button></div>)}</div>:<div className="emptyState">Nenhum fornecedor cadastrado.</div>}</section>
  {open&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&fechar()}><div className="v8Modal large"><div className="modalHead"><div><small>FORNECEDOR</small><h2>{editingId?'Editar fornecedor':'Cadastrar fornecedor'}</h2><p>Os campos marcados com * são obrigatórios.</p></div><button className="iconClose" onClick={fechar}>×</button></div><div className="modalBody"><div className="formGrid three"><Field label="CPF / CNPJ *"><input className={!form.cpf_cnpj?'requiredInput':''} value={form.cpf_cnpj} onChange={e=>setForm({...form,cpf_cnpj:e.target.value})}/></Field><Field label="Razão Social / Nome *"><input className={!form.name?'requiredInput':''} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field><Field label="Nome Fantasia"><input value={form.trade_name} onChange={e=>setForm({...form,trade_name:e.target.value})}/></Field><Field label="RG / Inscrição Estadual"><input value={form.rg_ie} onChange={e=>setForm({...form,rg_ie:e.target.value})}/></Field><Field label="Celular"><input value={form.mobile} onChange={e=>setForm({...form,mobile:e.target.value})}/></Field><Field label="Telefone"><input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></Field><Field label="CEP"><div className="inputAction"><input value={form.cep} onBlur={buscarCep} onChange={e=>setForm({...form,cep:e.target.value})}/><button className="ghost" onClick={buscarCep}>{cepBusy?'...':'Buscar'}</button></div></Field><Field label="Cidade"><input value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/></Field><Field label="UF"><input maxLength="2" value={form.state} onChange={e=>setForm({...form,state:e.target.value.toUpperCase()})}/></Field><Field label="Número"><input value={form.number} onChange={e=>setForm({...form,number:e.target.value})}/></Field><Field label="Logradouro"><input value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/></Field><Field label="Bairro"><input value={form.neighborhood} onChange={e=>setForm({...form,neighborhood:e.target.value})}/></Field><Field label="Complemento"><input value={form.complement} onChange={e=>setForm({...form,complement:e.target.value})}/></Field><Field label="Código IBGE"><input value={form.ibge} onChange={e=>setForm({...form,ibge:e.target.value})}/></Field><Field label="E-mail"><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></Field></div><label className="inlineCheck"><input type="checkbox" checked={form.active!==false} onChange={e=>setForm({...form,active:e.target.checked})}/><span>Fornecedor ativo</span></label></div><div className="modalFoot"><button className="ghost" onClick={fechar}>Cancelar</button><button className="primary" onClick={save}>{editingId?'Salvar alterações':'Salvar fornecedor'}</button></div></div></div>}
 </>
}

function TaxConfig({data,refresh,notice}){const empty={state:'RJ',tax_profile:'Simples Nacional',operation_nature:'Venda de mercadoria',regime:'Simples Nacional',crt:'1',cfop_default:'5102',ncm_default:'',csosn_default:'102',icms_cst:'',icms_rate:0,pis_cst:'49',pis_rate:0,cofins_cst:'49',cofins_rate:0,ipi_cst:'53',ipi_rate:0,ibs_cbs_notes:'',notes:''},[form,setForm]=useState({...empty,...(data||{})}),[tab,setTab]=useState('initial'),[open,setOpen]=useState(false);useEffect(()=>data&&setForm({...empty,...data}),[data]);async function save(){try{await api.put('/catalog/tax',form);await refresh();setOpen(false);notice('Configuração tributária salva')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar configuração')}}const tabs=[['initial','Configuração Inicial'],['icms','ICMS'],['pis','PIS'],['cofins','COFINS'],['ipi','IPI'],['ibscbs','IBS / CBS']];return <><div className="pageTitle"><div><span>FISCAL</span><h2>Configuração Tributária</h2><p>Padrões fiscais usados nas operações da empresa.</p></div><button className="primary" onClick={()=>setOpen(true)}>＋ Cadastrar nova configuração tributária</button></div><section className="panel taxSummary"><div><small>UF</small><b>{form.state||'—'}</b></div><div><small>Perfil tributário</small><b>{form.tax_profile||form.regime}</b></div><div><small>Natureza da operação</small><b>{form.operation_nature||'—'}</b></div><div><small>CFOP padrão</small><b>{form.cfop_default||'—'}</b></div></section>{open&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&setOpen(false)}><div className="v8Modal xl"><div className="modalHead"><div><small>TRIBUTAÇÃO</small><h2>Cadastrar nova Configuração Tributária</h2><p>Configure cada grupo de impostos usando as abas.</p></div><button className="iconClose" onClick={()=>setOpen(false)}>×</button></div><div className="taxTabs">{tabs.map(([k,l])=><button className={tab===k?'active':''} key={k} onClick={()=>setTab(k)}>{l}</button>)}</div><div className="modalBody">{tab==='initial'&&<div className="formGrid three"><Field label="UF *"><input value={form.state} onChange={e=>setForm({...form,state:e.target.value.toUpperCase()})}/></Field><Field label="Perfil Tributário *"><select value={form.tax_profile} onChange={e=>setForm({...form,tax_profile:e.target.value,regime:e.target.value})}><option>Simples Nacional</option><option>Lucro Presumido</option><option>Lucro Real</option></select></Field><Field label="Natureza da Operação *"><input value={form.operation_nature} onChange={e=>setForm({...form,operation_nature:e.target.value})}/></Field><Field label="CRT"><input value={form.crt} onChange={e=>setForm({...form,crt:e.target.value})}/></Field><Field label="CFOP padrão"><input value={form.cfop_default} onChange={e=>setForm({...form,cfop_default:e.target.value})}/></Field><Field label="NCM padrão"><input inputMode="numeric" autoComplete="off" maxLength="8" value={cleanNcm(form.ncm_default)} onChange={e=>setForm({...form,ncm_default:cleanNcm(e.target.value)})} placeholder="8 números"/></Field><Field label="CSOSN padrão"><input value={form.csosn_default} onChange={e=>setForm({...form,csosn_default:e.target.value})}/></Field></div>}{tab==='icms'&&<div className="formGrid two"><Field label="CST / CSOSN ICMS"><input value={form.icms_cst} onChange={e=>setForm({...form,icms_cst:e.target.value})}/></Field><Field label="Alíquota ICMS (%)"><input type="number" step="0.01" value={form.icms_rate} onChange={e=>setForm({...form,icms_rate:+e.target.value})}/></Field></div>}{tab==='pis'&&<div className="formGrid two"><Field label="CST PIS"><input value={form.pis_cst} onChange={e=>setForm({...form,pis_cst:e.target.value})}/></Field><Field label="Alíquota PIS (%)"><input type="number" step="0.01" value={form.pis_rate} onChange={e=>setForm({...form,pis_rate:+e.target.value})}/></Field></div>}{tab==='cofins'&&<div className="formGrid two"><Field label="CST COFINS"><input value={form.cofins_cst} onChange={e=>setForm({...form,cofins_cst:e.target.value})}/></Field><Field label="Alíquota COFINS (%)"><input type="number" step="0.01" value={form.cofins_rate} onChange={e=>setForm({...form,cofins_rate:+e.target.value})}/></Field></div>}{tab==='ipi'&&<div className="formGrid two"><Field label="CST IPI"><input value={form.ipi_cst} onChange={e=>setForm({...form,ipi_cst:e.target.value})}/></Field><Field label="Alíquota IPI (%)"><input type="number" step="0.01" value={form.ipi_rate} onChange={e=>setForm({...form,ipi_rate:+e.target.value})}/></Field></div>}{tab==='ibscbs'&&<Field label="IBS / CBS" wide><textarea placeholder="Regras e observações para IBS/CBS" value={form.ibs_cbs_notes} onChange={e=>setForm({...form,ibs_cbs_notes:e.target.value})}/></Field>}</div><div className="modalFoot"><button className="ghost" onClick={()=>setOpen(false)}>Cancelar</button><button className="primary" onClick={save}>Salvar configuração</button></div></div></div>}</>}


function LabelsModule({tab,products,company}){
  const [selected,setSelected]=useState([]),[printItems,setPrintItems]=useState([])
  function toggle(id){setSelected(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id])}
  function printSelected(){const items=products.filter(p=>selected.includes(p.id));if(!items.length)return;setPrintItems(items);setTimeout(()=>window.print(),180)}
  return <><section className="panel"><PanelHead eyebrow="ETIQUETAS" title={tab==='label-models'?'Modelo padrão CDM':'Gerar Etiquetas'} text="Selecione as peças e imprima etiquetas com Código QR, código grande e aplicação do veículo."/><div className="labelToolbar"><button className="labelBtn" onClick={printSelected} disabled={!selected.length}>▣ Imprimir selecionadas ({selected.length})</button><button className="ghost" onClick={()=>setSelected(selected.length===products.length?[]:products.map(p=>p.id))}>{selected.length===products.length&&products.length?'Limpar seleção':'Selecionar todas'}</button></div>{tab==='label-models'&&<div className="labelModelInfo"><b>Etiqueta CDM 100 × 50 mm</b><span>Empresa + Código QR + código grande + descrição + veículo/OEM + SKU.</span></div>}<div className="labelGrid">{products.slice(0,36).map(p=><label className={'labelPreview '+(selected.includes(p.id)?'selected':'')} key={p.id}><input type="checkbox" checked={selected.includes(p.id)} onChange={()=>toggle(p.id)}/><QRCodeSVG value={`${location.origin}/?produto=${p.id}&sku=${encodeURIComponent(p.sku||'')}`} size={62}/><div><small>#{p.id} · {p.sku}</small><b>{p.name}</b><strong>{p.brand} {p.model} {p.year||''}</strong></div></label>)}</div></section><LabelPrintOverlay products={printItems} company={company}/></>
}

// CDM PDV V2
function Sales({products,sales,customers=[],refresh,notice}){
 const [cart,setCart]=useState([]),[pid,setPid]=useState(''),[qty,setQty]=useState(1),[method,setMethod]=useState('pix'),[customerId,setCustomerId]=useState(''),[productSearch,setProductSearch]=useState(''),[busy,setBusy]=useState(false)
 const selected=products.find(p=>p.id===+pid)
 const availableProducts=useMemo(()=>{
   const q=productSearch.trim().toLowerCase()
   return products.filter(p=>Number(p.stock||0)>0&&(!q||`${p.sku} ${p.name} ${p.brand||''} ${p.model||''}`.toLowerCase().includes(q))).slice(0,120)
 },[products,productSearch])

 function add(){
   if(!selected)return
   const q=Math.max(1,+qty||1)
   const existing=cart.find(x=>x.product_id===selected.id)
   const finalQty=(existing?.quantity||0)+q
   if(finalQty>Number(selected.stock||0))return notice(`Só existem ${selected.stock} unidade(s) desta peça no estoque`)
   setCart(c=>existing?c.map(x=>x.product_id===selected.id?{...x,quantity:finalQty}:x):[...c,{product_id:selected.id,quantity:q,name:selected.name,sku:selected.sku,price:selected.price,stock:selected.stock}])
   setPid('');setQty(1);setProductSearch('')
 }

 function changeQty(id,value){
   setCart(c=>c.map(x=>x.product_id===id?{...x,quantity:Math.max(1,Math.min(Number(x.stock||1),Number(value||1)))}:x))
 }

 function remove(id){setCart(c=>c.filter(x=>x.product_id!==id))}
 const total=cart.reduce((a,x)=>a+Number(x.price||0)*x.quantity,0)
 const itemCount=cart.reduce((a,x)=>a+Number(x.quantity||0),0)
 const selectedCustomer=customers.find(c=>c.id===+customerId)

 async function sell(){
   if(!cart.length)return notice('Adicione pelo menos uma peça')
   setBusy(true)
   try{
     const r=await api.post('/sales',{customer_id:customerId?+customerId:null,payment_method:method,items:cart.map(({product_id,quantity})=>({product_id,quantity}))})
     setCart([]);setCustomerId('');setMethod('pix')
     await refresh()
     notice(`Venda #${r.data.id} finalizada, estoque baixado e canais sincronizados`)
   }catch(e){
     notice(erroPt(e.response?.data?.detail)||'Erro na venda')
   }finally{
     setBusy(false)
   }
 }

 return <div className="twoCols saleLayout pdvV2">
   <section className="panel">
     <PanelHead eyebrow="PDV" title="Nova Venda" text="Venda rápida com conferência de estoque, cliente, pagamento e baixa automática."/>
     <div className="pdvQuickSummary">
       <span><small>Itens no carrinho</small><b>{itemCount}</b></span>
       <span><small>Produtos diferentes</small><b>{cart.length}</b></span>
       <span><small>Cliente</small><b>{selectedCustomer?.name||'Consumidor final'}</b></span>
       <span><small>Total</small><b>{money(total)}</b></span>
     </div>

     <div className="pdvProductSearch"><Field label="Buscar peça"><input value={productSearch} onChange={e=>setProductSearch(e.target.value)} placeholder="SKU, nome, marca ou modelo..."/></Field></div>
     <div className="saleAddRow">
       <Field label="Produto"><select value={pid} onChange={e=>setPid(e.target.value)}><option value="">Selecione...</option>{availableProducts.map(p=><option key={p.id} value={p.id}>{p.sku} — {p.name} ({p.stock} un.)</option>)}</select></Field>
       <Field label="Quantidade"><input type="number" min="1" max={selected?.stock||999} value={qty} onChange={e=>setQty(e.target.value)}/></Field>
       <button className="ghost saleAddBtn" onClick={add} disabled={!pid}>+ Adicionar</button>
     </div>

     {selected&&<div className="pdvSelectedInfo"><span>Estoque disponível: <b>{selected.stock}</b></span><span>Preço unitário: <b>{money(selected.price)}</b></span><span>SKU: <b>{selected.sku}</b></span></div>}

     <div className="saleCart">{cart.length?cart.map(x=><div className="saleCartRow pdvCartRow" key={x.product_id}>
       <div><b>{x.name}</b><small>{x.sku} · estoque {x.stock}</small></div>
       <div className="pdvQty"><small>Qtd.</small><input type="number" min="1" max={x.stock} value={x.quantity} onChange={e=>changeQty(x.product_id,e.target.value)}/></div>
       <span>{money(x.price)} cada</span>
       <strong>{money(x.quantity*x.price)}</strong>
       <button onClick={()=>remove(x.product_id)} title="Remover">×</button>
     </div>):<div className="emptyState compact">Carrinho vazio.</div>}</div>

     <div className="formGrid two pdvCheckout">
       <Field label="Cliente"><select value={customerId} onChange={e=>setCustomerId(e.target.value)}><option value="">Consumidor não identificado</option>{customers.map(c=><option key={c.id} value={c.id}>{c.name}{c.cpf_cnpj?` — ${c.cpf_cnpj}`:''}</option>)}</select></Field>
       <Field label="Pagamento"><select value={method} onChange={e=>setMethod(e.target.value)}><option value="pix">PIX</option><option value="credit">Cartão de crédito</option><option value="debit">Cartão de débito</option><option value="cash">Dinheiro</option></select></Field>
     </div>

     <div className="saleTotal"><div><span>Total da venda</span><small>{itemCount} item(ns) · {cart.length} produto(s)</small></div><strong>{money(total)}</strong></div>
     <div className="pdvActions"><button className="ghost" disabled={!cart.length||busy} onClick={()=>setCart([])}>Limpar carrinho</button><button className="primary bigBtn" disabled={!cart.length||busy} onClick={sell}>{busy?'Finalizando...':'Finalizar venda e baixar estoque →'}</button></div>
   </section>

   <section className="panel">
     <PanelHead eyebrow="HISTÓRICO" title="Últimas vendas" text={`${sales.length} vendas registradas`}/>
     <Table rows={sales.slice(0,10)} cols={['id','source','payment_method','total','status','created_at']} format={{source:v=>valuePt('source',v),payment_method:v=>valuePt('payment_method',v),status:v=>statusPt(v),total:money,created_at:v=>v?new Date(v).toLocaleString('pt-BR'):'—'}}/>
   </section>
 </div>
}

// CDM ORDER CENTER V51
function SalesHistory({sales,refresh}){
 const [query,setQuery]=useState(''),[channel,setChannel]=useState('all'),[statusFilter,setStatusFilter]=useState('all'),[openId,setOpenId]=useState(null),[busy,setBusy]=useState(false)

 const canceledValues=new Set(['cancelled','canceled','cancelada','cancelado','cancelled_by_user'])
 const doneValues=new Set(['paid','completed','finished','shipped','delivered','to_confirm_receive'])
 const statusGroup=s=>{
   const v=String(s||'').toLowerCase()
   if(canceledValues.has(v))return 'canceled'
   if(doneValues.has(v))return 'done'
   return 'open'
 }
 const sourceMeta=s=>({
   mercadolivre:{label:'Mercado Livre',short:'ML'},
   shopee:{label:'Shopee',short:'SH'},
   olx:{label:'OLX',short:'OLX'},
   manual:{label:'Venda local',short:'LOJA'}
 }[s]||{label:valuePt('source',s)||'Outro',short:'•'})

 const normalized=useMemo(()=>[...(sales||[])].sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0)),[sales])
 const filtered=useMemo(()=>{
   const q=query.trim().toLowerCase()
   return normalized.filter(s=>{
     if(channel!=='all'&&String(s.source||'manual')!==channel)return false
     if(statusFilter!=='all'&&statusGroup(s.status)!==statusFilter)return false
     if(!q)return true
     const itemText=(s.items||[]).map(i=>`${i.sku||''} ${i.name||''}`).join(' ')
     return `${s.id} ${s.external_order_id||''} ${s.customer_name||''} ${s.source||''} ${s.payment_method||''} ${itemText}`.toLowerCase().includes(q)
   })
 },[normalized,query,channel,statusFilter])

 const activeSales=normalized.filter(s=>statusGroup(s.status)!=='canceled')
 const revenue=activeSales.reduce((a,s)=>a+Number(s.total||0),0)
 const marketplaceCount=normalized.filter(s=>['mercadolivre','shopee','olx'].includes(s.source)).length
 const openCount=normalized.filter(s=>statusGroup(s.status)==='open').length
 const todayKey=new Date().toLocaleDateString('pt-BR')
 const todayCount=normalized.filter(s=>s.created_at&&new Date(s.created_at).toLocaleDateString('pt-BR')===todayKey).length

 async function reload(){
   if(!refresh||busy)return
   setBusy(true)
   try{await refresh()}finally{setBusy(false)}
 }

 return <div className="orderCenter">
   <div className="pageTitle orderCenterTitle">
     <div><span>CENTRAL DE PEDIDOS</span><h2>Pedidos e vendas em um só lugar</h2><p>Acompanhe vendas locais, Mercado Livre, Shopee e outros canais sem misturar os estoques.</p></div>
     <button className="ghost orderRefresh" onClick={reload} disabled={busy}>{busy?'Atualizando...':'↻ Atualizar pedidos'}</button>
   </div>

   <div className="orderMetrics">
     <div><small>Pedidos registrados</small><strong>{normalized.length}</strong><span>{todayCount} hoje</span></div>
     <div><small>Faturamento registrado</small><strong>{money(revenue)}</strong><span>desconsiderando cancelados</span></div>
     <div><small>Marketplaces</small><strong>{marketplaceCount}</strong><span>pedidos externos</span></div>
     <div className={openCount?'attention':''}><small>Em andamento</small><strong>{openCount}</strong><span>pedidos para acompanhar</span></div>
   </div>

   <section className="panel orderCenterPanel">
     <div className="orderToolbar">
       <div className="orderSearch"><span>⌕</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar pedido, SKU, peça ou cliente..."/></div>
       <select value={channel} onChange={e=>setChannel(e.target.value)}>
         <option value="all">Todos os canais</option>
         <option value="manual">Venda local</option>
         <option value="mercadolivre">Mercado Livre</option>
         <option value="shopee">Shopee</option>
         <option value="olx">OLX</option>
       </select>
       <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
         <option value="all">Todos os status</option>
         <option value="open">Em andamento</option>
         <option value="done">Concluídos / pagos</option>
         <option value="canceled">Cancelados</option>
       </select>
     </div>

     <div className="orderResultBar">
       <span><b>{filtered.length}</b> pedido(s) exibido(s)</span>
       {(query||channel!=='all'||statusFilter!=='all')&&<button onClick={()=>{setQuery('');setChannel('all');setStatusFilter('all')}}>Limpar filtros</button>}
     </div>

     <div className="orderList">
       {filtered.length?filtered.map(s=>{
         const src=sourceMeta(s.source||'manual')
         const items=s.items||[]
         const opened=openId===s.id
         const group=statusGroup(s.status)
         return <article className={'orderCard '+group} key={s.id}>
           <button className="orderCardMain" onClick={()=>setOpenId(opened?null:s.id)}>
             <div className={'orderSource '+(s.source||'manual')}><b>{src.short}</b><small>{src.label}</small></div>
             <div className="orderIdentity">
               <small>{s.external_order_id?`PEDIDO ${s.external_order_id}`:`VENDA #${s.id}`}</small>
               <b>{items.length?items.map(i=>i.name||'Peça').slice(0,2).join(' + '):'Venda registrada'}</b>
               <span>{s.customer_name||'Consumidor final'} · {items.reduce((a,i)=>a+Number(i.quantity||0),0)} item(ns)</span>
             </div>
             <div className="orderDate"><small>Data</small><b>{s.created_at?new Date(s.created_at).toLocaleDateString('pt-BR'):'—'}</b><span>{s.created_at?new Date(s.created_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}):''}</span></div>
             <div className="orderPayment"><small>Pagamento</small><b>{valuePt('payment_method',s.payment_method)||'—'}</b></div>
             <div className="orderAmount"><small>Total</small><strong>{money(s.total)}</strong></div>
             <div className={'orderStatus '+group}><i/><span>{statusPt(s.status)}</span></div>
             <span className={'orderChevron '+(opened?'open':'')}>⌄</span>
           </button>

           {opened&&<div className="orderDetails">
             <div className="orderDetailSummary">
               <span><small>Canal</small><b>{src.label}</b></span>
               <span><small>ID interno</small><b>#{s.id}</b></span>
               <span><small>Pedido externo</small><b>{s.external_order_id||'—'}</b></span>
               <span><small>Cliente</small><b>{s.customer_name||'Consumidor final'}</b></span>
             </div>

             <div className="orderItems">
               <div className="orderItemsHead"><span>Peça</span><span>Qtd.</span><span>Unitário</span><span>Subtotal</span></div>
               {items.length?items.map((item,idx)=><div className="orderItemRow" key={`${s.id}-${item.id||item.product_id||idx}`}>
                 <div><b>{item.name||'Peça'}</b><small>{item.sku?`SKU ${item.sku}`:`Produto #${item.product_id||'—'}`}</small></div>
                 <span>{item.quantity||0}</span>
                 <span>{money(item.unit_price)}</span>
                 <strong>{money(Number(item.unit_price||0)*Number(item.quantity||0))}</strong>
               </div>):<div className="orderNoItems">Os itens detalhados deste pedido não estão disponíveis.</div>}
             </div>

             <div className="orderDetailFoot">
               <span>Origem: <b>{src.label}</b></span>
               <span>Status: <b>{statusPt(s.status)}</b></span>
               <strong>Total {money(s.total)}</strong>
             </div>
           </div>}
         </article>
       }):<div className="emptyState orderEmpty">Nenhum pedido encontrado com esses filtros.</div>}
     </div>
   </section>
 </div>
}

// CDM SHIPPING V52
function ShippingPanel({sales,refresh,notice}){
 const [filter,setFilter]=useState('active'),[query,setQuery]=useState(''),[busy,setBusy]=useState(''),[drafts,setDrafts]=useState({})
 const canceled=new Set(['cancelled','canceled','cancelada','cancelado','cancelled_by_user'])
 const steps=[['awaiting_separation','Aguardando separação'],['separated','Separado'],['ready_to_ship','Pronto para envio'],['shipped','Despachado']]
 const labels=Object.fromEntries(steps)
 const order=Object.fromEntries(steps.map((x,i)=>[x[0],i]))
 const src=s=>({manual:['LOJA','Venda local'],mercadolivre:['ML','Mercado Livre'],shopee:['SH','Shopee'],olx:['OLX','OLX']}[s]||['•',valuePt('source',s)||'Outro'])

 const eligible=useMemo(()=>[...(sales||[])].filter(s=>!canceled.has(String(s.status||'').toLowerCase())).sort((a,b)=>{
   const sa=order[s.shipping_status||'awaiting_separation']??0
   const sb=order[b.shipping_status||'awaiting_separation']??0
   return sa-sb||new Date(b.created_at||0)-new Date(a.created_at||0)
 }),[sales])

 const shown=useMemo(()=>{
   const q=query.trim().toLowerCase()
   return eligible.filter(s=>{
     const st=s.shipping_status||'awaiting_separation'
     if(filter==='active'&&st==='shipped')return false
     if(filter!=='all'&&filter!=='active'&&st!==filter)return false
     if(!q)return true
     const items=(s.items||[]).map(i=>`${i.sku||''} ${i.name||''}`).join(' ')
     return `${s.id} ${s.external_order_id||''} ${s.customer_name||''} ${s.carrier_name||''} ${s.tracking_code||''} ${items}`.toLowerCase().includes(q)
   })
 },[eligible,filter,query])

 const count=st=>eligible.filter(s=>(s.shipping_status||'awaiting_separation')===st).length
 const activeCount=eligible.filter(s=>(s.shipping_status||'awaiting_separation')!=='shipped').length

 function draftFor(s){return drafts[s.id]||{carrier_name:s.carrier_name||'',tracking_code:s.tracking_code||'',shipping_notes:s.shipping_notes||''}}
 function setDraft(id,key,value){
   const s=(sales||[]).find(x=>x.id===id)||{}
   setDrafts(d=>({...d,[id]:{...draftFor(s),...(d[id]||{}),[key]:value}}))
 }

 async function move(s,next){
   const d=draftFor(s)
   setBusy(`${s.id}:${next}`)
   try{
     await api.patch(`/sales/${s.id}/shipping`,{shipping_status:next,carrier_name:d.carrier_name||'',tracking_code:d.tracking_code||'',shipping_notes:d.shipping_notes||''})
     await refresh()
     notice(`Pedido ${s.external_order_id||'#'+s.id}: ${labels[next]}`)
   }catch(e){
     notice(erroPt(e.response?.data?.detail)||'Não foi possível atualizar a expedição')
   }finally{setBusy('')}
 }

 return <div className="shippingV52">
   <div className="pageTitle shippingTitle">
     <div><span>EXPEDIÇÃO</span><h2>Painel de Expedição</h2><p>Separe, confira e acompanhe os pedidos até o despacho sem alterar novamente o estoque.</p></div>
     <button className="ghost shippingRefresh" onClick={refresh}>↻ Atualizar pedidos</button>
   </div>

   <div className="shippingMetrics">
     <button className={filter==='active'?'active':''} onClick={()=>setFilter('active')}><small>Fila ativa</small><strong>{activeCount}</strong><span>pedidos pendentes</span></button>
     <button className={filter==='awaiting_separation'?'active':''} onClick={()=>setFilter('awaiting_separation')}><small>Aguardando separação</small><strong>{count('awaiting_separation')}</strong><span>para localizar no estoque</span></button>
     <button className={filter==='ready_to_ship'?'active':''} onClick={()=>setFilter('ready_to_ship')}><small>Prontos para envio</small><strong>{count('ready_to_ship')}</strong><span>aguardando despacho</span></button>
     <button className={filter==='shipped'?'active':''} onClick={()=>setFilter('shipped')}><small>Despachados</small><strong>{count('shipped')}</strong><span>pedidos concluídos</span></button>
   </div>

   <section className="panel shippingPanel">
     <div className="shippingToolbar">
       <div className="shippingSearch"><span>⌕</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar pedido, SKU, peça, cliente ou rastreio..."/></div>
       <select value={filter} onChange={e=>setFilter(e.target.value)}>
         <option value="active">Fila ativa</option><option value="all">Todos</option>
         {steps.map(([k,l])=><option key={k} value={k}>{l}</option>)}
       </select>
     </div>

     <div className="shippingResult"><b>{shown.length}</b> pedido(s) nesta visão</div>

     <div className="shippingList">
       {shown.length?shown.map(s=>{
         const st=s.shipping_status||'awaiting_separation',idx=order[st]??0,channel=src(s.source||'manual'),items=s.items||[],d=draftFor(s),isBusy=busy.startsWith(`${s.id}:`)
         return <article className={'shippingCard '+st} key={s.id}>
           <div className="shippingCardHead">
             <div className={'shippingSource '+(s.source||'manual')}><b>{channel[0]}</b><small>{channel[1]}</small></div>
             <div className="shippingIdentity"><small>{s.external_order_id?`PEDIDO ${s.external_order_id}`:`VENDA #${s.id}`}</small><b>{items.length?items.map(i=>i.name||'Peça').slice(0,2).join(' + '):'Venda registrada'}</b><span>{s.customer_name||'Consumidor final'} · {items.reduce((a,i)=>a+Number(i.quantity||0),0)} item(ns) · {money(s.total)}</span></div>
             <div className={'shippingStatus '+st}><i/><b>{labels[st]||st}</b></div>
           </div>

           <div className="shippingProgress">
             {steps.map(([k,l],i)=><div key={k} className={(i<idx?'done ':i===idx?'current ':'')+(k==='shipped'&&st==='shipped'?'done current':'')}><i>{i<idx||st==='shipped'?'✓':i+1}</i><span>{l}</span></div>)}
           </div>

           <div className="shippingItems">{items.map((it,i)=><div key={it.id||i}><span><b>{it.name||'Peça'}</b><small>{it.sku?`SKU ${it.sku}`:`Produto #${it.product_id||'—'}`}</small></span><strong>{it.quantity||0} un.</strong></div>)}</div>

           <div className="shippingFields">
             <label><span>Transportadora</span><input value={d.carrier_name} onChange={e=>setDraft(s.id,'carrier_name',e.target.value)} placeholder="Ex.: Correios, Jadlog..."/></label>
             <label><span>Código de rastreio</span><input value={d.tracking_code} onChange={e=>setDraft(s.id,'tracking_code',e.target.value)} placeholder="Opcional"/></label>
             <label className="shippingNotes"><span>Observações</span><input value={d.shipping_notes} onChange={e=>setDraft(s.id,'shipping_notes',e.target.value)} placeholder="Embalagem, retirada, conferência..."/></label>
           </div>

           <div className="shippingActions">
             <div><small>Criado em {s.created_at?new Date(s.created_at).toLocaleString('pt-BR'):'—'}</small>{s.shipped_at&&<small>Despachado em {new Date(s.shipped_at).toLocaleString('pt-BR')}</small>}</div>
             <div>
               {idx>0&&<button className="ghost" disabled={isBusy} onClick={()=>move(s,steps[idx-1][0])}>← Voltar etapa</button>}
               {st==='awaiting_separation'&&<button className="primary" disabled={isBusy} onClick={()=>move(s,'separated')}>✓ Marcar como separado</button>}
               {st==='separated'&&<button className="primary" disabled={isBusy} onClick={()=>move(s,'ready_to_ship')}>Pronto para envio →</button>}
               {st==='ready_to_ship'&&<button className="primary" disabled={isBusy} onClick={()=>move(s,'shipped')}>Despachar pedido →</button>}
               {st==='shipped'&&<span className="shippingDone">✓ Expedição concluída</span>}
             </div>
           </div>
         </article>
       }):<div className="emptyState shippingEmpty">Nenhum pedido encontrado nesta etapa.</div>}
     </div>
   </section>
 </div>
}

// CDM INTEGRATION CENTER V1
function Marketplaces({data,listings,products,refresh,notice,focus,subscription}){
 const filtered=focus&&['mercadolivre','shopee','olx'].includes(focus)?data.filter(m=>m.id===focus):data
 const [diagData,setDiagData]=useState(null),[diagBusy,setDiagBusy]=useState('')
 const connectedCount=filtered.filter(m=>m.connected).length,issueCount=filtered.reduce((a,m)=>a+Number(m.issues||0),0)
 const stateOf=m=>m.connected&&m.last_error?{key:'warning',label:'Conectado com alerta',text:'Sua conta está conectada, mas há uma pendência recente.'}:m.connected?{key:'connected',label:'Conectado',text:m.account_name?`Conta ${m.account_name} conectada.`:'Sua conta está conectada e pronta para usar.'}:!m.app_ready?{key:'setup',label:'Em preparação',text:'O CDM está finalizando a liberação deste canal. Você não precisa informar nenhuma chave.'}:m.last_error?{key:'error',label:'Reconectar',text:'A última autorização não foi concluída. Tente conectar novamente.'}:{key:'ready',label:'Conectar conta',text:'Clique em conectar, faça login no marketplace e autorize o CDM.'}
 async function connect(m){try{const r=await api.get(`/marketplaces/${m}/authorize`);location.href=r.data.url}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível iniciar a conexão')}}
 async function remove(m){if(!confirm(`Desconectar ${marketName(m)} desta empresa?`))return;try{await api.delete(`/marketplaces/${m}/connection`);setDiagData(null);await refresh();notice(`${marketName(m)} desconectado`)}catch(e){notice('Erro ao desconectar')}}
 async function pub(id){try{await api.post(`/marketplaces/products/${id}/publish-all`);await refresh();notice('Publicação processada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao publicar')}}
 async function diag(m){setDiagBusy(m);try{const r=await api.get(`/marketplaces/${m}/diagnostics`);setDiagData({...r.data,id:m})}catch(e){notice('Não foi possível verificar a conta agora')}finally{setDiagBusy('')}}
 async function reloadStatus(){try{await refresh();notice('Contas atualizadas')}catch(e){notice('Não foi possível atualizar agora')}}
 return <>
  <div className="pageTitle marketplaceTitle integrationCenterTitle"><div><span>CONTAS CONECTADAS</span><h2>{focus&&['mercadolivre','shopee','olx'].includes(focus)?marketName(focus):'Marketplaces'}</h2><p>Conecte sua conta com login e autorização. O cliente nunca precisa copiar token, chave ou segredo.</p></div><button className="ghost integrationRefresh" onClick={reloadStatus}>↻ Atualizar</button></div>
  <div className="integrationCompactSummary"><span><b>{connectedCount}</b> conectado(s)</span><i/> <span>{filtered.length-connectedCount} para conectar</span>{issueCount>0&&<><i/><span className="hasIssue"><b>{issueCount}</b> pendência(s)</span></>}</div>
  <div className="marketGrid integrationSimpleGrid">{filtered.map(m=>{const state=stateOf(m);return <article className={'marketCard integrationSimpleCard '+state.key} key={m.id}>
   <div className="integrationSimpleTop"><MarketLogo id={m.id} large/><span className={'channelState '+state.key}><i/>{state.label}</span></div>
   <h3>{marketName(m.id)}</h3><p>{state.text}</p>
   {m.connected&&<div className="integrationAccount"><b>{m.account_name||'Conta autorizada'}</b><span>{m.published||0} anúncios publicados{Number(m.issues||0)>0?` · ${m.issues} pendência(s)`:''}</span></div>}
   <div className="integrationPrimaryAction">{m.connected?<button className="primary" onClick={()=>diag(m.id)}>{diagBusy===m.id?'Verificando...':'Gerenciar conta'}</button>:m.app_ready?<button className="primary" onClick={()=>connect(m.id)}>Conectar {marketName(m.id)} →</button>:<button className="ghost" disabled>Disponível em breve</button>}</div>
  </article>})}</div>
  <section className="panel integrationHelpSimple"><b>Como funciona?</b><span>Você clica em conectar, entra na própria conta do marketplace e autoriza. O CDM recebe a autorização e volta conectado automaticamente.</span></section>
  <section className="panel"><PanelHead eyebrow="ANÚNCIOS" title="Publicações" text="Veja somente o que precisa de atenção."/><div className="tableWrap"><table><thead><tr><th>Produto</th><th>Mercado Livre</th><th>Shopee</th><th>OLX</th><th>Ação</th></tr></thead><tbody>{products.map(p=><tr key={p.id}><td><b>{p.name}</b><small className="block">{p.sku}</small></td>{['mercadolivre','shopee','olx'].map(m=>{const r=listings.find(x=>x.product_id===p.id&&x.marketplace===m);return <td key={m}><Status r={r}/></td>})}<td><button className="ghost" onClick={()=>pub(p.id)}>Publicar</button></td></tr>)}</tbody></table></div></section>
  {diagData&&<div className="modalBackdrop" onMouseDown={e=>e.target===e.currentTarget&&setDiagData(null)}><div className="v8Modal medium integrationDiagModal"><div className="modalHead"><div><small>CONTA CONECTADA</small><h2>{marketName(diagData.id)}</h2><p>Somente informações úteis para manter a integração funcionando.</p></div><button className="iconClose" onClick={()=>setDiagData(null)}>×</button></div><div className="modalBody"><div className="diagStatusGrid"><div className={diagData.connected?'ok':'warn'}><small>Conta</small><strong>{diagData.connected?'Conectada':'Desconectada'}</strong></div><div><small>Situação</small><strong>{statusPt(diagData.status)}</strong></div></div>{diagData.last_error?<div className="marketError integrationError"><b>O que precisa de atenção</b><span>{erroPt(diagData.last_error)}</span></div>:<div className="diagOk">✓ Tudo certo com esta conexão.</div>}{diagData.connected&&<button className="ghost dangerOutline full" onClick={()=>remove(diagData.id)}>Desconectar esta conta</button>}</div></div></div>}
 </>
}
function Status({r}){if(!r)return <span className="pill neutral">Não enviado</span>;if(r.status==='published')return <span className="pill success">Publicado</span>;if(['processing','queued','pending'].includes(r.status))return <span className="pill neutral">Processando</span>;return <span className="pill warn" title={erroPt(r.error_message)}>{r.status==='needs_connection'?'Conectar conta':r.status==='needs_product_data'?'Completar produto':'Pendência'}</span>}
function MarketLogo({id,large}) {return <div className={'marketLogo '+id+(large?' large':'')}>{id==='mercadolivre'?'ML':id==='shopee'?'SH':'OLX'}</div>}

function FiscalModule({tab,notice}){
 const fiscalEmpty={series:'1',number:'',operation_type:'saida',purpose:'normal',operation_nature:'Venda de mercadoria',referenced_key:'',order_number:'',intermediary_indicator:'sem_intermediador',recipient:'',recipient_ie:'',sections:{recipient:{name:'',cpf_cnpj:'',cep:'',state:'RJ',city:'',address:'',number:'',neighborhood:''},items:{description:'',sku:'',quantity:1,unit:'UN',unit_value:0,ncm:'',cfop:'5102'},transport:{freight_mode:'sem_frete',carrier:'',plate:'',state:'RJ',volumes:0,gross_weight:0,net_weight:0},financial:{payment_method:'pix',amount:0,installments:1,due_date:''},taxation:{regime:'Simples Nacional',cfop:'5102',ncm:'',csosn:'102',icms_rate:0,pis_rate:0,cofins_rate:0,ipi_rate:0}}}
 const companyEmpty={trade_name:'',legal_name:'',cnpj:'',state_registration:'',tax_regime:'Simples Nacional',email:'',phone:'',responsible_name:'',rg:'',cpf:'',issuing_agency:'',cep:'',state:'RJ',city:'',address:'',number:'',complement:'',logo_url:''}
 const taxEmpty={state:'RJ',tax_profile:'Simples Nacional',operation_nature:'Venda de mercadoria',regime:'Simples Nacional',crt:'1',cfop_default:'5102',ncm_default:'',csosn_default:'102',icms_cst:'',icms_rate:0,pis_cst:'49',pis_rate:0,cofins_cst:'49',cofins_rate:0,ipi_cst:'53',ipi_rate:0,ibs_cbs_notes:'',notes:''}
 const pickCompany=(x={})=>Object.fromEntries(Object.keys(companyEmpty).map(k=>[k,x?.[k]??companyEmpty[k]]))
 const pickTax=(x={})=>{const out=Object.fromEntries(Object.keys(taxEmpty).map(k=>[k,x?.[k]??taxEmpty[k]]));out.ncm_default=cleanNcm(out.ncm_default);return out}
 const [form,setForm]=useState(fiscalEmpty),[section,setSection]=useState('identification'),[docs,setDocs]=useState([]),[docId,setDocId]=useState(null),[busy,setBusy]=useState(false),[setup,setSetup]=useState(null),[cert,setCert]=useState(null),[certPass,setCertPass]=useState(''),[setupBusy,setSetupBusy]=useState(false),[cancelId,setCancelId]=useState(null),[cancelReason,setCancelReason]=useState('')
 const [companyForm,setCompanyForm]=useState(companyEmpty),[taxForm,setTaxForm]=useState(taxEmpty),[lookupBusy,setLookupBusy]=useState(false),[showSetup,setShowSetup]=useState(false)
 const setSec=(key,field,value)=>setForm(f=>({...f,sections:{...f.sections,[key]:{...(f.sections?.[key]||{}),[field]:value}}}))
 async function load(){try{const [d,c,co,tx]=await Promise.all([api.get('/fiscal'),api.get('/fiscal/setup'),api.get('/company/me'),api.get('/catalog/tax')]);setDocs(d.data||[]);setSetup(c.data);setCompanyForm(pickCompany(co.data?.company||{}));setTaxForm(pickTax(tx.data||{}));if(!c.data?.ready)setShowSetup(true)}catch(e){}}
 useEffect(()=>{load()},[tab])
 async function lookupCompany(){const c=String(companyForm.cnpj||'').replace(/\D/g,'');if(c.length!==14)return notice('Digite um CNPJ válido com 14 números');setLookupBusy(true);try{const r=await api.get(`/fiscal/cnpj/${c}`);const found=r.data||{};setCompanyForm(v=>({...v,...Object.fromEntries(Object.entries(found).filter(([,value])=>value!==''&&value!=null))}));if(found.tax_regime)setTaxForm(v=>({...v,tax_profile:found.tax_regime,regime:found.tax_regime}));notice('Dados encontrados. Confira e salve.')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível consultar o CNPJ')}finally{setLookupBusy(false)}}
 async function saveCompany(){setSetupBusy(true);try{await api.put('/company/me',pickCompany(companyForm));await load();notice('Dados da empresa salvos')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível salvar os dados da empresa')}finally{setSetupBusy(false)}}
 async function saveTax(){setSetupBusy(true);try{await api.put('/catalog/tax',pickTax(taxForm));await load();notice('Tributação salva')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível salvar a tributação')}finally{setSetupBusy(false)}}
 async function saveSetup(patch={}){setSetupBusy(true);try{const body={environment:setup?.environment||'homologacao',auto_issue_sales:!!setup?.auto_issue_sales,...patch};const r=await api.put('/fiscal/setup',body);setSetup(r.data);notice('Configuração fiscal salva')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar configuração fiscal')}finally{setSetupBusy(false)}}
 async function sendCert(){if(!cert)return notice('Selecione seu certificado A1 (.pfx ou .p12)');if(!certPass)return notice('Digite a senha do certificado A1');setSetupBusy(true);try{const fd=new FormData();fd.append('certificate',cert);fd.append('password',certPass);const r=await api.post('/fiscal/setup/certificate',fd,{headers:{'Content-Type':'multipart/form-data'}});setSetup(r.data);setCert(null);setCertPass('');notice('Certificado A1 validado e conectado ao emissor fiscal')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível configurar o certificado')}finally{setSetupBusy(false)}}
 async function testSetup(){setSetupBusy(true);try{const r=await api.post('/fiscal/setup/test');setSetup(r.data.setup);notice(r.data.message)}catch(e){notice(erroPt(e.response?.data?.detail)||'Falha ao validar configuração fiscal')}finally{setSetupBusy(false)}}
 async function saveDraft(){setBusy(true);try{const r=docId?await api.put(`/fiscal/${docId}`,form):await api.post('/fiscal',form);setDocId(r.data.id);await load();notice('Rascunho da NF-e salvo');return r.data.id}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro ao salvar rascunho')}finally{setBusy(false)}}
 async function emit(){let id=docId;if(!id)id=await saveDraft();if(!id)return;setBusy(true);try{const r=await api.post(`/fiscal/${id}/emit`);await load();notice(r.data.status==='autorizada'?'NF-e autorizada':'NF-e enviada; o CDM vai acompanhar o processamento')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível emitir a NF-e')}finally{setBusy(false)}}
 async function refreshDoc(id){try{await api.post(`/fiscal/${id}/refresh`);await load();notice('Situação da NF-e atualizada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível consultar a NF-e')}}
 async function cancelDoc(){if(!cancelId)return;try{await api.post(`/fiscal/${cancelId}/cancel`,{justification:cancelReason});setCancelId(null);setCancelReason('');await load();notice('NF-e cancelada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível cancelar a NF-e')}}
 function newDraft(){setForm(fiscalEmpty);setDocId(null);setSection('identification')}
 if(!setup)return <section className="panel"><p>Carregando configuração fiscal...</p></section>
 if(tab==='invoice-history')return <><section className="panel"><PanelHead eyebrow="FISCAL" title="Notas emitidas e rascunhos" text="Consulte a SEFAZ/provedor, abra XML/DANFE e acompanhe cada documento."/><div className="tableWrap"><table><thead><tr><th>NF-e</th><th>Destinatário</th><th>Status</th><th>Chave</th><th>Ações</th></tr></thead><tbody>{docs.map(d=><tr key={d.id}><td><b>{d.number||`#${d.id}`}</b><small className="block">Série {d.series}</small></td><td>{d.recipient||'—'}</td><td><span className={'pill '+(d.status==='autorizada'?'success':d.status==='rejeitada'?'warn':'neutral')}>{statusPt(d.status)}</span></td><td><small>{d.access_key||'—'}</small></td><td><div className="rowActions"><button className="ghost" onClick={()=>refreshDoc(d.id)}>Consultar</button>{d.xml_url&&<button className="ghost" onClick={()=>window.open(d.xml_url,'_blank')}>XML</button>}{d.danfe_url&&<button className="ghost" onClick={()=>window.open(d.danfe_url,'_blank')}>DANFE</button>}{d.status==='autorizada'&&<button className="ghost dangerOutline" onClick={()=>setCancelId(d.id)}>Cancelar</button>}</div></td></tr>)}</tbody></table></div></section>{cancelId&&<div className="modalBackdrop"><div className="v8Modal medium"><div className="modalHead"><div><small>CANCELAMENTO</small><h2>Cancelar NF-e</h2><p>A justificativa deve ter entre 15 e 255 caracteres.</p></div><button className="iconClose" onClick={()=>setCancelId(null)}>×</button></div><div className="modalBody"><Field label="Justificativa"><textarea value={cancelReason} onChange={e=>setCancelReason(e.target.value)} placeholder="Ex.: NF-e emitida com dados incorretos..."/></Field></div><div className="modalFoot"><button className="ghost" onClick={()=>setCancelId(null)}>Voltar</button><button className="primary" onClick={cancelDoc}>Confirmar cancelamento</button></div></div></div>}</>
 if(tab==='xml')return <SimpleModule eyebrow="FISCAL" title="Enviar XML" text="Importação de XML fica separada da emissão para evitar misturar operações." actions={['Consultar documentos','Configuração fiscal']}/>
 if(tab==='invalidate-number')return <SimpleModule eyebrow="FISCAL" title="Inutilizar número" text="Operação fiscal avançada. Use apenas quando houver quebra de sequência de numeração." actions={['Consultar histórico','Configuração fiscal']}/>
 const fiscalChecks=setup.checks||[
   {id:'company',label:'Empresa',done:setup.company_ready},
   {id:'tax',label:'Tributação',done:setup.tax_ready},
   {id:'certificate',label:'Certificado',done:setup.certificate_uploaded},
   {id:'connection',label:'Conexão fiscal',done:setup.connection_ready}
 ]
 const fiscalDone=fiscalChecks.filter(x=>x.done).length
 const fiscalPct=setup.percent??Math.round(fiscalDone/fiscalChecks.length*100)
 if(showSetup||!setup.ready)return <section className="panel fiscalSetupV143">
     <div className="fiscalSetupTop"><div><span>CONFIGURAÇÃO FISCAL</span><h2>NF-e simples, passo a passo</h2><p>Faça esta configuração uma vez. Depois o CDM cuida da emissão e do acompanhamento.</p></div><div className="fiscalTitleActions"><span className={'fiscalEnv '+(setup.environment==='producao'?'production':'')}>{setup.environment==='producao'?'PRODUÇÃO':'HOMOLOGAÇÃO'}</span>{setup.ready&&<button className="ghost" onClick={()=>setShowSetup(false)}>Ir para emissão</button>}</div></div>
     <div className="fiscalSetupProgress"><div><b>{setup.ready?'Configuração concluída':`${fiscalDone} de ${fiscalChecks.length} etapas concluídas`}</b><span>{setup.ready?'Sua empresa está pronta para emitir NF-e.':'O CDM mostra somente o que ainda falta.'}</span></div><strong>{fiscalPct}%</strong></div>
     <div className="fiscalProgressBar"><i style={{width:`${fiscalPct}%`}}/></div>
     {!setup.service_available&&<div className="fiscalServiceNotice"><b>Emissor fiscal em preparação</b><span>Você pode preencher os dados normalmente. A validação do certificado será liberada automaticamente quando o serviço fiscal da plataforma estiver ativado.</span></div>}
     <div className="fiscalQuickChecks">{fiscalChecks.map(x=><span className={x.done?'done':''} key={x.id}><i>{x.done?'✓':'•'}</i>{x.label}</span>)}</div>

     <article className={'fiscalSetupCard '+(setup.company_ready?'done':'')}>
       <div className="fiscalSetupCardHead"><b>{setup.company_ready?'✓':'1'}</b><div><h3>Empresa</h3><p>Digite o CNPJ. O CDM busca os dados públicos e você só confirma o que faltar.</p></div><span>{setup.company_ready?'Concluído':'Obrigatório'}</span></div>
       <div className="fiscalCnpjRow"><Field label="CNPJ"><input value={companyForm.cnpj||''} onChange={e=>setCompanyForm({...companyForm,cnpj:e.target.value})} placeholder="00.000.000/0000-00"/></Field><button className="ghost" disabled={lookupBusy} onClick={lookupCompany}>{lookupBusy?'Buscando...':'Buscar dados'}</button></div>
       <div className="fiscalCompanyGrid"><Field label="Razão social"><input value={companyForm.legal_name||''} onChange={e=>setCompanyForm({...companyForm,legal_name:e.target.value})}/></Field><Field label="Nome fantasia"><input value={companyForm.trade_name||''} onChange={e=>setCompanyForm({...companyForm,trade_name:e.target.value})}/></Field><Field label="Inscrição estadual"><input value={companyForm.state_registration||''} onChange={e=>setCompanyForm({...companyForm,state_registration:e.target.value})}/></Field><Field label="CEP"><input value={companyForm.cep||''} onChange={e=>setCompanyForm({...companyForm,cep:e.target.value})}/></Field><Field label="UF"><input value={companyForm.state||''} maxLength="2" onChange={e=>setCompanyForm({...companyForm,state:e.target.value.toUpperCase()})}/></Field><Field label="Cidade"><input value={companyForm.city||''} onChange={e=>setCompanyForm({...companyForm,city:e.target.value})}/></Field><Field label="Endereço"><input value={companyForm.address||''} onChange={e=>setCompanyForm({...companyForm,address:e.target.value})}/></Field><Field label="Número"><input value={companyForm.number||''} onChange={e=>setCompanyForm({...companyForm,number:e.target.value})}/></Field></div>
       <div className="fiscalCardActions"><button className="primary" disabled={setupBusy} onClick={saveCompany}>{setup.company_ready?'Salvar alterações':'Salvar empresa'}</button></div>
     </article>

     <article className={'fiscalSetupCard '+(setup.tax_ready?'done':'')}>
       <div className="fiscalSetupCardHead"><b>{setup.tax_ready?'✓':'2'}</b><div><h3>Tributação básica</h3><p>Defina os padrões principais. Cada peça pode ter NCM próprio na hora da emissão.</p></div><span>{setup.tax_ready?'Concluído':'Confirmar com contador'}</span></div>
       <div className="fiscalTaxGrid"><Field label="Regime"><select value={taxForm.tax_profile||taxForm.regime} onChange={e=>setTaxForm({...taxForm,tax_profile:e.target.value,regime:e.target.value})}><option>Simples Nacional</option><option>MEI</option><option>Lucro Presumido</option><option>Lucro Real</option></select></Field><Field label="CFOP padrão"><input value={taxForm.cfop_default||''} onChange={e=>setTaxForm({...taxForm,cfop_default:e.target.value})} placeholder="5102"/></Field><Field label="CSOSN / CST padrão"><input value={taxForm.csosn_default||''} onChange={e=>setTaxForm({...taxForm,csosn_default:e.target.value})} placeholder="102"/></Field><Field label="NCM padrão (opcional)"><input inputMode="numeric" autoComplete="off" maxLength="8" value={cleanNcm(taxForm.ncm_default)} onChange={e=>setTaxForm({...taxForm,ncm_default:cleanNcm(e.target.value)})} placeholder="8 números ou deixe vazio"/></Field></div>
       <div className="fiscalCardActions"><small>As regras fiscais variam por operação. Confirme estes padrões com seu contador antes de usar Produção.</small><button className="primary" disabled={setupBusy} onClick={saveTax}>{setup.tax_ready?'Salvar alterações':'Salvar tributação'}</button></div>
     </article>

     <article className={'fiscalSetupCard '+(setup.certificate_uploaded?'done':'')}>
       <div className="fiscalSetupCardHead"><b>{setup.certificate_uploaded?'✓':'3'}</b><div><h3>Certificado digital A1</h3><p>Selecione o arquivo .pfx ou .p12 e informe a senha apenas para validação.</p></div><span>{setup.certificate_uploaded?'Validado':'Pendente'}</span></div>
       {setup.certificate_uploaded&&<div className="certificateOk"><b>✓ Certificado conectado</b><span>{setup.certificate_name||'Certificado A1'}</span></div>}
       <div className="fiscalCertificateSimple"><label className="certificateFile"><span>{cert?.name||'Escolher certificado A1'}</span><input type="file" accept=".pfx,.p12" onChange={e=>setCert(e.target.files?.[0]||null)}/></label><input type="password" value={certPass} onChange={e=>setCertPass(e.target.value)} placeholder="Senha do certificado"/><button className="primary" disabled={setupBusy||!cert||!certPass||!setup.service_available} onClick={sendCert}>{setupBusy?'Validando...':setup.certificate_uploaded?'Substituir e validar':'Validar certificado'}</button></div>
       <small className="fiscalPrivacy">A senha é usada somente durante o envio ao emissor fiscal e não fica armazenada no CDM.</small>
     </article>

     <article className={'fiscalSetupCard '+(setup.last_test_status==='ok'?'done':'')}>
       <div className="fiscalSetupCardHead"><b>{setup.last_test_status==='ok'?'✓':'4'}</b><div><h3>Teste final</h3><p>O CDM confere tudo antes de liberar a emissão.</p></div><span>{setup.last_test_status==='ok'?'Aprovado':'Última etapa'}</span></div>
       <div className="fiscalFinalRow"><Field label="Ambiente"><select value={setup.environment} onChange={e=>{const environment=e.target.value;setSetup(v=>({...v,environment}));saveSetup({environment})}}><option value="homologacao">Homologação — testes sem valor fiscal</option><option value="producao">Produção — notas com valor fiscal</option></select></Field><button className="primary" disabled={setupBusy} onClick={testSetup}>{setupBusy?'Verificando...':'Verificar tudo automaticamente'}</button></div>
       {setup.last_error&&<div className="fiscalSetupError"><b>Ainda falta concluir:</b><span>{setup.last_error.replace(/^Falta:\s*/i,'')}</span></div>}
       {setup.last_test_status==='ok'&&<div className="fiscalReadyMessage"><b>✓ Sua empresa está pronta para emitir NF-e</b><span>O CDM pode enviar a nota e acompanhar o retorno automaticamente.</span>{setup.ready&&<button className="primary" onClick={()=>setShowSetup(false)}>Ir para emissão de NF-e →</button>}</div>}
     </article>
   </section>
 const tabs=[['identification','Identificação'],['recipient','Destinatário'],['items','Itens'],['transport','Transporte'],['financial','Financeiro'],['taxation','Tributação']],items=form.sections?.items||{},recipient=form.sections?.recipient||{},transport=form.sections?.transport||{},financial=form.sections?.financial||{},taxation=form.sections?.taxation||{}
 return <><div className="pageTitle fiscalTitle"><div><span>FISCAL</span><h2>Emitir NF-e</h2><p>Ambiente configurado e pronto. O CDM envia e acompanha o retorno automaticamente.</p></div><div className="fiscalTitleActions"><span className={'fiscalEnv '+(setup.environment==='producao'?'production':'')}>{setup.environment==='producao'?'PRODUÇÃO':'HOMOLOGAÇÃO'}</span><button className="ghost" onClick={()=>setShowSetup(true)}>Configuração fiscal</button></div></div><section className="panel fiscalPanel"><div className="fiscalTabs">{tabs.map(([k,l])=><button className={section===k?'active':''} key={k} onClick={()=>setSection(k)}>{l}</button>)}</div>
 {section==='identification'&&<div className="formGrid three fiscalForm"><Field label="Série"><input value={form.series} onChange={e=>setForm({...form,series:e.target.value})}/></Field><Field label="Número (opcional)"><input value={form.number} onChange={e=>setForm({...form,number:e.target.value})}/></Field><Field label="Tipo"><select value={form.operation_type} onChange={e=>setForm({...form,operation_type:e.target.value})}><option value="saida">Saída</option><option value="entrada">Entrada</option></select></Field><Field label="Finalidade"><select value={form.purpose} onChange={e=>setForm({...form,purpose:e.target.value})}><option value="normal">Normal</option><option value="complementar">Complementar</option><option value="ajuste">Ajuste</option><option value="devolucao">Devolução</option></select></Field><Field label="Natureza da operação"><input value={form.operation_nature} onChange={e=>setForm({...form,operation_nature:e.target.value})}/></Field><Field label="Pedido / referência"><input value={form.order_number} onChange={e=>setForm({...form,order_number:e.target.value})}/></Field></div>}
 {section==='recipient'&&<div className="formGrid three fiscalForm">{[['Nome / Razão Social','name'],['CPF / CNPJ','cpf_cnpj'],['CEP','cep'],['UF','state'],['Cidade','city'],['Endereço','address'],['Número','number'],['Bairro','neighborhood']].map(([l,k])=><Field key={k} label={l}><input value={recipient[k]||''} onChange={e=>setSec('recipient',k,e.target.value)}/></Field>)}<Field label="Inscrição Estadual"><input value={form.recipient_ie} onChange={e=>setForm({...form,recipient_ie:e.target.value})}/></Field></div>}
 {section==='items'&&<div className="fiscalSectionEditor"><div className="formGrid three"><Field label="Descrição da peça"><input value={items.description||''} onChange={e=>setSec('items','description',e.target.value)}/></Field><Field label="SKU"><input value={items.sku||''} onChange={e=>setSec('items','sku',e.target.value)}/></Field><Field label="Quantidade"><input type="number" min="1" value={items.quantity??1} onChange={e=>setSec('items','quantity',+e.target.value)}/></Field><Field label="Unidade"><input value={items.unit||'UN'} onChange={e=>setSec('items','unit',e.target.value.toUpperCase())}/></Field><Field label="Valor unitário"><input type="number" step="0.01" value={items.unit_value??0} onChange={e=>setSec('items','unit_value',+e.target.value)}/></Field><Field label="NCM"><input inputMode="numeric" autoComplete="off" maxLength="8" value={cleanNcm(items.ncm)} onChange={e=>setSec('items','ncm',cleanNcm(e.target.value))}/></Field><Field label="CFOP"><input value={items.cfop||'5102'} onChange={e=>setSec('items','cfop',e.target.value)}/></Field></div><div className="fiscalTotalPreview"><span>Total do item</span><b>{money(Number(items.quantity||0)*Number(items.unit_value||0))}</b></div></div>}
 {section==='transport'&&<div className="formGrid three"><Field label="Frete"><select value={transport.freight_mode||'sem_frete'} onChange={e=>setSec('transport','freight_mode',e.target.value)}><option value="sem_frete">Sem frete</option><option value="emitente">Por conta do emitente</option><option value="destinatario">Por conta do destinatário</option><option value="terceiros">Por conta de terceiros</option></select></Field><Field label="Transportadora"><input value={transport.carrier||''} onChange={e=>setSec('transport','carrier',e.target.value)}/></Field><Field label="Placa"><input value={transport.plate||''} onChange={e=>setSec('transport','plate',e.target.value.toUpperCase())}/></Field></div>}
 {section==='financial'&&<div className="formGrid three"><Field label="Forma de pagamento"><select value={financial.payment_method||'pix'} onChange={e=>setSec('financial','payment_method',e.target.value)}><option value="pix">PIX</option><option value="dinheiro">Dinheiro</option><option value="cartao_credito">Cartão de crédito</option><option value="cartao_debito">Cartão de débito</option><option value="boleto">Boleto</option><option value="transferencia">Transferência</option></select></Field><Field label="Valor"><input type="number" step="0.01" min="0" value={financial.amount??0} onChange={e=>setSec('financial','amount',+e.target.value)}/></Field><Field label="Parcelas"><input type="number" min="1" value={financial.installments??1} onChange={e=>setSec('financial','installments',+e.target.value)}/></Field></div>}
 {section==='taxation'&&<div className="formGrid three"><Field label="Regime tributário"><select value={taxation.regime||'Simples Nacional'} onChange={e=>setSec('taxation','regime',e.target.value)}><option>Simples Nacional</option><option>Lucro Presumido</option><option>Lucro Real</option></select></Field><Field label="CFOP"><input value={taxation.cfop||'5102'} onChange={e=>setSec('taxation','cfop',e.target.value)}/></Field><Field label="NCM"><input inputMode="numeric" autoComplete="off" maxLength="8" value={cleanNcm(taxation.ncm)} onChange={e=>setSec('taxation','ncm',cleanNcm(e.target.value))}/></Field><Field label="CSOSN / CST"><input value={taxation.csosn||'102'} onChange={e=>setSec('taxation','csosn',e.target.value)}/></Field></div>}
 <div className="fiscalActions"><button className="primary" disabled={busy} onClick={emit}>{busy?'Processando...':'Emitir NF-e'}</button><button className="ghost" disabled={busy} onClick={saveDraft}>Salvar rascunho</button><button className="ghost" onClick={newDraft}>Nova nota</button></div><div className="fiscalWarning">{setup.environment==='homologacao'?'Você está em HOMOLOGAÇÃO: as notas são somente testes e não têm valor fiscal.':'Você está em PRODUÇÃO: emissões têm valor fiscal. Confira os dados antes de enviar.'}</div></section></>
}

function PublicCatalog({companyId}){
 const [data,setData]=useState(null),[q,setQ]=useState(''),[busy,setBusy]=useState(false)
 async function search(term=q){setBusy(true);try{setData((await axios.get(`${API}/intelligence/public/catalog/${companyId}`,{params:{q:term}})).data)}catch(e){setData({error:erroPt(e.response?.data?.detail)||'Loja não encontrada',products:[]})}finally{setBusy(false)}}
 useEffect(()=>{search('')},[companyId])
 const phone=String(data?.company?.phone||'').replace(/\D/g,''),phoneIntl=phone.startsWith('55')?phone:(phone?`55${phone}`:'')
 function wa(p){const msg=encodeURIComponent(`Olá! Tenho interesse na peça ${p.name} (${p.sku}) por ${money(p.price)}. Ainda está disponível?`);return phoneIntl?`https://wa.me/${phoneIntl}?text=${msg}`:'#'}
 return <div className="publicStore"><header className="publicStoreHead"><div className="brandMark">CDM</div><div><small>CATÁLOGO DE PEÇAS</small><h1>{data?.company?.name||'CDM Desmontes'}</h1><p>{[data?.company?.city,data?.company?.state].filter(Boolean).join(' / ')}</p></div></header><main><div className="publicSearch"><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()} placeholder="Pesquise peça, modelo, ano, OEM ou compatibilidade"/><button className="primary" onClick={()=>search()}>{busy?'Buscando...':'Pesquisar'}</button></div>{data?.error&&<div className="error">{data.error}</div>}<div className="publicProductGrid">{(data?.products||[]).map(p=><article className="publicProduct" key={p.id}><div className="publicPhoto">{p.has_image?<img src={`${API}/products/public/${p.id}/images/0`} alt={p.name}/>:<span>Sem foto</span>}</div><small>{p.sku}</small><h3>{p.name}</h3><p>{p.brand} {p.model} {p.year||''}</p><div className="publicBadges"><span>Qualidade {p.quality_grade||'B'}</span><span>{p.warranty_days||0} dias de garantia</span></div><strong>{money(p.price)}</strong>{phoneIntl&&<a className="waButton" href={wa(p)} target="_blank" rel="noreferrer">Falar no WhatsApp</a>}</article>)}</div>{data&&!busy&&!data.products?.length&&!data.error&&<div className="emptyState">Nenhuma peça encontrada para esta busca.</div>}</main><footer>Catálogo na internet • CDM Desmontes</footer></div>
}

function PublicWarranty({token}){
 const [d,setD]=useState(null),[err,setErr]=useState('')
 useEffect(()=>{axios.get(`${API}/intelligence/public/warranty/${encodeURIComponent(token)}`).then(r=>setD(r.data)).catch(e=>setErr(erroPt(e.response?.data?.detail)||'Não foi possível consultar a garantia'))},[token])
 return <div className="warrantyPage"><div className="warrantyCard"><div className="brandMark">CDM</div><small>CONSULTA DE GARANTIA</small>{err?<div className="error">{err}</div>:!d?<p>Consultando...</p>:<><h1>{d.active?'Garantia ativa':'Garantia encerrada'}</h1><div className={d.active?'warrantyStatus ok':'warrantyStatus bad'}>{d.active?'✓ Dentro do prazo':'Prazo encerrado'}</div><dl><dt>Empresa</dt><dd>{d.company}</dd><dt>Venda</dt><dd>#{d.sale_id}</dd><dt>Peça</dt><dd>{d.product}</dd><dt>SKU</dt><dd>{d.sku}</dd><dt>Qualidade</dt><dd>{d.quality_grade}</dd><dt>Garantia</dt><dd>{d.warranty_days} dias</dd><dt>Compra</dt><dd>{fmtDate(d.purchased_at)}</dd><dt>Vencimento</dt><dd>{fmtDate(d.expires_at)}</dd></dl></>}</div></div>
}

function IntelligenceHome({setTab}){
 const cards=[
  ['🤖','Assistente CDM','Pergunte sobre vendas, estoque, financeiro e operação.','assistant-cdm'],
  ['👑','Painel do Dono','Resumo rápido da empresa para abrir e entender tudo em segundos.','owner-panel'],
  ['📡','Radar de Oportunidades','Peças que vendem, itens parados e buscas sem resultado.','radar'],
  ['🚗','Desmonte Inteligente','Prioriza quais peças retirar primeiro de cada sucata.','smart-dismantling'],
  ['💰','Preço Inteligente','Sugere preço usando custo, idade no estoque e histórico da empresa.','smart-pricing'],
  ['🛡','Proteção de Venda','Conferência de SKU, evidências de envio e apoio contra devoluções.','sale-protection']
 ]
 return <><div className="pageTitle"><div><span>INOVAÇÃO CDM</span><h2>Inteligência CDM</h2><p>Ferramentas inteligentes ligadas diretamente aos dados da sua empresa.</p></div><span className="statusBadge">● Liberado pela assinatura</span></div><div className="innovationGrid">{cards.map(([i,t,d,k])=><button className="innovationCard" key={k} onClick={()=>setTab(k)}><span className="innovationIcon">{i}</span><div><h3>{t}</h3><p>{d}</p><b>Abrir →</b></div></button>)}</div><section className="panel innovationInfo"><b>Como funciona por empresa</b><p>Cada empresa assinante recebe automaticamente estas ferramentas. Os cálculos e o Assistente CDM usam somente os dados da própria empresa autenticada.</p></section></>
}

function AssistantCDM(){
 const [status,setStatus]=useState(null),[messages,setMessages]=useState([]),[input,setInput]=useState(''),[busy,setBusy]=useState(false)
 async function load(){try{const [s,h]=await Promise.all([api.get('/intelligence/status'),api.get('/intelligence/assistant/history')]);setStatus(s.data);setMessages(h.data||[])}catch(e){}}
 useEffect(()=>{load()},[])
 async function send(text=input){const q=(text||'').trim();if(!q||busy)return;setInput('');setMessages(v=>[...v,{role:'user',content:q}]);setBusy(true);try{const r=await api.post('/intelligence/assistant/chat',{message:q});setMessages(v=>[...v,{role:'assistant',content:r.data.answer}])}catch(e){setMessages(v=>[...v,{role:'assistant',content:erroPt(e.response?.data?.detail)||'Não consegui responder agora.'}])}finally{setBusy(false)}}
 const quick=['Quanto vendi hoje?','Quais peças estão com estoque baixo?','Quais peças estão paradas?','Qual é meu saldo financeiro?','Quais peças mais vendem?']
 return <><div className="pageTitle"><div><span>ASSISTENTE DA EMPRESA</span><h2>Assistente CDM</h2><p>Um assistente para cada empresa, liberado automaticamente pelo plano.</p></div><span className="statusBadge">● {status?.mode==='ia'?'IA conectada':'Inteligência local ativa'}</span></div><section className="assistantShell panel"><div className="assistantQuick">{quick.map(q=><button className="ghost" key={q} onClick={()=>send(q)}>{q}</button>)}</div><div className="assistantMessages">{messages.length?messages.map((m,i)=><div key={m.id||i} className={'assistantMsg '+m.role}><small>{m.role==='assistant'?'Assistente CDM':'Você'}</small><p>{m.content}</p></div>):<div className="assistantWelcome"><span>🤖</span><h3>Olá! Sou o Assistente CDM desta empresa.</h3><p>Posso analisar os dados do estoque, vendas e financeiro sem misturar informações de outras empresas.</p></div>}{busy&&<div className="assistantMsg assistant"><small>Assistente CDM</small><p>Analisando os dados...</p></div>}</div><div className="assistantComposer"><textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="Ex.: quanto vendi nos últimos 30 dias?"/><button className="primary" disabled={busy||!input.trim()} onClick={()=>send()}>Enviar</button></div></section><p className="fieldHelp">Durante os 7 dias de teste o assistente também fica disponível. Se a assinatura vencer, ele é bloqueado junto com os módulos; após o pagamento aprovado, volta automaticamente. {status&&<>Uso do mês: <b>{status.messages_used_month}</b> de <b>{status.messages_limit_month}</b> mensagens.</>}</p></>
}

function OwnerPanel(){
 const [d,setD]=useState(null)
 useEffect(()=>{api.get('/intelligence/owner-dashboard').then(r=>setD(r.data)).catch(()=>{})},[])
 if(!d)return <section className="panel"><p>Carregando painel inteligente...</p></section>
 return <><div className="pageTitle"><div><span>VISÃO DO DONO</span><h2>Painel do Dono</h2><p>Os números principais da operação em uma única tela.</p></div></div><div className="grid metrics"><Card icon="Hoje" title="Vendas hoje" value={money(d.revenue_today)} sub={`${d.sales_today} venda(s)`}/><Card icon="30d" title="Últimos 30 dias" value={money(d.revenue_30d)} sub={`${d.sales_30d} venda(s)`}/><Card icon="▤" title="Unidades em estoque" value={d.stock_qty} sub={`${d.low_stock} com estoque baixo`}/><Card icon="R$" title="Saldo financeiro" value={money(d.balance)} sub="Entradas menos saídas"/></div><div className="twoCols"><section className="panel"><PanelHead eyebrow="DESTAQUES" title="Peças com maior saída" text="Ranking dos últimos 90 dias"/><Table rows={d.top_products||[]} cols={['sku','name','quantity','revenue']} format={{revenue:money}}/></section><section className="panel"><PanelHead eyebrow="SUCATA" title="Maior retorno registrado" text="Receita de peças vinculadas ao veículo"/>{d.best_vehicle?<div className="bestVehicle"><span>🚗</span><h3>{d.best_vehicle.label}</h3><p>{d.best_vehicle.plate||'Sem placa'}</p><strong>{money(d.best_vehicle.revenue)}</strong><small>Retorno registrado: {d.best_vehicle.return_percent}% do valor de aquisição</small></div>:<div className="emptyState">Ainda não há dados suficientes de peças vinculadas a sucatas.</div>}<div className="publicCatalogBox"><b>Catálogo público da empresa</b><span>{location.origin}/?loja={d.company_id}</span><div><button className="ghost" onClick={()=>navigator.clipboard?.writeText(`${location.origin}/?loja=${d.company_id}`)}>Copiar endereço</button><button className="primary" onClick={()=>window.open(`${location.origin}/?loja=${d.company_id}`,'_blank')}>Abrir catálogo</button></div></div></section></div></>
}

function OpportunityRadar(){
 const [d,setD]=useState(null)
 useEffect(()=>{api.get('/intelligence/radar').then(r=>setD(r.data)).catch(()=>{})},[])
 if(!d)return <section className="panel"><p>Carregando radar...</p></section>
 return <><div className="pageTitle"><div><span>RADAR CDM</span><h2>Radar de Oportunidades</h2><p>Ajuda a enxergar o que vende, o que está parado e o que as buscas não encontram.</p></div></div><div className="twoCols"><section className="panel"><PanelHead eyebrow="SAÍDA" title="Mais vendidos" text="Últimos 90 dias"/><Table rows={d.top_sellers||[]} cols={['sku','name','quantity','revenue']} format={{revenue:money}}/></section><section className="panel"><PanelHead eyebrow="DEMANDA PERDIDA" title="Buscas sem resultado" text="Pesquisas feitas no estoque que não encontraram peças"/><Table rows={d.lost_searches||[]} cols={['query','count']}/></section></div><section className="panel"><PanelHead eyebrow="ESTOQUE PARADO" title="Peças há mais de 120 dias" text="Candidatas a revisão de preço ou divulgação"/><Table rows={d.stale_products||[]} cols={['sku','name','stock','price','days']} format={{price:money}}/></section></>
}

function SmartDismantling({vehicles=[],notice}){
 const [id,setId]=useState(''),[d,setD]=useState(null),[busy,setBusy]=useState(false),[err,setErr]=useState('')
 async function analyze(){
   if(!id)return
   setBusy(true);setErr('')
   try{setD((await api.get(`/intelligence/dismantling/${id}`)).data)}
   catch(e){const msg=erroPt(e.response?.data?.detail)||'Não foi possível analisar esta sucata';setErr(msg);notice?.(msg)}
   finally{setBusy(false)}
 }
 function copyPlan(){
   if(!d)return
   const lines=[`PLANO DE DESMONTE - ${d.vehicle.brand||''} ${d.vehicle.model||''} ${d.vehicle.year||''}`.trim(),`Placa: ${d.vehicle.plate||'sem placa'}`,'',...d.suggestions.map((x,i)=>`${i+1}. ${x.piece} - prioridade ${x.priority} - pontuação ${x.score}${x.estimated_price?` - média ${money(x.estimated_price)}`:' - sem histórico local de preço'}`)]
   navigator.clipboard?.writeText(lines.join('\n'));notice?.('Plano de desmonte copiado')
 }
 if(!vehicles.length)return <><div className="pageTitle"><div><span>DESMONTE INTELIGENTE</span><h2>O que desmontar primeiro?</h2><p>Prioridade calculada usando os dados da sua empresa.</p></div></div><section className="panel"><div className="emptyState"><b>Cadastre uma sucata primeiro</b><p>Depois do cadastro, o CDM monta automaticamente uma ordem sugerida para retirada das peças.</p></div></section></>
 return <><div className="pageTitle"><div><span>DESMONTE INTELIGENTE</span><h2>O que desmontar primeiro?</h2><p>O CDM monta uma prioridade usando histórico de vendas e uma base operacional segura.</p></div></div><section className="panel">
   <div className="smartSelector"><Field label="Sucata / veículo"><select value={id} onChange={e=>{setId(e.target.value);setD(null);setErr('')}}><option value="">Selecione...</option>{vehicles.map(v=><option value={v.id} key={v.id}>#{v.id} · {v.plate||'sem placa'} · {v.brand} {v.model} {v.year||''}</option>)}</select></Field><button className="primary" disabled={!id||busy} onClick={analyze}>{busy?'Analisando...':'Analisar sucata'}</button></div>
   {err&&<div className="error">{err}</div>}
   {d&&<><div className="smartVehicleHead"><div><span>🚗</span><div><b>{d.vehicle.brand} {d.vehicle.model} {d.vehicle.year||''}</b><small>{d.vehicle.plate||'Sem placa'} · {d.linked_products} peça(s) já vinculada(s)</small></div></div><strong>{money(d.revenue_from_linked_parts)}</strong></div>
   <div className="intelligenceSummary"><span><small>Prioridade alta</small><b>{d.high_priority_count||0} peças</b></span><span><small>Receita já registrada</small><b>{money(d.revenue_from_linked_parts)}</b></span><span><small>Estimativa baseada no histórico</small><b>{d.estimated_total>0?money(d.estimated_total):'Sem histórico suficiente'}</b></span></div>
   <div className="dismantlingMap">{d.suggestions.map((x,i)=><article key={x.piece} className={'priorityCard '+(x.priority==='Alta'?'high':'')}><div><small>#{i+1}</small><b>{x.piece}</b><span>Prioridade {x.priority}</span></div><strong>{x.score}</strong><small>{x.historical_sales} venda(s) no histórico{x.estimated_price?` · média ${money(x.estimated_price)}`:' · sem preço histórico'}</small></article>)}</div>
   <div className="intelligenceActions"><button className="ghost" onClick={copyPlan}>Copiar plano</button><button className="ghost" onClick={()=>window.print()}>Imprimir plano</button><button className="primary" onClick={analyze}>Atualizar análise</button></div><p className="fieldHelp">{d.note}</p></>}</section></>
}


function SmartPricing({products=[],refresh,notice}){
 const [id,setId]=useState(''),[d,setD]=useState(null),[busy,setBusy]=useState(false),[applying,setApplying]=useState(false),[err,setErr]=useState('')
 async function analyze(){
   if(!id)return
   setBusy(true);setErr('')
   try{setD((await api.get(`/intelligence/pricing/${id}`)).data)}
   catch(e){const msg=erroPt(e.response?.data?.detail)||'Não foi possível calcular o preço';setErr(msg);notice?.(msg)}
   finally{setBusy(false)}
 }
 async function applySuggested(){
   if(!id||!d)return
   if(!confirm(`Aplicar ${money(d.suggested_price)} como novo preço desta peça?`))return
   setApplying(true)
   try{const r=await api.post(`/intelligence/pricing/${id}/apply`);await refresh?.();setD(v=>({...v,current_price:r.data.new_price,suggested_price:r.data.new_price}));notice?.(r.data.message||'Preço inteligente aplicado')}
   catch(e){notice?.(erroPt(e.response?.data?.detail)||'Não foi possível aplicar o preço')}
   finally{setApplying(false)}
 }
 const p=products.find(x=>x.id===+id)
 if(!products.length)return <><div className="pageTitle"><div><span>PREÇO INTELIGENTE</span><h2>Sugestão de preço</h2><p>Use seus próprios dados para orientar o preço de venda.</p></div></div><section className="panel"><div className="emptyState"><b>Cadastre uma peça primeiro</b><p>Com uma peça cadastrada, o CDM calcula preço sugerido, piso e tempo de estoque.</p></div></section></>
 return <><div className="pageTitle"><div><span>PREÇO INTELIGENTE</span><h2>Sugestão de preço</h2><p>O CDM considera custo, tempo de estoque e histórico de vendas da própria empresa.</p></div></div><section className="panel"><div className="smartSelector"><Field label="Peça"><select value={id} onChange={e=>{setId(e.target.value);setD(null);setErr('')}}><option value="">Selecione...</option>{products.map(x=><option key={x.id} value={x.id}>{x.sku} · {x.name}</option>)}</select></Field><button className="primary" disabled={!id||busy} onClick={analyze}>{busy?'Calculando...':'Calcular preço'}</button></div>
 {err&&<div className="error">{err}</div>}
 {d&&<><div className="priceIntelligence"><div><small>Preço atual</small><b>{money(d.current_price)}</b></div><div className="recommended"><small>Preço sugerido</small><b>{money(d.suggested_price)}</b></div><div><small>Piso recomendado</small><b>{money(d.minimum_price)}</b></div><div><small>Dias em estoque</small><b>{d.days_in_stock}</b></div><div><small>Média do histórico</small><b>{d.historical_average>0?money(d.historical_average):'Sem histórico'}</b></div><div><small>Vendas usadas no cálculo</small><b>{d.sales_sample||0}</b></div><p>{d.reason}</p><small>{d.channel_note}</small></div><div className="intelligenceActions"><button className="ghost" onClick={analyze}>Recalcular</button><button className="primary" disabled={applying||Number(d.suggested_price)<=0} onClick={applySuggested}>{applying?'Aplicando...':'Aplicar preço sugerido'}</button></div></>}
 {p&&<div className="qualityMini"><span>Qualidade: <b>{p.quality_grade||'B'}</b></span><span>Garantia: <b>{p.warranty_days??90} dias</b></span><span>Estoque: <b>{p.stock||0} un.</b></span></div>}</section></>
}


function SaleProtection({sales=[],products=[],notice}){
 const [mode,setMode]=useState('check')
 const [saleId,setSaleId]=useState(''),[sku,setSku]=useState(''),[result,setResult]=useState(null),[checks,setChecks]=useState([])
 const [evidence,setEvidence]=useState({sale_id:'',product_id:'',serial_number:'',condition_notes:'',photos:[]})
 const [saved,setSaved]=useState([])
 const [warranty,setWarranty]=useState({sale_id:'',product_id:'',token:'',days:0})
 async function loadProtection(){try{const [ev,ch]=await Promise.all([api.get('/intelligence/evidence'),api.get('/intelligence/shipping-checks')]);setSaved(ev.data||[]);setChecks(ch.data||[])}catch(e){}}
 useEffect(()=>{loadProtection()},[])
 const saleProducts=sid=>{const sale=sales.find(s=>s.id===+sid);return (sale?.items||[]).map(i=>products.find(p=>p.id===i.product_id)).filter(Boolean)}
 const evidenceProducts=saleProducts(evidence.sale_id),warrantyProducts=saleProducts(warranty.sale_id)
 async function check(){try{const r=await api.post('/intelligence/shipping-check',{sale_id:+saleId,sku});setResult(r.data);await loadProtection()}catch(e){setResult({ok:false,result:erroPt(e.response?.data?.detail)||'Não foi possível conferir'})}}
 async function filesToData(files){const arr=[];for(const f of Array.from(files||[]).slice(0,4))arr.push(await readFileAsDataUrl(f));setEvidence(v=>({...v,photos:arr}))}
 async function saveEvidence(){
   if(!evidence.sale_id)return notice('Informe a venda')
   try{await api.post('/intelligence/evidence',{...evidence,sale_id:+evidence.sale_id,product_id:evidence.product_id?+evidence.product_id:null});await loadProtection();notice('Prova de envio salva');setEvidence({sale_id:'',product_id:'',serial_number:'',condition_notes:'',photos:[]})}
   catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível salvar a prova')}
 }
 async function generateWarranty(){
   if(!warranty.sale_id||!warranty.product_id)return notice('Selecione a venda e a peça')
   try{const r=await api.post('/intelligence/warranty-token',{sale_id:+warranty.sale_id,product_id:+warranty.product_id});setWarranty(v=>({...v,token:r.data.token,days:r.data.warranty_days}))}
   catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível gerar a garantia')}
 }
 const warrantyUrl=warranty.token?`${location.origin}/?garantia=${encodeURIComponent(warranty.token)}`:''
 return <><div className="pageTitle"><div><span>SEGURANÇA DA VENDA</span><h2>Proteção contra erro e devolução</h2><p>Confira a peça, registre evidências e gere uma garantia digital vinculada à venda.</p></div></div>
   <div className="taxTabs protectionTabs"><button className={mode==='check'?'active':''} onClick={()=>setMode('check')}>Conferência de expedição</button><button className={mode==='evidence'?'active':''} onClick={()=>setMode('evidence')}>Prova de envio</button><button className={mode==='warranty'?'active':''} onClick={()=>setMode('warranty')}>Garantia por Código QR</button></div>
   {mode==='check'&&<><section className="panel"><div className="formGrid two"><Field label="Número da venda"><select value={saleId} onChange={e=>{setSaleId(e.target.value);setResult(null)}}><option value="">Selecione...</option>{sales.map(s=><option key={s.id} value={s.id}>Venda #{s.id} · {money(s.total)}</option>)}</select></Field><Field label="SKU escaneado / digitado"><input value={sku} onChange={e=>setSku(e.target.value.toUpperCase())} placeholder="Ex.: CDM-001"/></Field></div><button className="primary" disabled={!saleId||!sku.trim()} onClick={check}>Conferir peça</button>{result&&<div className={'shippingResult '+(result.ok?'ok':'bad')}><b>{result.ok?'✓ Conferência aprovada':'⚠ Divergência encontrada'}</b><span>{result.result}</span>{result.product&&<small>{result.product.sku} · {result.product.name}</small>}</div>}</section><section className="panel"><PanelHead eyebrow="HISTÓRICO" title="Conferências recentes" text="Cada leitura fica registrada com venda, SKU, resultado e responsável"/><Table rows={checks} cols={['id','sale_id','sku_scanned','result','checked_by','created_at']} format={{created_at:v=>v?new Date(v).toLocaleString('pt-BR'):'—'}}/></section></>}
   {mode==='evidence'&&<><section className="panel"><div className="formGrid two"><Field label="Venda"><select value={evidence.sale_id} onChange={e=>setEvidence({...evidence,sale_id:e.target.value,product_id:''})}><option value="">Selecione...</option>{sales.map(s=><option key={s.id} value={s.id}>Venda #{s.id} · {money(s.total)}</option>)}</select></Field><Field label="Peça da venda"><select value={evidence.product_id} disabled={!evidence.sale_id} onChange={e=>setEvidence({...evidence,product_id:e.target.value})}><option value="">Venda inteira</option>{evidenceProducts.map(p=><option key={p.id} value={p.id}>{p.sku} · {p.name}</option>)}</select></Field><Field label="Número de série / marcação"><input value={evidence.serial_number} onChange={e=>setEvidence({...evidence,serial_number:e.target.value})}/></Field><Field label="Fotos antes de embalar"><input type="file" accept="image/*" multiple onChange={e=>filesToData(e.target.files)}/></Field><Field label="Condição e observações" wide><textarea value={evidence.condition_notes} onChange={e=>setEvidence({...evidence,condition_notes:e.target.value})} placeholder="Teste realizado, marcas existentes, lacres, embalagem..."/></Field></div>{evidence.photos.length>0&&<div className="evidenceThumbs">{evidence.photos.map((x,i)=><img key={i} src={x} alt={`Evidência ${i+1}`}/>)}</div>}<button className="primary" disabled={!evidence.sale_id} onClick={saveEvidence}>Salvar prova de envio</button></section><section className="panel"><PanelHead eyebrow="HISTÓRICO" title="Evidências registradas" text="Registro interno para conferência e contestação"/><Table rows={saved} cols={['id','sale_id','product_id','serial_number','packed_by','created_at']} format={{created_at:v=>v?new Date(v).toLocaleString('pt-BR'):'—'}}/></section></>}
   {mode==='warranty'&&<section className="panel"><PanelHead eyebrow="GARANTIA DIGITAL" title="Garantia por Código QR" text="Gere um Código QR apenas para uma peça que realmente faz parte da venda."/><div className="formGrid two"><Field label="Venda"><select value={warranty.sale_id} onChange={e=>setWarranty({sale_id:e.target.value,product_id:'',token:'',days:0})}><option value="">Selecione...</option>{sales.map(s=><option key={s.id} value={s.id}>Venda #{s.id} · {money(s.total)}</option>)}</select></Field><Field label="Peça da venda"><select value={warranty.product_id} disabled={!warranty.sale_id} onChange={e=>setWarranty(v=>({...v,product_id:e.target.value,token:''}))}><option value="">Selecione...</option>{warrantyProducts.map(p=><option key={p.id} value={p.id}>{p.sku} · {p.name}</option>)}</select></Field></div><button className="primary" disabled={!warranty.sale_id||!warranty.product_id} onClick={generateWarranty}>Gerar Código QR de garantia</button>{warrantyUrl&&<div className="warrantyGenerator"><QRCodeSVG value={warrantyUrl} size={180}/><div><b>Garantia digital criada</b><span>{warranty.days} dias conforme cadastro da peça.</span><small>{warrantyUrl}</small><button className="ghost" onClick={()=>navigator.clipboard?.writeText(warrantyUrl)}>Copiar endereço</button></div></div>}</section>}
 </>
}


// CDM OPERATIONS PACK V1
function Finance({data,refresh,notice}){
 const empty={kind:'income',description:'',amount:0,status:'paid',due_date:''}
 const [form,setForm]=useState(empty),[editingId,setEditingId]=useState(null),[search,setSearch]=useState(''),[kindFilter,setKindFilter]=useState('all'),[statusFilter,setStatusFilter]=useState('all'),[busy,setBusy]=useState(false)

 const paidIncome=data.filter(x=>x.kind==='income'&&x.status==='paid').reduce((a,x)=>a+Number(x.amount||0),0)
 const paidExpense=data.filter(x=>x.kind==='expense'&&x.status==='paid').reduce((a,x)=>a+Number(x.amount||0),0)
 const pending=data.filter(x=>x.status!=='paid').reduce((a,x)=>a+Number(x.amount||0),0)
 const filtered=useMemo(()=>data.filter(x=>{
   const q=search.trim().toLowerCase()
   return (!q||`${x.description||''} ${x.id||''}`.toLowerCase().includes(q))&&(kindFilter==='all'||x.kind===kindFilter)&&(statusFilter==='all'||x.status===statusFilter)
 }),[data,search,kindFilter,statusFilter])

 function edit(row){
   if(String(row.description||'').trim().toLowerCase().startsWith('venda #'))return notice('Lançamentos automáticos de venda são controlados pela própria venda')
   setEditingId(row.id)
   setForm({kind:row.kind||'income',description:row.description||'',amount:Number(row.amount||0),status:row.status||'paid',due_date:row.due_date||''})
   window.scrollTo({top:0,behavior:'smooth'})
 }

 function cancel(){setEditingId(null);setForm(empty)}

 async function save(){
   if(!form.description.trim())return notice('Informe a descrição do lançamento')
   if(Number(form.amount||0)<=0)return notice('Informe um valor maior que zero')
   setBusy(true)
   try{
     if(editingId)await api.put(`/finance/${editingId}`,form)
     else await api.post('/finance',form)
     cancel();await refresh();notice(editingId?'Lançamento atualizado':'Lançamento salvo')
   }catch(e){
     notice(erroPt(e.response?.data?.detail)||'Não foi possível salvar o lançamento')
   }finally{setBusy(false)}
 }

 async function remove(row){
   if(String(row.description||'').trim().toLowerCase().startsWith('venda #'))return notice('Lançamentos automáticos de venda não podem ser excluídos aqui')
   if(!confirm(`Excluir o lançamento "${row.description}"?`))return
   try{await api.delete(`/finance/${row.id}`);await refresh();notice('Lançamento excluído')}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível excluir')}
 }

 return <>
   <div className="pageTitle financeTitle"><div><span>FINANCEIRO</span><h2>Controle financeiro</h2><p>Entradas, saídas, pendências e saldo realizado da empresa.</p></div><span className="financeBalance">Saldo realizado: <b>{money(paidIncome-paidExpense)}</b></span></div>
   <div className="financeMetrics">
     <div className="income"><small>Entradas pagas</small><strong>{money(paidIncome)}</strong></div>
     <div className="expense"><small>Saídas pagas</small><strong>{money(paidExpense)}</strong></div>
     <div><small>Saldo realizado</small><strong>{money(paidIncome-paidExpense)}</strong></div>
     <div className={pending>0?'pending':''}><small>Valores pendentes</small><strong>{money(pending)}</strong></div>
   </div>

   <section className="panel financeEditor">
     <PanelHead eyebrow={editingId?'EDIÇÃO':'NOVO LANÇAMENTO'} title={editingId?`Editar lançamento #${editingId}`:'Adicionar movimentação'} text="Lançamentos criados automaticamente por vendas ficam protegidos contra edição manual."/>
     <div className="formGrid financeForm">
       <Field label="Tipo"><select value={form.kind} onChange={e=>setForm({...form,kind:e.target.value})}><option value="income">Entrada</option><option value="expense">Saída</option></select></Field>
       <Field label="Descrição"><input value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="Ex.: compra de embalagem"/></Field>
       <Field label="Valor"><input type="number" min="0" step="0.01" value={form.amount} onChange={e=>setForm({...form,amount:+e.target.value})}/></Field>
       <Field label="Situação"><select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}><option value="paid">Pago</option><option value="pending">Pendente</option></select></Field>
       <Field label="Vencimento"><input type="date" value={form.due_date||''} onChange={e=>setForm({...form,due_date:e.target.value})}/></Field>
     </div>
     <div className="financeEditActions">{editingId&&<button className="ghost" onClick={cancel}>Cancelar edição</button>}<button className="primary" disabled={busy} onClick={save}>{busy?'Salvando...':editingId?'Salvar alterações':'+ Salvar lançamento'}</button></div>
   </section>

   <section className="panel">
     <div className="financeToolbar">
       <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar descrição ou código..."/>
       <select value={kindFilter} onChange={e=>setKindFilter(e.target.value)}><option value="all">Todos os tipos</option><option value="income">Entradas</option><option value="expense">Saídas</option></select>
       <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="all">Todas as situações</option><option value="paid">Pagos</option><option value="pending">Pendentes</option></select>
     </div>
     <div className="tableWrap"><table><thead><tr><th>Código</th><th>Tipo</th><th>Descrição</th><th>Valor</th><th>Situação</th><th>Vencimento</th><th>Ações</th></tr></thead><tbody>
       {filtered.length?filtered.map(row=>{const automatic=String(row.description||'').trim().toLowerCase().startsWith('venda #');return <tr key={row.id}><td>#{row.id}</td><td>{valuePt('kind',row.kind)}</td><td><b>{row.description}</b>{automatic&&<small className="block">Automático da venda</small>}</td><td>{money(row.amount)}</td><td><span className={row.status==='paid'?'pill success':'pill warn'}>{statusPt(row.status)}</span></td><td>{row.due_date||'—'}</td><td><div className="rowActions"><button className="ghost" disabled={automatic} onClick={()=>edit(row)}>Editar</button><button className="ghost dangerMini" disabled={automatic} onClick={()=>remove(row)}>Excluir</button></div></td></tr>}):<tr><td colSpan="7" className="empty">Nenhum lançamento encontrado.</td></tr>}
     </tbody></table></div>
   </section>
 </>
}

function CashFlow({data}){
 const paid=data.filter(x=>x.status==='paid')
 const income=paid.filter(x=>x.kind==='income').reduce((a,x)=>a+Number(x.amount||0),0)
 const expense=paid.filter(x=>x.kind==='expense').reduce((a,x)=>a+Number(x.amount||0),0)
 const receivable=data.filter(x=>x.kind==='income'&&x.status!=='paid').reduce((a,x)=>a+Number(x.amount||0),0)
 const payable=data.filter(x=>x.kind==='expense'&&x.status!=='paid').reduce((a,x)=>a+Number(x.amount||0),0)
 return <>
   <div className="grid metrics cashFlowMetrics">
     <Card icon="↑" title="Entradas realizadas" value={money(income)} sub="Valores pagos"/>
     <Card icon="↓" title="Saídas realizadas" value={money(expense)} sub="Valores pagos"/>
     <Card icon="=" title="Saldo realizado" value={money(income-expense)} sub="Entradas - saídas"/>
     <Card icon="⌛" title="A receber / pagar" value={money(receivable-payable)} sub={`${money(receivable)} a receber · ${money(payable)} a pagar`}/>
   </div>
   <section className="panel"><PanelHead eyebrow="CAIXA" title="Fluxo de Caixa" text="Movimentações realizadas e pendentes, sem misturar previsão com dinheiro já recebido."/><Table rows={data} cols={['id','kind','description','amount','status','due_date']} format={{kind:v=>valuePt('kind',v),status:v=>statusPt(v),amount:money}}/></section>
 </>
}

function Reports({products,sales,finance,vehicles}){
 const [from,setFrom]=useState(''),[to,setTo]=useState('')
 const inRange=v=>{
   if(!from&&!to)return true
   if(!v)return false
   const d=new Date(String(v).length<=10?`${v}T12:00:00`:v)
   if(Number.isNaN(d.getTime()))return false
   const a=from?new Date(`${from}T00:00:00`):null,b=to?new Date(`${to}T23:59:59`):null
   return (!a||d>=a)&&(!b||d<=b)
 }
 const reportSales=sales.filter(x=>inRange(x.created_at))
 const reportFinance=finance.filter(x=>inRange(x.due_date||x.created_at))
 const stockValue=products.reduce((a,p)=>a+Number(p.cost||0)*Number(p.stock||0),0)
 const stockSaleValue=products.reduce((a,p)=>a+Number(p.price||0)*Number(p.stock||0),0)
 const revenue=reportSales.reduce((a,s)=>a+Number(s.total||0),0)
 const expenses=reportFinance.filter(x=>x.kind==='expense'&&x.status==='paid').reduce((a,x)=>a+Number(x.amount||0),0)
 const low=products.filter(p=>Number(p.stock||0)<=1).length

 function csvCell(v){return `"${String(v??'').replaceAll('"','""')}"`}
 function exportExcel(){
   const lines=[
     ['RELATÓRIO CDM DESMONTES'],
     ['Período',from||'início',to||'hoje'],
     [],
     ['RESUMO'],
     ['Vendas',revenue],['Despesas pagas',expenses],['Resultado operacional simples',revenue-expenses],['Custo do estoque',stockValue],['Valor de venda do estoque',stockSaleValue],
     [],
     ['VENDAS'],['Código','Canal','Pagamento','Total','Situação','Data'],
     ...reportSales.map(s=>[s.id,valuePt('source',s.source),valuePt('payment_method',s.payment_method),s.total,statusPt(s.status),s.created_at||'']),
     [],
     ['FINANCEIRO'],['Código','Tipo','Descrição','Valor','Situação','Vencimento'],
     ...reportFinance.map(x=>[x.id,valuePt('kind',x.kind),x.description,x.amount,statusPt(x.status),x.due_date||'']),
     [],
     ['ESTOQUE BAIXO'],['SKU','Peça','Estoque','Preço'],
     ...products.filter(p=>Number(p.stock||0)<=1).map(p=>[p.sku,p.name,p.stock,p.price])
   ]
   const csv='\ufeff'+lines.map(r=>r.map(csvCell).join(';')).join('\n')
   const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download=`relatorio-cdm-${new Date().toISOString().slice(0,10)}.csv`;a.click()
 }
 function printReport(){window.print()}

 return <>
   <div className="pageTitle reportTitle"><div><span>RELATÓRIOS</span><h2>Visão gerencial</h2><p>Filtre o período, acompanhe números e exporte o relatório.</p></div><div className="reportActions"><button className="ghost" onClick={printReport}>▤ Imprimir / Salvar PDF</button><button className="excelBtn" onClick={exportExcel}>↓ Exportar Excel (CSV)</button></div></div>
   <section className="panel reportFilters"><div><Field label="De"><input type="date" value={from} onChange={e=>setFrom(e.target.value)}/></Field><Field label="Até"><input type="date" value={to} onChange={e=>setTo(e.target.value)}/></Field><button className="ghost" onClick={()=>{setFrom('');setTo('')}}>Limpar período</button></div><span>{reportSales.length} venda(s) no período</span></section>

   <div className="grid metrics">
     <Card icon="R$" title="Vendas no período" value={money(revenue)} sub={`${reportSales.length} vendas`}/>
     <Card icon="↓" title="Despesas pagas" value={money(expenses)} sub="No período selecionado"/>
     <Card icon="=" title="Resultado simples" value={money(revenue-expenses)} sub="Vendas - despesas"/>
     <Card icon="▤" title="Venda potencial em estoque" value={money(stockSaleValue)} sub={`${products.length} SKUs · custo ${money(stockValue)}`}/>
   </div>

   <div className="twoCols reportTables">
     <section className="panel"><PanelHead eyebrow="VENDAS" title="Vendas do período" text={`${reportSales.length} registro(s)`}/><Table rows={reportSales.slice(0,40)} cols={['id','source','payment_method','total','status','created_at']} format={{source:v=>valuePt('source',v),payment_method:v=>valuePt('payment_method',v),total:money,status:v=>statusPt(v),created_at:v=>v?new Date(v).toLocaleString('pt-BR'):'—'}}/></section>
     <section className="panel"><PanelHead eyebrow="FINANCEIRO" title="Movimentações do período" text={`${reportFinance.length} registro(s)`}/><Table rows={reportFinance.slice(0,40)} cols={['id','kind','description','amount','status','due_date']} format={{kind:v=>valuePt('kind',v),amount:money,status:v=>statusPt(v)}}/></section>
   </div>
   <section className="panel"><PanelHead eyebrow="ESTOQUE" title={`Estoque baixo · ${low} item(ns)`} text="Peças com uma unidade ou menos."/><Table rows={products.filter(p=>Number(p.stock||0)<=1)} cols={['sku','name','stock','price']} format={{price:money}}/></section>
   <section className="panel reportVehicleMini"><span>Sucatas cadastradas</span><strong>{vehicles.length}</strong><small>veículos no sistema</small></section>
 </>
}

function Gamification({sales,products}){const points=sales.length*10+products.length*2;return <section className="panel"><PanelHead eyebrow="EQUIPE" title="Gamificação" text="Metas e produtividade da equipe."/><div className="scoreHero"><small>PONTOS DA OPERAÇÃO</small><strong>{points}</strong><span>Nível {Math.max(1,Math.floor(points/100)+1)}</span><div className="progress"><i style={{width:`${Math.min(100,points%100)}%`}}/></div></div></section>}

function PlatformAdmin({notice}){const [rows,setRows]=useState([]),[busy,setBusy]=useState(true);async function load(){setBusy(true);try{setRows((await api.get('/admin/companies')).data||[])}catch(e){notice(erroPt(e.response?.data?.detail)||'Não foi possível carregar clientes')}finally{setBusy(false)}}useEffect(()=>{load()},[]);async function toggle(c){try{await api.put(`/admin/companies/${c.id}/active`,{active:!c.active});await load();notice('Empresa atualizada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro')}}async function status(c,value){try{await api.put(`/admin/companies/${c.id}/subscription`,{status:value,days:31});await load();notice('Assinatura atualizada')}catch(e){notice(erroPt(e.response?.data?.detail)||'Erro')}}async function backup(){try{const r=await api.get('/admin/backup',{responseType:'blob'});const a=document.createElement('a');a.href=URL.createObjectURL(r.data);a.download=`cdm-backup-${new Date().toISOString().slice(0,10)}.json.gz`;a.click();notice('Cópia de segurança gerada')}catch(e){notice('Não foi possível gerar a cópia de segurança')}}return <><div className="pageTitle"><div><span>ADMINISTRAÇÃO DA PLATAFORMA</span><h2>Clientes e empresas</h2><p>Controle central das empresas assinantes do CDM.</p></div><button className="primary" onClick={backup}>↓ Baixar cópia de segurança agora</button></div><section className="panel"><PanelHead eyebrow="CLIENTES" title={busy?'Carregando...':`${rows.length} empresas cadastradas`} text="Ative/desative empresas e acompanhe assinatura, produtos e vendas."/><div className="adminCompanyGrid">{rows.map(c=><article className="adminCompany" key={c.id}><div><small>EMPRESA #{c.id}</small><h3>{c.trade_name||'Sem nome'}</h3><p>{c.email||'sem e-mail'} · {c.cnpj||'sem CNPJ'}</p></div><div className="adminStats"><span><b>{c.products}</b> peças</span><span><b>{c.sales}</b> vendas</span><span><b>{c.users}</b> usuários</span><span><b>{c.connections}</b> canais</span></div><div className="adminActions"><span className={c.active?'pill success':'pill warn'}>{c.active?'Empresa ativa':'Empresa bloqueada'}</span><span className={['active','trial'].includes(c.subscription_status)?'pill success':'pill warn'}>{statusPt(c.subscription_status)}</span><button className="ghost" onClick={()=>toggle(c)}>{c.active?'Bloquear':'Ativar'}</button><select value={c.subscription_status} onChange={e=>status(c,e.target.value)}><option value="trial">Teste</option><option value="active">Ativa</option><option value="pending">Pendente</option><option value="past_due">Atrasada</option><option value="canceled">Cancelada</option><option value="inactive">Inativa</option></select></div></article>)}</div></section></>}

function SimpleModule({eyebrow,title,text,actions=[]}){return <><div className="pageTitle"><div><span>{eyebrow}</span><h2>{title}</h2><p>{text}</p></div></div><div className="moduleCards">{actions.map((a,i)=><div className="moduleCard" key={a}><div className="moduleIcon">{['+','▤','⚙'][i%3]}</div><div><h3>{a}</h3><p>Módulo organizado e pronto para receber regras específicas.</p><span className="pill neutral">Disponível</span></div></div>)}</div></>}
function Checklist({items}){return <div className="checklist">{items.map(i=><span key={i}>✓ {i}</span>)}</div>}
function PanelHead({eyebrow,title,text}){return <div className="panelTitle"><div><small>{eyebrow}</small><h2>{title}</h2><p>{text}</p></div></div>}
function Field({label,children,wide}){return <label className={'field '+(wide?'wide':'')}><span>{label}</span>{children}</label>}
function Table({rows,cols,format={}}){return <div className="tableWrap"><table><thead><tr>{cols.map(c=><th key={c}>{pretty(c)}</th>)}</tr></thead><tbody>{rows?.length?rows.map((r,i)=><tr key={r.id||i}>{cols.map(c=><td key={c}>{format[c]?format[c](r[c]):String(valuePt(c,r[c])??'')}</td>)}</tr>):<tr><td colSpan={cols.length} className="empty">Nenhum registro ainda.</td></tr>}</tbody></table></div>}
function pretty(s){
 const raw=String(s??'').trim(),key=raw.toLowerCase()
 const labels={
  id:'Código',sku:'SKU',name:'Nome',plate:'Placa',brand:'Marca',model:'Modelo',year:'Ano',fuel:'Combustível',transmission:'Câmbio',status:'Situação',
  category:'Categoria',part_group:'Grupo de peças',condition:'Condição',side:'Lado',position:'Posição',cost:'Custo',price:'Preço',stock:'Estoque',
  cpf_cnpj:'CPF / CNPJ',commission_rate:'Comissão %',cfop_default:'CFOP padrão',ncm_default:'NCM padrão',csosn_default:'CSOSN padrão',
  created_at:'Criado em',updated_at:'Atualizado em',payment_method:'Pagamento',acquisition_value:'Valor de aquisição',other_costs:'Outros custos',
  trade_name:'Nome Fantasia',legal_name:'Razão Social',state_registration:'Inscrição Estadual',tax_regime:'Regime tributário',responsible_name:'Responsável',
  issuing_agency:'Órgão expedidor',rg_ie:'RG / Inscrição Estadual',mobile:'Celular',phone:'Telefone',email:'E-mail',cep:'CEP',city:'Cidade',state:'UF',
  number:'Número',address:'Logradouro',neighborhood:'Bairro',complement:'Complemento',ibge:'IBGE',active:'Ativo',code:'Sigla',max_quantity:'Quantidade máxima',
  quantity_delta:'Movimento',balance_after:'Saldo',reference:'Referência',source:'Canal',access_key:'Chave de acesso',kind:'Tipo',description:'Descrição',
  amount:'Valor',due_date:'Vencimento',total:'Total',customer_id:'Cliente',query:'Pesquisa',count:'Quantidade de buscas',days:'Dias',quantity:'Quantidade',
  revenue:'Faturamento',sale_id:'Venda',product_id:'Peça',serial_number:'Número de série',packed_by:'Responsável pelo envio',recipient:'Destinatário',series:'Série',
  role:'Perfil',users:'Usuários',products:'Peças',sales:'Vendas',connections:'Canais',external_order_id:'Pedido externo',sku_scanned:'SKU conferido',
  result:'Resultado',checked_by:'Conferido por',historical_average:'Média histórica',sales_sample:'Vendas no cálculo',quality_grade:'Qualidade',warranty_days:'Garantia (dias)',
  warehouse:'Depósito',aisle:'Corredor',shelf:'Prateleira',bin:'Posição',payer_email:'E-mail do pagador',account_name:'Conta',external_account_id:'Conta externa'
 }
 if(labels[key])return labels[key]
 const cleaned=raw.replaceAll('_',' ')
 return cleaned.replace(/^./,x=>x.toUpperCase())
}
function marketName(id){return id==='mercadolivre'?'Mercado Livre':id==='shopee'?'Shopee':'OLX'}
function marketDesc(id){return id==='mercadolivre'?'O cliente autoriza a própria conta pela tela oficial do Mercado Livre e publica suas peças.':id==='shopee'?'A loja do cliente fica vinculada à empresa dele no CDM.':'Autorização oficial e importação de anúncios para contas com plano compatível.'}

createRoot(document.getElementById('root')).render(<App/>)
