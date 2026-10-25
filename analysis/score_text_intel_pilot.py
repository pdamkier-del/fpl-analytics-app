"""Frozen, preselected 40-case text pilot. No active model caller."""
from pathlib import Path
import json,hashlib,base64,gzip
import numpy as np
import pandas as pd
from datetime import datetime,timezone
from individual_mm_evidence import load_frame
from research_europe_rotation import source_frames
from research_individual_mm_refinement import project
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/text-intel-pilot-20261025';ARCHIVE=OUT/'source-archives'
KEY=['season','fixture_uuid','player_uuid']

def metric(g,p='p',x='x'):
    if not len(g):return {'rows':0}
    a=np.clip(g[p].to_numpy(float),1e-9,1-1e-9);y=g.y.to_numpy(float)
    return dict(rows=len(g),start_brier=float(np.mean((g[p]-g.y)**2)),start_log_loss=float(np.mean(-y*np.log(a)-(1-y)*np.log(1-a))),minute_mae=float(np.mean(abs(g[x]-g.minutes))),minute_bias=float(np.mean(g[x]-g.minutes)),start_bias=float(np.mean(g[p]-g.y)))

def main():
    raw=(OUT/'case-selection.json').read_bytes();lock=json.loads((OUT/'selection-lock.json').read_text());assert hashlib.sha256(raw).hexdigest()==lock['case_selection_sha256']
    cases=pd.DataFrame(json.loads(raw)['cases']);receipts={r['key']:r for r in json.loads((OUT/'archive-receipts.json').read_text())}
    for c in cases.itertuples():
        at=datetime.strptime(c.archive_timestamp,'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc);assert at<pd.Timestamp(c.cutoff).to_pydatetime()
        k='archive-picks'if 'scout-picks-'in c.source_url else 'archive-news';body=gzip.decompress((ARCHIVE/(k+'.html.gz')).read_bytes())
        assert hashlib.sha256(body).hexdigest()==c.source_sha256
        assert base64.b32encode(hashlib.sha1(body).digest()).decode().rstrip('=')==c.archive_digest_sha1_base32
    # Outcomes and numerical predictions are opened only after the frozen case lock.
    f,_,_=source_frames();f=f[f.season.eq('2025-26')&f.gw.eq(22)].copy().reset_index(drop=True)
    cases=cases.merge(f[['player_uuid','fixture_uuid','team_id']],on=['player_uuid','team_id'],how='left',validate='one_to_one')
    missing=cases[cases.fixture_uuid.isna()];eligible=cases[cases.fixture_uuid.notna()].copy();c=f.copy();changed=set();altered=[]
    for r in eligible.itertuples():
        if r.candidate_action!='hard_unavailable':continue
        mask=c.player_uuid.eq(r.player_uuid)&c.fixture_uuid.eq(r.fixture_uuid)
        if len(c.loc[mask])!=1:raise ValueError('Missing target player fixture')
        if (c.loc[mask,'p']+c.loc[mask,'q']).iloc[0]>1e-12:
            c.loc[mask,'news_eligible']=True;c.loc[mask,'news_state']='OUT';c.loc[mask,'news_chance']=0.;changed.add((r.fixture_uuid,r.team_id));altered.append(r.case_id)
    if changed:
        mask=np.array([(fx,t)in changed for fx,t in zip(c.fixture_uuid,c.team_id)])
        update=project(c.loc[mask].copy());c.loc[mask,['p','q','x']]=update[['p','q','x']].to_numpy()
    paired=eligible.merge(f[KEY+['p','q','x','y','minutes']],on=KEY,validate='one_to_one').merge(c[KEY+['p','q','x']].rename(columns={'p':'candidate_p','q':'candidate_q','x':'candidate_x'}),on=KEY,validate='one_to_one')
    result=dict(cases_locked=40,cases_scored=len(paired),missing_forecast_cases=missing[['case_id','name','team_id']].to_dict('records'),selection_sha256=lock['case_selection_sha256'],archived_body_and_clock_verified=True,scope='Upstream frozen B MM. Fixed explicit-unavailability intervention only; soft role/praise/return text does not become an invented p boost.',metrics={'selected':{'baseline':metric(paired),'candidate':metric(paired,'candidate_p','candidate_x')},'whole_origin_roster':{'baseline':metric(f),'candidate':metric(c)}},categories={},hard_unavailability_rows_changed=altered,active_model_changed=False,production_changed=False,final_role_PM_xP_scored=False,promotion_allowed=False)
    for name,g in paired.groupby('category'):result['categories'][name]={'baseline':metric(g),'candidate':metric(g,'candidate_p','candidate_x'),'actual_starts':int(g.y.sum()),'actual_nonstarts':int((1-g.y).sum())}
    whole=f[KEY+['team_id','p','q','x','y','minutes']].copy();whole['candidate_p']=c.p.to_numpy();whole['candidate_q']=c.q.to_numpy();whole['candidate_x']=c.x.to_numpy();whole.to_csv(OUT/'whole-origin-predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    unaffected=whole[[not ((fx,t)in changed)for fx,t in zip(whole.fixture_uuid,whole.team_id)]]
    result['unaffected_teams_identical']=bool(np.max(abs(unaffected.p-unaffected.candidate_p))<1e-12 and np.max(abs(unaffected.x-unaffected.candidate_x))<1e-12)
    result['team_start_mass_max_error']=float(np.max(abs(c.groupby(['fixture_uuid','team_id']).p.sum()-11)))
    result['case_club_count']=int(paired.team_id.nunique())
    paired.to_csv(OUT/'paired-predictions.csv',index=False)
    (OUT/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
