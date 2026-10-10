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
const mobileNav=element('nav','fpl-bottom-nav',{'aria-label':'Mobil navigation'});
for(const item of links.slice(0,5)){
 const a=element('a',item.key===section?'active':'',{href:item.href});
 if(item.key===section)a.setAttribute('aria-current','page');
 const glyph=element('span','fpl-nav-icon',{'aria-hidden':'true'});glyph.textContent=item.glyph;
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
