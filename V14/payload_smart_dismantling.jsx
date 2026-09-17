function SmartDismantling({vehicles=[],notice}){
 const [vehicleId,setVehicleId]=useState('')
 const [plan,setPlan]=useState(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')

 useEffect(()=>{
   if(!vehicleId&&vehicles.length)setVehicleId(String(vehicles[0].id))
 },[vehicles,vehicleId])

 useEffect(()=>{
   if(vehicleId)loadPlan()
   else setPlan(null)
 },[vehicleId])

 async function loadPlan(){
   if(!vehicleId)return
   setBusy(true);setError('')
   try{
     const r=await api.get(`/v14/vehicles/${vehicleId}/smart-dismantling`)
     setPlan(r.data)
   }catch(e){
     setError(erroPt(e.response?.data?.detail)||'Não foi possível analisar o veículo')
   }finally{setBusy(false)}
 }

 async function setStage(status){
   if(!vehicleId)return
   setBusy(true);setError('')
   try{
     const r=await api.post(`/v14/vehicles/${vehicleId}/dismantling-state`,{status})
     setPlan(r.data.plan)
     notice?.(status==='in_progress'?'Desmontagem iniciada':status==='completed'?'Desmontagem concluída':'Status atualizado')
   }catch(e){
     const msg=erroPt(e.response?.data?.detail)||'Não foi possível atualizar a desmontagem'
     setError(msg);notice?.(msg)
   }finally{setBusy(false)}
 }

 const s=plan?.summary||{}
 const rows=plan?.suggestions||[]
 const selected=vehicles.find(v=>String(v.id)===String(vehicleId))
 const status=plan?.dismantling?.status||'pending'

 return <div className="smartDismantlingPage">
   <div className="pageTitle">
     <div><span>INTELIGÊNCIA OPERACIONAL</span><h2>Desmonte Inteligente</h2><p>Priorize as peças mais importantes, acompanhe o que já foi cadastrado e avance o ciclo da sucata.</p></div>
     <span className="pill neutral">Inteligência local · sem credencial externa</span>
   </div>

   <section className="panel smartDismantlingControl">
     <div>
       <small>VEÍCULO</small>
       <select value={vehicleId} onChange={e=>setVehicleId(e.target.value)}>
         <option value="">Selecione um veículo...</option>
         {vehicles.map(v=><option key={v.id} value={v.id}>{[v.brand,v.model,v.year].filter(Boolean).join(' ')||`Veículo #${v.id}`} {v.plate?`· ${v.plate}`:''}</option>)}
       </select>
     </div>
     <div className="smartDismantlingActions">
       <button className="ghost" onClick={loadPlan} disabled={!vehicleId||busy}>↻ Recalcular</button>
       <button className="primary" onClick={()=>setStage('in_progress')} disabled={!vehicleId||busy||status==='in_progress'}>▶ Iniciar desmontagem</button>
       <button className="ghost" onClick={()=>setStage('completed')} disabled={!vehicleId||busy||status==='completed'}>✓ Concluir desmontagem</button>
     </div>
   </section>

   {error&&<div className="error">{error}</div>}
   {!vehicleId?<div className="emptyState">Cadastre ou selecione um veículo para gerar o plano.</div>:busy&&!plan?<div className="emptyState">Analisando veículo...</div>:plan&&<>
     <div className="smartDismantlingHero">
       <div><small>VEÍCULO ANALISADO</small><h3>{plan.vehicle?.label||selected?.model||'Veículo'}</h3><span>{plan.vehicle?.plate||'Sem placa'} · {statusPt(plan.vehicle?.status)}</span></div>
       <div><small>DESMONTAGEM</small><b>{statusPt(status)}</b></div>
     </div>

     <div className="smartDismantlingKpis">
       <article><span>SUGESTÕES PENDENTES</span><b>{s.pending_suggestions||0}</b><small>itens para conferir e cadastrar</small></article>
       <article><span>JÁ CADASTRADAS</span><b>{s.already_registered||0}</b><small>categorias identificadas no veículo</small></article>
       <article><span>TOTAL INVESTIDO</span><b>{money(s.total_invested||0)}</b><small>compra + custos + despesas</small></article>
       <article><span>ESTOQUE ESTIMADO</span><b>{money(s.estimated_current_stock_value||0)}</b><small>valor atual das peças cadastradas</small></article>
     </div>

     <section className="panel smartDismantlingPlan">
       <div className="smartPlanHead">
         <div><small>PLANO DE RETIRADA</small><h3>Prioridades sugeridas</h3><p>O CDM cruza prioridade da peça com o histórico de vendas da própria empresa.</p></div>
         <span>{rows.length} grupos analisados</span>
       </div>
       <div className="smartPlanRows">
         {rows.map((x,i)=><div key={x.title} className={'smartPlanRow '+(x.registered?'done':'')}>
           <div className="smartPlanRank">{x.registered?'✓':i+1}</div>
           <div className="smartPlanName"><b>{x.title}</b><small>{x.action}</small></div>
           <div><small>Prioridade</small><b>{x.priority}/100</b></div>
           <div><small>Vendas 12m</small><b>{x.company_sales_12m||0}</b></div>
           <div><small>Preço médio</small><b>{x.average_sale_price?money(x.average_sale_price):'Sem histórico'}</b></div>
           <div><span className={'pill '+(x.registered?'success':'neutral')}>{x.registered?'Já cadastrada':'Pendente'}</span></div>
         </div>)}
       </div>
     </section>
   </>}
 </div>
}
