"""Add private team news and automatic next-GW planning to desktop copies only."""

def inject(out):
    path=out/'weekly-app.js';text=path.read_text()
    def change(old,new):
        nonlocal text
        if text.count(old)!=1:raise ValueError('Desktop dashboard integration anchor changed: '+old[:70])
        text=text.replace(old,new,1)
    change("const notice=()=>", "const dashboardNews=FplTeamNews.controller({get:()=>({forecast,official,state,plan,usable,busy,stateValid:!!forecast&&stateLegal(state,false)}),compute:()=>compute(),render:()=>render(),hash,hasJob:()=>sessionStorage.getItem('fpl-private-B-preview-job')});\nconst notice=()=>")
    change("if(route==='dashboard'){", "if(route==='dashboard'){\n const teamStatus=dashboardNews.status(),currentPlan=teamStatus.planReady?plan:null;")
    change("+'</div><div class=\"dashboard-columns\"><section class=\"panel\"><h2>Mit faktiske hold", "+'</div>'+dashboardNews.html()+'<div class=\"dashboard-columns\"><section class=\"panel\"><h2>Mit faktiske hold")
    change("(plan?FplTransferCard.html(plan,people,true):missing())", "(teamStatus.planReady?FplTransferCard.html(plan,people,true):dashboardNews.planMessage())")
    change("document.getElementById('compute')?.addEventListener('click',compute);", "document.getElementById('compute')?.addEventListener('click',compute);dashboardNews.afterRender();")
    change("if(!service.url)throw Error(", "if(!dashboardNews.status().canCompute)throw Error(dashboardNews.status().message);\n if(!service.url)throw Error(")
    change("usable=FplForecastWindow.check(forecast,official).usable;if(!initialImportHandled)", "usable=FplForecastWindow.check(forecast,official).usable;await dashboardNews.refresh();if(!initialImportHandled)")
    change("await readSaved();if(new URLSearchParams(location.search).get('run-plan')", "await readSaved();if(!dashboardNews.status().aligned)plan=null;if(new URLSearchParams(location.search).get('run-plan')")
    start=text.index("if(route==='dashboard'){");end=text.index("}else if(route==='players'){",start)
    block=text[start:end].replace('const first=plan?.plan.path[0],chosen=plan?.chip_assessment?', 'const first=currentPlan?.plan.path[0],chosen=currentPlan?.chip_assessment?').replace('const valid=usable&&stateLegal(state)', 'const valid=teamStatus.aligned&&usable&&stateLegal(state)').replace("(plan?'<p>Modellens", "(currentPlan?'<p>Modellens")
    text=text[:start]+block+text[end:]
    change('busy=true;if(button)button.disabled=true;', 'busy=true;if(button)button.disabled=true;render();')
    change('if(activeButton)activeButton.disabled=false}', 'if(activeButton)activeButton.disabled=false;render();}')
    change('&&!busy&&usable&&stateLegal(state)){sessionStorage.removeItem', '&&!busy&&usable&&stateLegal(state)&&dashboardNews.status().aligned){sessionStorage.removeItem')
    # Keep an in-flight result from appearing ready after newer injury news.
    change("if(d.status==='completed'){const latest=", "if(d.status==='completed'){await dashboardNews.refresh();if(!dashboardNews.status().aligned)throw Error('Ny spillerstatus: afventer opdateret forecast før forslaget kan bruges.');const latest=")
    path.write_text(text)
    manager=out/'classic-manager.js';mt=manager.read_text()
    def manager_change(old,new):
        nonlocal mt
        if mt.count(old)!=1:raise ValueError('Private manager news integration anchor changed: '+old[:60])
        mt=mt.replace(old,new,1)
    manager_change('function feedback(){', "let latestTeamNews=null,latestTeamNewsError=null;\nfunction feedback(){")
    manager_change('usable=FplForecastWindow.check(forecast,official).usable;if(!initialImportHandled)', "usable=FplForecastWindow.check(forecast,official).usable;try{latestTeamNews=await FplTeamNews.load();latestTeamNewsError=null;}catch(e){latestTeamNews=null;latestTeamNewsError=e.message;}if(!FplTeamNews.evaluate({news:latestTeamNews,official,forecast,usable}).aligned)usable=false;if(!initialImportHandled)")
    manager_change("if(!service.url)throw Error(", "if(!FplTeamNews.evaluate({news:latestTeamNews,official,forecast,state,stateValid:stateLegal(state),usable,error:latestTeamNewsError}).aligned)throw Error(latestTeamNewsError||'Nye FPL-meldinger afventer opdateret MM/PM.');\n if(!service.url)throw Error(")
    manager_change("if(d.status==='completed'){const latest=", "if(d.status==='completed'){latestTeamNews=await FplTeamNews.load();if(!FplTeamNews.evaluate({news:latestTeamNews,official,forecast,usable}).aligned)throw Error('Ny spillerstatus: afventer opdateret forecast før forslaget kan bruges.');const latest=")
    manager.write_text(mt)
    for page in out.glob('*.html'):
        source=page.read_text()
        if 'weekly-app.js'not in source and 'classic-manager.js'not in source:continue
        source=source.replace('</head>','<link rel="stylesheet" href="../dashboard-team-news.css?v=1"><script src="../dashboard-team-news.js?v=1"></script></head>')
        source=source.replace('src="weekly-app.js?', 'src="weekly-app.js?team-news=1&').replace('src="weekly-app.js"','src="weekly-app.js?team-news=1"')
        source=source.replace('src="classic-manager.js?', 'src="classic-manager.js?team-news=1&').replace('src="classic-manager.js"','src="classic-manager.js?team-news=1"')
        page.write_text(source)
