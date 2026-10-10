/* Shared navigation shell. Presentation only; never reads/writes model or squad state. */
(()=>{
'use strict';
document.documentElement.classList.add('fpl-v2');
const file=(location.pathname.split('/').pop()||'overview.html').toLowerCase();
const section=({
'overview.html':'overview','mobile.html':'overview','index.html':'fixtures',
'my-team-live.html':'squad','my-team.html':'squad',
'own-forecast.html':'forecast','forecast-live.html':'forecast','forecast-history.html':'forecast','forecast-center.html':'forecast',
'team-optimizer.html':'transfers',
'fixtures-live.html':'fixtures','current-players.html':'forecast','rankings.html':'forecast',
'models.html':'models','live-model-status.html':'models','replay.html':'models'
})[file]||'overview';
document.body.classList.add('page-'+section);
if(file==='mobile.html')document.body.classList.add('page-mobile');
const links=[
{key:'overview',href:'overview.html',label:'Overblik',short:'Overblik',glyph:'⌂'},
{key:'squad',href:'my-team-live.html',label:'Mit hold',short:'Mit hold',glyph:'♟'},
{key:'forecast',href:'own-forecast.html',label:'Forecast',short:'Forecast',glyph:'⌁'},
{key:'transfers',href:'team-optimizer.html',label:'Transfers',short:'Transfers',glyph:'⇄'},
{key:'fixtures',href:'fixtures-live.html',label:'Kampe',short:'Kampe',glyph:'⚽'},
{key:'models',href:'models.html',label:'Modellen',short:'Model',glyph:'◇'}
];
const element=(tag,klass,attrs={})=>{
 const e=document.createElement(tag);
 if(klass)e.className=klass;
 for(const [key,val] of Object.entries(attrs))e.setAttribute(key,val);
 return e;
};
const skip=element('a','fpl-skip',{href:'#fpl-main'});
skip.textContent='Spring til indhold';
const header=element('header','fpl-appbar');
const brand=element('a','fpl-brand',{href:'overview.html','aria-label':'FPL Analytics – overblik'});
const mark=element('span','fpl-brand-symbol');mark.textContent='xP';
const brandText=element('span','fpl-brand-text');brandText.innerHTML='FPL <em>Analytics</em>';
brand.append(mark,brandText);header.appendChild(brand);
const nav=element('nav','fpl-desktop-nav',{'aria-label':'Hovednavigation'});
for(const item of links){
 const a=element('a',item.key===section?'active':'',{href:item.href});
 if(item.key===section)a.setAttribute('aria-current','page');
 a.textContent=item.label;nav.appendChild(a);
}
header.appendChild(nav);
const status=element('a','fpl-nav-model',{href:'live-model-status.html'});
status.textContent='Modelstatus';
header.appendChild(status);
// Keep the existing player-jump search functional even when the old sidebar is hidden.
const oldSearch=document.querySelector('.sidebar .global-player-jump');
if(oldSearch){
 oldSearch.classList.add('fpl-appbar-search');
 const heading=oldSearch.querySelector('.jump-label');
 if(heading)heading.textContent='Historisk søgning';
 const input=oldSearch.querySelector('input');
 if(input)input.placeholder='Søg historiske spillere…';
 header.insertBefore(oldSearch,nav);
 const trigger=element('button','fpl-search-toggle',{'type':'button','aria-label':'Søg i historiske spillere','aria-expanded':'false'});
 trigger.textContent='⌕';
 trigger.addEventListener('click',()=>{
  const opened=header.classList.toggle('search-active');
  trigger.setAttribute('aria-expanded',String(opened));
  if(opened)input?.focus();
 });
 header.appendChild(trigger);
}
const mobileNav=element('nav','fpl-bottom-nav',{'aria-label':'Mobil navigation'});
for(const item of links.slice(0,5)){
 const a=element('a',item.key===section?'active':'',{href:item.href});
 if(item.key===section)a.setAttribute('aria-current','page');
 const glyph=element('span','fpl-nav-icon',{'aria-hidden':'true'});
 const drawings={
  overview:'<path d="m3 10 9-7 9 7"/><path d="M5 9v12h14V9"/><path d="M9 21v-8h6v8"/>',
  squad:'<circle cx="9" cy="7.5" r="3"/><path d="M2.5 20v-2.5A5.5 5.5 0 0 1 8 12h2a5.5 5.5 0 0 1 5.5 5.5V20"/><path d="M16 5a3 3 0 0 1 0 6M16.5 13a5 5 0 0 1 5 5v2"/>',
  forecast:'<path d="M3 3v18h18"/><path d="m6 16 4-5 4 3 5-8"/>',
  transfers:'<path d="M4 8h15l-4-4"/><path d="m19 8-4 4"/><path d="M20 16H5l4-4"/><path d="m5 16 4 4"/>',
  fixtures:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/><path d="m10 15 2 2 4-4"/>'
 };
 glyph.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+(drawings[item.key]||'')+'</svg>';
 const label=element('span','');label.textContent=item.short;
 a.append(glyph,label);mobileNav.appendChild(a);
}
document.body.prepend(header);
document.body.prepend(skip);
document.body.appendChild(mobileNav);
const main=document.querySelector('main');
if(main&&!main.id)main.id='fpl-main';
else if(!main){const surface=document.querySelector('.app');if(surface)surface.id='fpl-main';}
})();
