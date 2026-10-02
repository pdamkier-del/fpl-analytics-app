#!/usr/bin/env python3
"""Build audited observed workload from Core PL + source cup/Europe minutes.

FA Cup is absent from the frozen source and explicitly flagged as missing.
Never relabel this observed subset as complete all-competition coverage.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from fpl_v1_1_model.workload import WorkloadHistory
from build_reproducible_role_benchmark import write_json, write_prediction_csv, sha


def build_ledger(con, raw, classified):
    def read(name):
        return pd.concat([pd.read_csv(p) for p in sorted(raw.glob('GW*/'+name+'.csv'))], ignore_index=True)
    matches, lines, stats = read('matches'), read('lineups'), read('playermatchstats')
    assert not matches.match_id.duplicated().any()
    assert not stats.duplicated(['match_id','player_id']).any()
    mapping = {int(k):v for k,v in con.execute("SELECT external_id,player_uuid FROM player_id_mapping WHERE season='2025-26' AND id_namespace='fpl_element'")}
    # European lineups often omit FPL IDs although player-stats carry them.
    # Recover only exact, unique (club-code, display-name) aliases witnessed in
    # PL lineups. No fuzzy surname matching and no cross-club name matching.
    # This is retrospective stable identity resolution, not an outcome feature.
    anchors=lines[lines.match_id.str.contains('-prem-') & lines.player_id.notna()]
    aliases={key:set(g.player_id.astype(int)) for key,g in anchors.groupby(['team_code','player_name'])}
    identity=[]
    for index,r in lines[lines.player_id.isna() & lines.team_code.notna()].iterrows():
        choices=aliases.get((r.team_code,r.player_name),set())
        if len(choices)==1:
            pid=next(iter(choices));lines.loc[index,'player_id']=pid
            identity.append({'match_id':r.match_id,'team_code':r.team_code,'player_name':r.player_name,'resolved_fpl_id':pid,'rule':'unique exact club-code/name alias from PL; retrospective identity only'})
    lines['player_uuid'] = lines.player_id.map(mapping)
    # Infer source club-code -> Core season team ID only from verified PL slots.
    aligned = lines.merge(classified[['match_id','player_uuid','team_id']].drop_duplicates(), on=['match_id','player_uuid'])
    pairs = aligned[['team_code','team_id']].dropna().drop_duplicates()
    assert not pairs.team_code.duplicated().any() and pairs.team_id.nunique()==20
    team_map = {int(r.team_code):int(r.team_id) for r in pairs.itertuples()}
    core = pd.read_sql_query("SELECT fixture_uuid,player_uuid,team_id,kickoff_at,started,minutes FROM player_fixture_observations WHERE season='2025-26' AND is_final=1",con)
    ids = classified[['match_id','fixture_uuid']].drop_duplicates()
    pl = core.merge(ids,on='fixture_uuid',validate='many_to_one')
    assert len(pl)==len(core), 'Core fixtures not mapped'
    history = WorkloadHistory(); ledger=[]; coverage=[]; excluded=[]
    for (mid,team), group in pl.groupby(['match_id','team_id']):
        players = {r.player_uuid:{'minutes':float(r.minutes),'started':bool(r.started)} for r in group.itertuples()}
        ko=pd.to_datetime(group.kickoff_at.iloc[0],utc=True); known=ko+pd.Timedelta(hours=3)
        history.add_game(team,mid,ko,known,'prem',players,True)
        coverage.append({'match_id':mid,'team_id':team,'competition':'prem','kickoff':ko.isoformat(),'available_at':known.isoformat(),'mapped_players':len(players),'complete_player_stats':True,'source':'Historical Core'})
        for pid,v in players.items(): ledger.append({'match_id':mid,'team_id':team,'player_uuid':pid,'kickoff':ko.isoformat(),'available_at':known.isoformat(),'competition':'prem',**v})
    pl_history=deepcopy(history)
    stats_groups={mid:g for mid,g in stats.groupby('match_id')}
    for m in matches.loc[matches.tournament!='prem'].itertuples():
        if str(m.finished).lower()!='true':
            excluded.append({'match_id':m.match_id,'reason':'not finished'}); continue
        if pd.isna(pd.to_datetime(m.kickoff_time,utc=True,errors='coerce')):
            excluded.append({'match_id':m.match_id,'reason':'missing kickoff: cannot establish cutoff availability'});continue
        sl=lines[lines.match_id==m.match_id]
        sg=stats_groups.get(m.match_id,pd.DataFrame(columns=stats.columns))
        lookup={int(r.player_id):r for r in sg.itertuples()}
        for side in ('home','away'):
            g=sl[sl.team_side==side]
            codes=g.team_code.dropna().unique()
            if len(codes)==0:
                fallback=getattr(m,side+'_team')
                if pd.notna(fallback):codes=np.array([fallback])
            if len(codes)!=1 or int(codes[0]) not in team_map:
                excluded.append({'match_id':m.match_id,'team_side':side,'reason':'non-PL or unresolved team'});continue
            team=team_map[int(codes[0])];players={}; missing_positive=0;missing_ids=0
            for r in g.itertuples():
                if pd.isna(r.player_id) or pd.isna(r.player_uuid):
                    missing_ids+=1;continue
                s=lookup.get(int(r.player_id));start=str(r.is_starting).lower()=='true'
                if s is None or pd.isna(s.minutes_played):
                    missing_positive += int(start);continue
                minutes=float(s.minutes_played)
                if not np.isfinite(minutes) or not 0<=minutes<=120:
                    raise ValueError('Invalid source workload minutes '+m.match_id)
                players[r.player_uuid]={'minutes':minutes,'started':start}
            ko=pd.to_datetime(m.kickoff_time,utc=True);known=ko+pd.Timedelta(hours=3)
            # Strong completeness claim is limited to mapped starting XI, not
            # an independent tournament-fixture inventory or all academy IDs.
            complete=missing_positive==0 and sum(v['started'] for v in players.values())==11
            history.add_game(team,m.match_id,ko,known,m.tournament,players,complete)
            coverage.append({'match_id':m.match_id,'team_id':team,'competition':m.tournament,'kickoff':ko.isoformat(),'available_at':known.isoformat(),'mapped_players':len(players),'complete_player_stats':complete,'unmapped_lineup_players':missing_ids,'missing_starter_stats':missing_positive,'source':'FPL-Core-Insights snapshot'})
            for pid,v in players.items():ledger.append({'match_id':m.match_id,'team_id':team,'player_uuid':pid,'kickoff':ko.isoformat(),'available_at':known.isoformat(),'competition':m.tournament,**v})
    return history,pl_history,pd.DataFrame(ledger),pd.DataFrame(coverage),pd.DataFrame(excluded),matches,pd.DataFrame(identity)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',required=True)
    ap.add_argument('--out',default=str(ROOT/'analysis/results/workload-v1'))
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    raw=ROOT/'data_v1_1/raw/all-competitions-2025-26'
    con=sqlite3.connect(f'file:{Path(a.db).resolve()}?mode=ro',uri=True)
    classified=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv')
    history,pl_history,ledger,coverage,excluded,matches,identity=build_ledger(con,raw,classified)
    features_path=ROOT/'analysis/results/reproducible-role-v1/all_feature_predictions.csv.gz'
    frame=pd.read_csv(features_path)
    deadlines=pd.read_csv(raw/'gameweek_summaries.csv')
    assert not deadlines.id.duplicated().any()
    cutoff_map={int(r.id):pd.to_datetime(r.deadline_time,utc=True) for r in deadlines.itertuples()}
    cache={};rows=[]
    for r in frame.itertuples():
        cutoff=cutoff_map[r.gw]
        assert cutoff==pd.to_datetime(r.cutoff,utc=True), 'Rebuild role features using supplied authoritative deadlines'
        key=(int(r.team_id),r.gw)
        if key not in cache:cache[key]=(history.state(r.team_id,cutoff),pl_history.state(r.team_id,cutoff))
        (state,default,known),(pl_state,pl_default,pl_known)=cache[key]
        record=state.get(r.player_uuid,default).copy()
        record.update({'pl_only_'+k:v for k,v in pl_state.get(r.player_uuid,pl_default).items()})
        record['work_max_history_known_at']=known.isoformat() if known else ''
        record['work_all_competitions_complete']=False
        assert known is None or known<cutoff
        rows.append(record)
    frame=pd.concat([frame,pd.DataFrame(rows)],axis=1)
    write_prediction_csv(frame,out/'all_features.csv.gz')
    ledger.sort_values(['kickoff','match_id','team_id','player_uuid']).to_csv(out/'official_player_minutes.csv',index=False)
    coverage.sort_values(['kickoff','match_id','team_id']).to_csv(out/'team_match_coverage.csv',index=False)
    excluded.to_csv(out/'excluded_team_sides.csv',index=False)
    identity.to_csv(out/'exact_identity_resolutions.csv',index=False)
    deadlines[['id','deadline_time']].rename(columns={'id':'gw','deadline_time':'cutoff'}).sort_values('gw').to_csv(out/'authoritative_deadlines.csv',index=False)
    audit={'source_matches_by_competition':matches.groupby('tournament').match_id.nunique().astype(int).to_dict(),
      'team_matches_by_competition':coverage.groupby('competition').size().astype(int).to_dict(),
      'incomplete_team_stat_records':int((~coverage.complete_player_stats).sum()),
      'exact_identity_resolutions':len(identity),
      'excluded_match_reasons':excluded.groupby('reason').size().astype(int).to_dict(),
      'feature_rows':len(frame),'all_competitions_complete':False,
      'missing_competitions':['FA Cup'],
      'other_gaps':'No independent complete fixture inventory; source is limited to FPL-mapped PL club players. Internationals and pre-season excluded. Transfers only count workload at the current team.',
      'availability':'kickoff+3h reconstruction proxy, not ingestion-certified',
      'deadlines':'All 38 source FPL deadlines available; GW6-38 exactly match the earlier proxies. This does not certify cohort/schedule ingestion.'}
    write_json(out/'coverage_audit.json',audit)
    code=[Path(__file__),ROOT/'src/fpl_v1_1_model/workload.py']
    inputs=[Path(a.db).resolve(),features_path,*sorted(raw.rglob('*.csv')),raw/'SOURCE_MANIFEST.json']
    write_json(out/'manifest.json',{'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
      'code':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in code],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json' and not p.name.endswith('.tmp')]})
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
