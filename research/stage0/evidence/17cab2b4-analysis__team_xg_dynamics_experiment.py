"""Chronological holdout: team xG memory vs adaptive random-walk gain. Research only."""
import io,json,urllib.request
import numpy as np
import pandas as pd
URL="https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/2025-26/gws/merged_gw.csv"
def main():
    with urllib.request.urlopen(URL,timeout=90) as r: raw=r.read()
    f=pd.read_csv(io.BytesIO(raw),low_memory=False)
    required={'fixture','team','opponent_team','was_home','expected_goals','minutes','element','kickoff_time'}
    assert required<=set(f),sorted(required-set(f))
    f['expected_goals']=pd.to_numeric(f.expected_goals,errors='coerce')
    f['minutes']=pd.to_numeric(f.minutes,errors='coerce')
    f=f.dropna(subset=['fixture','team','opponent_team','kickoff_time'])
    f=f[f.minutes.gt(0)].copy()
    grouped=f.groupby(['fixture','team','opponent_team','was_home','kickoff_time'],as_index=False).agg(
        xg=('expected_goals','sum'),n=('element','nunique'),valid=('expected_goals','count'))
    grouped=grouped[(grouped.n>=11)&(grouped.valid==grouped.n)].copy()
    assert len(grouped)>=300,'Insufficient complete team-match xG observations'
    grouped['kickoff_time']=pd.to_datetime(grouped.kickoff_time,utc=True)
    grouped=grouped.sort_values(['kickoff_time','fixture','team'])
    # Fixtures can share kickoff; exclude all same-time observations from updates.
    times=sorted(grouped.kickoff_time.unique())
    cutoff=times[int(len(times)*.65)]
    state={}
    outputs=[]
    for moment,g in grouped.groupby('kickoff_time',sort=True):
        forecasts=[]
        for row in g.itertuples(index=False):
            team=str(row.team);opp=str(row.opponent_team)
            memory=state.get(team,[])
            # Difference from preceding average for that club; no opponent adjustment yet.
            old=np.array(memory,dtype=float)
            baseline=float(old.mean()) if len(old)>=3 else 1.45
            exponential=float(np.average(old,weights=np.power(.85,np.arange(len(old)-1,-1,-1)))) if len(old)>=3 else baseline
            # Adaptive gain from recent volatility; both methods use same inputs.
            if len(old)>=3:
                prev=old[0]
                filtered=prev
                for value in old[1:]:
                    filtered=filtered+.20*(value-filtered)
                recent_var=float(np.var(old[-5:],ddof=1)) if len(old)>=5 else .3
                gain=float(np.clip(.15+.25*recent_var,.12,.55))
                adaptive=float(filtered+gain*(old[-1]-filtered))
            else:adaptive=baseline
            if moment>=cutoff and len(old)>=5:
                forecasts.append((team,opp,float(row.xg),baseline,exponential,adaptive,bool(row.was_home)))
        outputs.extend(forecasts)
        for row in g.itertuples(index=False):state.setdefault(str(row.team),[]).append(float(row.xg))
    assert len(outputs)>=100,'Insufficient holdout observations'
    arr=np.array([o[2:6] for o in outputs])
    y=arr[:,0]
    summary={'source':URL,'limitations':'Raw team xG sums; no opponent/home normalization, calibration on entire series, or locked FPL production baseline. The dynamic estimator is exploratory, not a canonical Kalman filter.',
             'complete_team_match_rows':int(len(grouped)),'holdout_team_matches':len(outputs),'cutoff':str(cutoff),
             'rmse':{k:round(float(np.sqrt(np.mean((arr[:,i]-y)**2))),6) for i,k in [(1,'historical_mean'),(2,'exponential_085'),(3,'adaptive_gain')]},
             'mae':{k:round(float(np.mean(np.abs(arr[:,i]-y))),6) for i,k in [(1,'historical_mean'),(2,'exponential_085'),(3,'adaptive_gain')]}}
    print(json.dumps(summary,indent=2))
    with open('team-xg-dynamics-results.json','w') as out:json.dump(summary,out,indent=2)
if __name__=='__main__':main()
