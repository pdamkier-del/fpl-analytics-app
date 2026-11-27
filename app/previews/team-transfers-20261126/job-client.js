'use strict';
(function(root){
 async function request(url,options={},timeout=45000,fetcher=fetch){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
  try{
   const response=await fetcher(url,{...options,cache:'no-store',signal:controller.signal});
   if(!response.ok){let message;try{message=(await response.json()).error;}catch{}
    const error=Error(message||'HTTP '+response.status+' fra '+(url.startsWith('http')?'beregningstjenesten':url));error.httpStatus=response.status;throw error;
   }
   return await response.json();
  }catch(error){
   if(error.name==='AbortError')throw Error('Forbindelsen fik timeout; dit hold og job er bevaret.');
   throw error;
  }finally{clearTimeout(timer);}
 }
 function terminal(error){return [404,410,422].includes(error.httpStatus);}
 const api={request,terminal};root.FplBJobClient=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
