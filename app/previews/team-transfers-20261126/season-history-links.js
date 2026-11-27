'use strict';
(function(){
 const link=document.getElementById('archive-club-link'),select=document.getElementById('clubSelect');if(!link||!select)return;
 const update=()=>{const club=select.value||new URLSearchParams(location.search).get('club');link.href='history-classic.html?view=teams'+(/^\d+$/.test(club||'')?'&club='+encodeURIComponent(club):'');};
 select.addEventListener('change',update);new MutationObserver(update).observe(select,{childList:true});update();
})();
