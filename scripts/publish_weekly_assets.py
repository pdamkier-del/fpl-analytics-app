"""Publish display-only fixture expectations and verified public TC scenarios.
No model input or mathematical operation is changed.
"""
import hashlib,json,shutil,re
from pathlib import Path
import pandas as pd
from collections import Counter
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fpl_v1_1_model.role_classifier import template, canonical
ROOT=Path(__file__).resolve().parents[1]
def version_frontend_assets(app):
    # Version HTML navigation as well: Pages caches documents independently of JS.
    ui_hash=hashlib.sha256()
    for source in sorted(app.glob('*')):
        if source.suffix not in ('.html','.js','.css'):continue
        text=source.read_text()
        if source.suffix=='.html':
            text=re.sub(r'<meta name="fpl-ui-version" content="[^"]*">','',text)
            text=re.sub(r'((?:src|href)="[^"?]+\.(?:js|css))(?:\?[^" ]*)?("\s*)',r'\1\2',text)
        ui_hash.update(source.name.encode());ui_hash.update(text.encode())
    ui_version=ui_hash.hexdigest()[:16]
    # Each published HTML references the exact deployed asset bytes. This avoids
    # a normal reload retaining an older planner UI in the Pages CDN/browser cache.
    for page in ('overview.html','manager-state.html','my-team-classic.html','transfers-classic.html','player.html','players-classic.html','clubs-classic.html'):
        path=app/page
        if not path.is_file():continue
        html=path.read_text()
        def version(match):
            asset=app/match.group(2)
            if not asset.is_file():return match.group(0)
            digest=hashlib.sha256(asset.read_bytes()).hexdigest()[:16]
            return match.group(1)+match.group(2)+'?v='+digest+match.group(3)
        html=re.sub(r'((?:src|href)=")([^"?]+\.(?:js|css))(?:\?[^" ]*)?(")',version,html)
        html=re.sub(r'<meta name="fpl-ui-version" content="[^"]*">','',html)
        html=html.replace('</head>','<meta name="fpl-ui-version" content="'+ui_version+'"></head>')
        path.write_text(html)

def club_lineups(df, forecast):
    """Expose existing frozen MM assignment; never select or re-score players."""
    rows=[]
    for (fixture, team), group in df.groupby(['fixture_uuid','team_id']):
        selected=group[group.xi_selected_map.eq(1)]
        if len(selected)!=11 or selected.fpl_element.nunique()!=11 or group.fpl_element.duplicated().any():
            raise ValueError('Invalid original club XI identity')
        formations=selected.xi_formation.unique()
        if len(formations)!=1:raise ValueError('Inconsistent original XI formation')
        formation=str(formations[0]); layers=[['GK']]+[[canonical(r) for r in layer] for layer in template(formation)]
        if Counter(r for layer in layers for r in layer)!=Counter(selected.xi_assigned_role):
            raise ValueError('Original XI slots do not match original formation')
        if selected.live_eligibility_applied.fillna(False).any():raise ValueError('Unavailable player in original XI')
        if not group.cutoff.eq(forecast['data_asof']).all():raise ValueError('Club XI cutoff mismatch')
        rows.append(dict(fixture_uuid=str(fixture),team_id=int(team),gw=int(group.target_gw.iloc[0]),
            kickoff=str(group.target_kickoff.iloc[0]),formation=formation,layers=layers,
            players=[dict(id=int(r.fpl_element),selected=bool(r.xi_selected_map==1),role=str(r.xi_assigned_role),
                unavailable=bool(r.live_eligibility_applied)) for r in group.itertuples()]))
    return dict(cutoff=forecast['data_asof'],checksums=forecast['checksums'],
        source='original_locked_MM_assignment',locked_model_active=False,fixtures=rows)

def main():
    forecast=json.loads((ROOT/'app/vfinal-diagnostic.json').read_text())
    base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1'
    source=base/'vfinal_live_full_simulator_input.csv.gz'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=forecast['checksums'][source.name]:raise ValueError('Fixture source checksum mismatch')
    df=pd.read_csv(source, usecols=['fpl_fixture_id','target_gw','home_team_id','away_team_id','lambda_home_goals','lambda_away_goals','fixture_uuid','team_id','fpl_element','xi_selected_map','xi_assigned_role','xi_formation','live_eligibility_applied','cutoff','target_kickoff'])
    (ROOT/'app/club-lineups.json').write_text(json.dumps(club_lineups(df,forecast),allow_nan=False)+'\n')
    keys=['fpl_fixture_id','target_gw','home_team_id','away_team_id']
    if df.groupby(keys)[['lambda_home_goals','lambda_away_goals']].nunique().gt(1).any().any():raise ValueError('Inconsistent match goal expectations')
    rows=df.drop_duplicates(keys)[keys+['lambda_home_goals','lambda_away_goals']].rename(columns={'fpl_fixture_id':'id','target_gw':'gw','home_team_id':'home','away_team_id':'away','lambda_home_goals':'home_xg','lambda_away_goals':'away_xg'})
    (ROOT/'app/fixture-expectations.json').write_text(json.dumps(dict(cutoff=forecast['data_asof'],checksums=forecast['checksums'],fixtures=rows.to_dict('records')),allow_nan=False)+'\n')
    tc=ROOT/'work/live-manager-validation/tc_samples.csv.gz'
    if forecast.get('tc_scenarios') and tc.exists():
        if hashlib.sha256(tc.read_bytes()).hexdigest()!=forecast['tc_scenarios']['samples_sha256']:raise ValueError('TC checksum mismatch')
        shutil.copyfile(tc,ROOT/'app/tc-samples.csv.gz')
    version_frontend_assets(ROOT/'app')
if __name__=='__main__':main()
