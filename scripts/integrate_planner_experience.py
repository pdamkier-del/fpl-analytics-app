"""Preview-only usability around unchanged MM/PM/TS and private state contracts."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
def inject(out):
    if out.parent.resolve()!=(ROOT/'app/mm-preview').resolve():
        for asset in ['planner-experience.js','planner-experience.css','dashboard-team-news.js','dashboard-team-news.css','history-explorer.js']:
            shutil.copyfile(ROOT/'app/mm-preview'/asset,out.parent/asset)
    for name in ['weekly-app.js','classic-manager.js']:
        path=out/name;text=path.read_text()
        old="throw Error('Registrér et lovligt faktisk hold og det korrekte observationstidspunkt.')"
        if text.count(old)!=1:raise ValueError('Planner validation anchor changed')
        text=text.replace(old,"throw Error(FplPlannerExperience.diagnose(state,forecast).join(' ')||'Kontrollér holdets oplysninger.')")
        if name=='weekly-app.js':
            old="document.getElementById('compute')?.addEventListener('click',compute);dashboardNews.afterRender();"
            new=old+"FplPlannerExperience.mount({forecast,people,state,plan,busy,usable:usable&&dashboardNews.status().aligned});"
        else:
            old="function render(){onChange();feedback();"
            new="function render(){onChange();FplPlannerExperience.mount(snapshot());feedback();"
            # load() returns the snapshot before initial classic page draw.
        if text.count(old)!=1:raise ValueError('Planner rendering anchor changed')
        path.write_text(text.replace(old,new))
    manager=out/'classic-manager.js';text=manager.read_text()
    reason="""function waitingReason(){
 if(!forecast)return '';
 const issues=FplPlannerExperience.diagnose(state,forecast);if(issues.length)return issues.join(' ');
 const clock=x=>new Date(x).toLocaleString('da-DK',{timeZone:'Europe/Copenhagen'});
 if(Date.parse(state.observed_at)>Date.parse(forecast.data_asof))return 'Dit hold er bekræftet '+clock(state.observed_at)+', men modeldata er fra '+clock(forecast.data_asof)+'. Venter på nyere modeldata. Du skal ikke bekræfte holdet igen.';
 const window=FplForecastWindow.check(forecast,official);if(!window.usable)return window.reason;
 const news=FplTeamNews.evaluate({news:latestTeamNews,official,forecast,state,stateValid:stateLegal(state,false),usable:true,error:latestTeamNewsError});return news.aligned?'':news.message;
}
"""
    old='function feedback(){'
    if text.count(old)!=1:raise ValueError('Feedback diagnosis anchor changed')
    text=text.replace(old,reason+old)
    text=text.replace('message:computeMessage,error:computeError','message:computeMessage||waitingReason(),error:computeError')
    text=text.replace('reason:FplForecastWindow.check(forecast,official).reason','reason:waitingReason()||FplForecastWindow.check(forecast,official).reason')
    manager.write_text(text)
    path=out/'classic-transfers.js';text=path.read_text();old='const c=FplManagerClient.snapshot();target.replaceChildren();button.disabled=c.busy;'
    if text.count(old)!=1:raise ValueError('Transfer page anchor changed')
    text=text.replace(old,old+'FplPlannerExperience.mount(c);')
    path.write_text(text)
    path=out/'classic-transfer-preview.js';text=path.read_text()
    text=text.replace('window.FplTransferPreview={render};', 'window.FplTransferPreview={render:()=>{render();FplPlannerExperience.comparison(FplManagerClient.snapshot());}};')
    text=text.replace("window.addEventListener('fpl-plan-updated',render);", "window.addEventListener('fpl-plan-updated',()=>{render();FplPlannerExperience.comparison(FplManagerClient.snapshot());});")
    path.write_text(text)
    path=out/'transfer-card.js';text=path.read_text();old='return result+\'</div>\'}'
    if text.count(old)!=1:raise ValueError('Transfer explanation anchor changed')
    path.write_text(text.replace(old,"return result+(compact?'':FplPlannerExperience.explanation(p,people))+'</div>'}"))
    for page in out.glob('*.html'):
        text=page.read_text()
        if 'match-data.js' in text:
            text=text.replace('</head>','<link rel="stylesheet" href="../planner-experience.css?v=1"></head>')
            text=text.replace('<script src="match-data.js"></script>','<script src="match-data.js"></script><script src="../history-explorer.js?v=1"></script>')
        page.write_text(text)
        if not any(s in text for s in ['weekly-app.js','classic-manager.js']):continue
        text=text.replace('</head>','<script src="../planner-experience.js?v=1"></script><link rel="stylesheet" href="../planner-experience.css?v=1"></head>')
        for name in ['weekly-app.js','classic-manager.js','classic-transfers.js','transfer-card.js','classic-transfer-preview.js']:
            text=text.replace('src="'+name+'?', 'src="'+name+'?planner=1&').replace('src="'+name+'"','src="'+name+'?planner=1"')
        text=text.replace('dashboard-team-news.js?v=1','dashboard-team-news.js?v=planner-1')
        page.write_text(text)
