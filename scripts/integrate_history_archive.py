"""Add historical exploration inside the existing B desktop layout only."""
import re
from pathlib import Path


def inject(out):
    out=Path(out);template=(out/'players-classic.html').read_text()
    # Reuse the existing desktop shell and styles. Its rankings scripts expect
    # rankings controls, so the archive loads only navigation and its own view.
    page=re.sub(r'<script\b[^>]*>[\s\S]*?</script>','',template,flags=re.I)
    main='''<main class="main"><div class="topbar"><div class="crumb">FPL Analytics / Historik</div></div>
<div class="page-head"><div><h1>Historiske stats</h1><p class="archive-caption">Undersøg spilleres og holds tidligere Premier League-kampe. Vælg sæson og klik på et navn for kampstatistik. Aktuelle prognoser findes fortsat på spillerkortet.</p></div></div>
<div class="mode-tabs"><button type="button" class="mode-tab" data-archive-view="players">Spillere</button><button type="button" class="mode-tab" data-archive-view="teams">Hold</button></div>
<div class="archive-controls"><label>Sæson<select id="archive-season" class="select"></select></label><label>Klub<select id="archive-club" class="select"></select></label><label>Søg<input id="archive-search" class="search" placeholder="Spiller eller hold"></label><label>Sortér<select id="archive-sort" class="select"><option value="points">Point</option><option value="minutes">Minutter</option><option value="goals">Mål</option><option value="xg">xG</option></select></label><button id="archive-retry" class="ghost" type="button">Prøv igen</button></div>
<p id="archive-status" role="status">Henter historiske data …</p><p id="archive-count" class="notice"></p><div id="archive-results"></div><section id="archive-detail" aria-live="polite" hidden></section>
<p class="archive-caption">Faktiske FPL-/kampdata. Klubben er spillerens klub i den pågældende kamp. Holdets xG er summen af tilgængelige spiller-xG; manglende tal vises som —. Arkivets dataindsamlingstid dokumenterer ikke, hvad modellen vidste før en gammel deadline.</p></main>'''
    page,count=re.subn(r'<main\b[^>]*>[\s\S]*?</main>',lambda _:main,page,count=1)
    if count!=1:raise ValueError('Existing desktop shell has no main view')
    page=re.sub(r'<title>.*?</title>','<title>Historiske stats · FPL Analytics</title>',page)
    page=page.replace('</head>','<link rel="stylesheet" href="../season-history-explorer.css"></head>')
    page=page.replace('</body>','<script src="classic-nav.js"></script><script src="../season-history-explorer.js"></script></body>')
    (out/'history-classic.html').write_text(page)
    for name in ['players-classic.html','clubs-classic.html']:
        p=out/name;text=p.read_text();view='teams'if name.startswith('clubs')else'players'
        identity=' id="archive-club-link"'if view=='teams'else''
        link='<a'+identity+' class="archive-head-link" href="history-classic.html?view='+view+'">Tidligere sæsoner · spillere og hold</a>'
        text=text.replace('<main class="main">','<main class="main">'+link,1)
        if view=='teams':text=text.replace('</body>','<script src="../season-history-links.js"></script></body>')
        p.write_text(text)
