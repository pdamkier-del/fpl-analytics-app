"""Retry temporary capacity refusals in copied B clients only."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]

def inject(out):
    if out.parent.resolve()!=(ROOT/'app/mm-preview').resolve():
        shutil.copyfile(ROOT/'app/mm-preview/preview-capacity.js',out.parent/'preview-capacity.js')
    for name in ['classic-manager.js','weekly-app.js']:
        path=out/name;text=path.read_text()
        old="const response=await boundedFetch(service.url+'/preview/plans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state,forecast_cutoff:forecast.data_asof,forecast_sha256:forecast.forecast_sha256,request_id:job.id,request_key:job.key})});"
        news="await dashboardNews.refresh();if(!dashboardNews.status().aligned)throw Error(dashboardNews.status().message);" if name=='weekly-app.js' else "latestTeamNews=await FplTeamNews.load();if(!FplTeamNews.evaluate({news:latestTeamNews,official,forecast,usable:true}).aligned)throw Error('Nye spillermeldinger kræver opdaterede modeldata. Tryk Vis nyeste transferplan.');"
        new="""const response=await FplPreviewCapacity.submit({url:service.url+'/preview/plans',body:{state,forecast_cutoff:forecast.data_asof,forecast_sha256:forecast.forecast_sha256,request_id:job.id,request_key:job.key},request:boundedFetch,onWait:seconds=>setComputeStatus('Venter på ledig beregningsplads. Prøver automatisk igen om '+seconds+' sekunder. Holdet er bevaret; der er endnu ikke startet et nyt job.'),beforeRetry:async()=>{
 await readSaved();if(await hash(state)!==job.manager_state_sha256)throw Error('Dit hold er ændret under ventetiden. Tryk Vis nyeste transferplan for at bruge det opdaterede hold.');
 const r=await boundedFetch(new URL('../current/index.json',location.href),{cache:'no-store'});if(!r.ok)throw Error('Modelstatus kan ikke verificeres. Din forespørgsel er bevaret.');const index=await r.json();if(index.forecast_sha256!==job.forecast_sha256||index.data_asof!==job.forecast_cutoff)throw Error('Der er kommet nye modeldata under ventetiden. Tryk Vis nyeste transferplan.');
 NEWS
 if(plan)return false;return true;
}});if(response===null){sessionStorage.removeItem('fpl-private-B-preview-job');busy=false;setComputeStatus('Din nyeste plan er allerede klar i denne browser.');render();return;}""".replace('NEWS',news)
        if text.count(old)!=1:raise ValueError('Preview submission anchor changed: '+name)
        path.write_text(text.replace(old,new))
    feedback=out/'compute-feedback.js';text=feedback.read_text()
    old="if(c.busy)return {kind:'running'"
    new="if(c.busy&&/^Venter på ledig beregningsplads/.test(message))return {kind:'queued',title:'Venter på ledig beregningsplads',detail:message};"+old
    if text.count(old)!=1:raise ValueError('Queue feedback anchor changed')
    text=text.replace(old,new)
    text=text.replace("const message=c.message||'';","const message=c.message||'';if(c.error&&/Beregningstjenesten er stadig optaget/.test(message))return {kind:'waiting',title:'Ventetiden er udløbet',detail:message};")
    text=text.replace("c.busy?'Beregning i gang…'","c.busy&&/^Venter på ledig beregningsplads/.test(c.message||'')?'Venter på ledig plads…':c.busy?'Beregning i gang…'")
    feedback.write_text(text)
    for page in out.glob('*.html'):
        text=page.read_text()
        if not any(name in text for name in ['classic-manager.js','weekly-app.js']):continue
        page.write_text(text.replace('</head>','<script src="../preview-capacity.js"></script></head>'))
