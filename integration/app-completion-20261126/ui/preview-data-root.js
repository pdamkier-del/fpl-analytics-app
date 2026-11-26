(function(){
 const native=window.fetch.bind(window),ui=new URL('../',location.href),parent=new URL('../../',location.href);
 const data=new URL('https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/');
 window.fetch=(input,options)=>{
  const url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
  if(url.origin===ui.origin&&/\.json(?:\.gz)?$/.test(url.pathname)){
   if(url.pathname.startsWith(ui.pathname))return native(new URL(url.pathname.slice(ui.pathname.length),data),options);
   if(url.pathname===parent.pathname+'manager-service.json')return native(new URL('../manager-service.json',data),options);
  }
  return native(input,options);
 };
})();
