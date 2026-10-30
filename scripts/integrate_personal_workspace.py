"""Personal-first navigation/dashboard in B copies; original app/model untouched."""
def inject(out):
    weekly=out/'weekly-app.js';text=weekly.read_text()
    if 'FplDashboardContext'not in text:
        marker='function showError(e){'
        if marker not in text:raise ValueError('Dashboard context anchor changed')
        text=text.replace(marker,"window.FplDashboardContext=()=>({forecast,official,fixtures,state,plan,usable,selection:savedSelection()});\n"+marker,1);weekly.write_text(text)
    assets='<link rel="stylesheet" href="../dashboard-workspace.css"><script src="../history-archive.js"></script><script src="../history-refresh-client.js"></script><script src="../history-refresh-card.js"></script><script defer src="../dashboard-workspace.js"></script><link rel="stylesheet" href="../model-explainer.css"><script defer src="../model-explainer.js"></script>'
    for page in out.glob('*.html'):
        text=page.read_text()
        if 'dashboard-workspace.js'not in text:page.write_text(text.replace('</head>',assets+'</head>'))
