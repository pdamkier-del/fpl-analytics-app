'use strict';
(function(root){
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=n=>Number.isFinite(n)?n.toFixed(2):'Not Available';
 function summary(plan){
  const path=plan?.plan?.path;
  const horizon=Number.isInteger(plan?.gw)&&plan.gw>=1&&plan.gw<=38?Math.min(6,39-plan.gw):0;
  if(!Array.isArray(path)||!horizon||path.length!==horizon||path.some((r,i)=>r.gw!==plan.gw+i))throw Error('Den originale seks-GW-plan mangler');
  if(!path.every(r=>Number.isFinite(r.projected_manager_score)&&Number.isFinite(r.official_hit_points)))throw Error('Planens point eller hits mangler');
  return {current:plan.current_team?.expected_score,recommended:path[0].projected_manager_score,
   hits:path[0].official_hit_points,six:path.reduce((n,r)=>n+r.projected_manager_score-r.official_hit_points,0)};
 }
 function render(plan,people,target){
  const s=summary(plan);
  root.FplPlanView.render(plan,people,target);
  // Keep navigation inside this sealed snapshot instead of resolving old
  // production links relative to /mm-preview/ (which caused 404s).
  for(const [from,to] of [['vfinal-diagnostic.html','#content'],['models.html','#modelDetails']]){
   const a=target.querySelector('a[href="'+from+'"]');if(a)a.setAttribute('href',to);
  }
  const box=document.createElement('section');box.className='personal-summary';
  const actual=plan.current_team?.rows;
  box.innerHTML='<h3>Dit nuværende hold · uden foreslåede transfers</h3><p>Bedste XI og kaptajn på din nuværende trup: <strong>'+num(s.current)+' xP</strong>. Ingen spillere er ændret eller gemt.</p>'+
   (Array.isArray(actual)?'<div class="scroll"><table><thead><tr><th>Rolle</th><th>Spiller</th><th>xP</th></tr></thead><tbody>'+actual.map(r=>'<tr><td>'+esc(r.role)+'</td><td>'+esc(people.get(Number(r.id))?.name||r.id)+'</td><td>'+num(r.xpts_mean)+'</td></tr>').join('')+'</tbody></table></div>':'<p>Not Available: serverens opstilling på den nuværende trup mangler.</p>')+
   '<h3>Modellens transferforslag · ikke udført</h3><p>XI inklusive kaptajn: <strong>'+num(s.recommended)+' xP</strong> før '+num(s.hits)+' hit-point. Horisonten (op til seks GW): <strong>'+num(s.six)+' xP efter officielle hits</strong>. Summen kommer direkte fra den originale Python-plans seks handlinger, ikke en ny JavaScript-model.</p>';
  target.prepend(box);
 }
 const api={summary,render};root.FplBPersonalView=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
