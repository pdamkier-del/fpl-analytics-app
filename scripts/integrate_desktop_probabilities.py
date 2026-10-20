"""Integrate validated probability data into the existing desktop app copies."""
from pathlib import Path
import hashlib,json,shutil
from build_existing_b_app import build
ROOT=Path(__file__).resolve().parents[1]

def integrate(root=ROOT):
    root=Path(root);base=root/'app/mm-preview'
    index=json.loads((base/'current/index.json').read_text())
    gk=json.loads((base/'gk/index.json').read_text())
    for name,key in [('forecast.json','forecast_sha256'),('gk-mm.json','mm_sha256'),('evidence.json','evidence_sha256')]:
        if hashlib.sha256((base/'gk'/name).read_bytes()).hexdigest()!=gk[key]:raise ValueError('Unverified probability artifact')
    evidence=json.loads((base/'gk/evidence.json').read_text())
    if not evidence['deterministic_repeat'] or not evidence['stages']['passed'] or not evidence['role_validation']['accepted']:raise ValueError('Probability validation incomplete')
    f=json.loads((base/'gk/forecast.json').read_text())
    if any('distribution'not in x for p in f['players']for w in p['weeks']for x in w['fixtures']):raise ValueError('Missing player probability data')
    index['desktop_probabilities']={'model':f['model'],'forecast_sha256':f['forecast_sha256']}
    (base/'current/index.json').write_text(json.dumps(index,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    out=build(root)
    # Read-only stats views consume the validated GK-v2 forecast. Private plan
    # clients retain their existing locked forecast/identity and storage contract.
    for name in ['classic-catalog.js','forecast-window.js','player.html']:
        path=out/name;text=path.read_text()
        for var in ['f','forecast']:
            text=text.replace(var+".model==='B_locked_PM_preview'","['B_locked_PM_preview','B-GK-role-aware-v2'].includes("+var+'.model)')
            text=text.replace(var+"?.model==='B_locked_PM_preview'","['B_locked_PM_preview','B-GK-role-aware-v2'].includes("+var+'?.model)')
            text=text.replace(var+".model!=='B_locked_PM_preview'","!['B_locked_PM_preview','B-GK-role-aware-v2'].includes("+var+'.model)')
        path.write_text(text)
    for path in out.glob('*.html'):
        text=path.read_text().replace('../existing-app-adapter.js?v=1','../existing-app-adapter.js?v=desktop-probabilities-2')
        text=text.replace('</head>','<link rel="stylesheet" href="../desktop-probabilities.css?v=2"><script src="../gk/contract.js?v=2"></script><script defer src="../desktop-probabilities.js?v=2"></script></head>')
        for asset in ['classic-catalog.js','forecast-window.js']:
            text=text.replace('src="'+asset+'?','src="'+asset+'?desktop-probabilities=2&').replace('src="'+asset+'"','src="'+asset+'?desktop-probabilities=2"')
        path.write_text(text)
    from integrate_dashboard_news import inject
    inject(out)
    from integrate_planner_experience import inject as planner_inject
    planner_inject(out)
    from integrate_transfers_workspace import inject as transfers_inject
    transfers_inject(out)
    from integrate_preview_capacity import inject as capacity_inject
    capacity_inject(out)
    # The same origin already serves earlier app versions. Content-derived
    # queries prevent cached old adapters from hiding newly added history APIs.
    import re
    def version_asset(match,page):
        attr,quote,url=match.groups()
        target=(page.parent/url.split('?')[0].split('#')[0]).resolve()
        if not target.is_file() or target.suffix not in {'.js','.css'}:return match.group(0)
        if not target.is_relative_to(base.resolve()):return match.group(0)
        checksum=hashlib.sha256(target.read_bytes()).hexdigest()[:16]
        return attr+'='+quote+url.split('?')[0]+'?asset='+checksum+quote
    for page in out.glob('*.html'):
        text=page.read_text()
        text=re.sub(r"(src|href)=([\"'])([^\"']+)(?:\2)",lambda m:version_asset(m,page),text)
        page.write_text(text)
    print('Integrated validated probabilities into existing desktop layout:',f['forecast_sha256'])

if __name__=='__main__':integrate()
