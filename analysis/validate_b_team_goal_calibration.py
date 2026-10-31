"""Fixed prefix-only G/xG shrinkage diagnostic; no live model activation."""
import argparse,gzip,json,sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import gammaln
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/results/integrated-repair-20261031/team-goals'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
        teams=pd.read_sql_query("SELECT * FROM team_fixture_observations WHERE season IN ('2024-25','2025-26')",db)
        schedules=pd.read_sql_query("SELECT f.season,s.kickoff_at,s.observed_at FROM fixture_schedule_snapshots s JOIN fixtures f USING(fixture_uuid) WHERE f.season IN ('2024-25','2025-26')",db)
    actual=teams[teams.source_name.eq('football_data_co_uk')].set_index(['season','fixture_uuid','team_id']);xg=teams[teams.source_name.eq('vaastav_historical_core')].copy();xg['known']=pd.to_datetime(xg.kickoff_at,utc=True)+pd.to_timedelta(np.where(xg.season.eq('2025-26'),3,4),unit='h')
    if xg.duplicated(['season','fixture_uuid','team_id']).any()or actual.index.duplicated().any():raise ValueError('Duplicate authoritative team outcome')
    records={}
    for season in ['2024-25','2025-26']:
        for line in gzip.open(ROOT/f'analysis/results/general-conversion-20261020/{season}_prepared.jsonl.gz','rt'):
            r=json.loads(line);records[season,r['core_fixture']]=r
    ap=argparse.ArgumentParser();ap.add_argument('--tasks',type=Path);args=ap.parse_args()
    if args.tasks:tasks=json.load(gzip.open(args.tasks,'rt'))
    else:
        from test_separated_goal_head import prepare_tasks
        tasks,_=prepare_tasks(json.loads((ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json').read_text()),OUT)
    rows=[]
    for season,fx,_,inp,*_ in tasks:
        cut=pd.Timestamp(records[season,fx]['cutoff'])
        for side in ['home','away']:
            team=int(inp[side+'_team']);y=actual.loc[season,fx,team];past=xg[xg.season.eq(season)&xg.team_id.eq(team)&xg.known.lt(cut)].copy()
            # Actual score includes own goals; xG source never supplies authoritative gf.
            past['authoritative_gf']=[actual.loc[(season,r.fixture_uuid,team),'gf']if (season,r.fixture_uuid,team)in actual.index else np.nan for r in past.itertuples()]
            usable=past.xg.notna()&past.authoritative_gf.notna();past=past[usable]
            if past.empty:raise ValueError('No prior G/xG observations')
            # Fixed 14 xG prior at conversion ratio one; no tuning on evaluation weeks.
            factor=(past.authoritative_gf.sum()+14)/(past.xg.sum()+14);base=float(inp['lambda_'+side+'_goals']);target_xg=xg[(xg.season.eq(season))&xg.fixture_uuid.eq(fx)&xg.team_id.eq(team)].xg.iloc[0]
            for arm,mean in [('frozen',base),('G_xG_shrinkage14',base*factor)]:rows.append(dict(season=season,fixture_uuid=fx,team_id=team,arm=arm,mean=mean,goals=int(y.gf),actual_xg=target_xg,prior_matches=len(past),last_known_at=str(past.known.max()),cutoff=str(cut)))
    frame=pd.DataFrame(rows);metrics=[]
    for(season,arm),g in frame.groupby(['season','arm']):
        metrics.append(dict(season=season,arm=arm,team_fixtures=len(g),goal_MAE=float(abs(g['mean']-g.goals).mean()),goal_RMSE=float(np.sqrt(((g['mean']-g.goals)**2).mean())),goal_bias=float((g['mean']-g.goals).mean()),poisson_NLL=float((g['mean']-g.goals*np.log(g['mean'])+gammaln(g.goals+1)).mean()),mean_xg=float(g.actual_xg.mean()),mean_goals=float(g.goals.mean()),mean_forecast=float(g['mean'].mean())))
    observed=pd.to_datetime(schedules.observed_at,utc=True);kick=pd.to_datetime(schedules.kickoff_at,utc=True);valid=int((observed<kick).sum())
    result=dict(metrics=metrics,candidate='Fixed 14-xG shrinkage of prior same-season team G/xG, multiplicative attack correction to existing team means',activation=False,limitations=['Reused GW22-38 research periods; historical +3/4h proxies','Team G includes own goals, xG does not','No new full individual PM candidate activated without joint scoring gate'],upcoming_rotation=dict(historical_PL_schedule_rows=len(schedules),recorded_before_kickoff=valid,nonPL_upcoming_calendar='Not Available: recovered finished-match observations do not prove predeadline schedule knowledge',decision='Keep future-opponent/relative-importance effect neutral; do not train on retrospective calendar'))
    frame.to_csv(OUT/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0});(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
