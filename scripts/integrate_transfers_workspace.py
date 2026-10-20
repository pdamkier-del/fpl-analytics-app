"""Reshape only the copied B transfer page; production templates are untouched."""
from pathlib import Path
import re
import shutil
ROOT = Path(__file__).resolve().parents[1]

def inject(out):
    for name in ['transfers-workspace.js', 'transfers-workspace.css']:
        if out.parent.resolve() != (ROOT/'app/mm-preview').resolve():
            shutil.copyfile(ROOT/'app/mm-preview'/name, out.parent/name)
    feedback = out/'compute-feedback.js'
    code = feedback.read_text()
    old = "b.textContent=c.busy?"
    if code.count(old) != 1:
        raise ValueError('Compute button label anchor changed')
    feedback.write_text(code.replace(old, "b.textContent=b.hasAttribute('data-latest-plan')&&!c.busy?'Vis nyeste transferplan':c.busy?"))
    page = out/'transfers-classic.html'
    text = page.read_text()
    start = text.index('<section class="pick-head">')
    end = text.index('</div></main>', start)
    text = text[:start] + '''<header class="pick-head transfer-heading"><div class="head-row"><div><div class="workspace-eyebrow">DIN NÆSTE GAMEWEEK <span id="transfer-gw">Seks ugers overblik</span></div><h1>Transfer Planner</h1><p>Din anbefaling, dit hold og dine alternativer — samlet ét sted.</p></div><div class="workspace-actions"><button class="save-btn" data-compute data-latest-plan>Vis nyeste transferplan</button><button class="workspace-secondary" data-open-alternatives>Undersøg alternativer</button></div></div></header><section class="transfer-squad" id="transfer-squad" aria-label="Dit aktuelle hold"><p>Henter dit hold …</p></section><section class="panel transfer-workspace"><div data-compute-feedback class="compute-feedback"></div><p data-compute-status role="status" class="compute-technical"></p><div id="transfer-status" role="status">Henter seneste gemte plan …</div><button id="transfer-retry" class="reset-btn" hidden>Prøv at indlæse igen</button><div id="transfer-content"></div><button type="button" class="workspace-recompute" data-recompute-plan hidden>Beregn planen på ny</button></section><details id="transfer-alternatives" class="transfer-disclosure"><summary><span><strong>Undersøg dine egne alternativer</strong><small>Sammenlign 0, 1 eller 2 transfers uden at ændre dit hold</small></span><span class="disclosure-chevron" aria-hidden="true">⌄</span></summary><div class="disclosure-body"><section id="manual-preview" class="panel"></section></div></details><p class="workspace-footer">Original TS v3 · seks gameweeks · B-preview. Kun anbefalinger — ingen officielle FPL-transfers udføres automatisk.</p>''' + text[end:]
    text, count = re.subn(r'<script src="classic-transfers.js[^\"]*"></script>', '<script src="../transfers-workspace.js"></script>', text)
    if count != 1:
        raise ValueError('Transfer script anchor changed')
    text = text.replace('</head>', '<link rel="stylesheet" href="../transfers-workspace.css"></head>')
    page.write_text(text)
