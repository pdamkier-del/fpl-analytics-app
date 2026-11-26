'use strict';
// Pure presentation/accounting helpers. No TS search or model sampling.
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.FplSharedTeamModel=api;})(globalThis,()=>{
 function lineup(picks,people){
  const sorted=[...picks].sort((a,b)=>a.position-b.position),ids=sorted.map(p=>p.element),xi=ids.slice(0,11);
  const counts=[0,0,0,0,0];for(const id of xi){const p=people.get(id);if(!p)return null;counts[p.position]++;}
  const captain=sorted.find(p=>p.is_captain)?.element,vice=sorted.find(p=>p.is_vice_captain)?.element;
  return ids.length===15&&new Set(ids).size===15&&counts[1]===1&&counts[2]>=3&&counts[2]<=5&&counts[3]>=2&&counts[3]<=5&&counts[4]>=1&&counts[4]<=3&&captain!==vice&&xi.includes(captain)&&xi.includes(vice)?{ids,captain,vice}:null;
 }
 function sale(purchase,current){return current<=purchase?current:purchase+Math.floor((current-purchase)/2);}
 function compare(original,draft,people){
  const old=new Map(original?.squad?.map(p=>[p.id,p])||[]),out=[...old.keys()].filter(id=>!draft.includes(id)),incoming=draft.filter(id=>!old.has(id));
  let bank=Number.isInteger(original?.bank_tenths)?original.bank_tenths:null;
  for(const id of out){const buy=old.get(id)?.purchase_price_tenths,price=people.get(id)?.price_tenths;if(!Number.isInteger(buy)||!Number.isInteger(price))bank=null;else if(bank!==null)bank+=sale(buy,price);}
  for(const id of incoming){const price=people.get(id)?.price_tenths;if(!Number.isInteger(price))bank=null;else if(bank!==null)bank-=price;}
  const counts=[0,0,0,0,0],clubs={};for(const id of draft){const p=people.get(id);if(!p)return {valid:false,reason:'Spilleren mangler i prognosen.'};counts[p.position]++;clubs[p.team_id]=(clubs[p.team_id]||0)+1;}
  const valid=draft.length===15&&new Set(draft).size===15&&counts.slice(1).join(',')==='2,5,5,3'&&Object.values(clubs).every(n=>n<=3)&&(bank===null||bank>=0);
  const ft=original?.free_transfers,hits=Number.isInteger(ft)?4*Math.max(0,incoming.length-ft):null;
  const deltas=[1,3,6].map(n=>{const value=ids=>ids.reduce((s,id)=>{const w=people.get(id)?.weeks?.slice(0,n);return w?.length===n&&w.every(x=>Number.isFinite(x.xpts))?s+w.reduce((a,x)=>a+x.xpts,0):NaN;},0);return value(incoming)-value(out);});
  return {valid,reason:valid?'':bank!==null&&bank<0?'Budgettet er overskredet.':'Ugyldig position, klubgrænse eller dubleret spiller.',out,incoming,bank,hits,deltas};
 }
 return {lineup,sale,compare};
});
