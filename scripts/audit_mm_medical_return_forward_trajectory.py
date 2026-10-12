#!/usr/bin/env python3
"""Cutoff-safe medical-return trajectory study in archived 2025/26 PL.

Cohorts observed at GW t:
- at t-2 player missed PL game with archived PRE-DEADLINE FPL news
  OUT / DOUBT / MAJOR_DOUBT, but not suspension;
- at t-1 player made confirmed PL start after missing t-2;
- >=2 confirmed starts within t-3..t-6;
- current t team news AVAILABLE or RETURNED_AVAILABLE before t deadline.
Use *only* information <= t-1 to select cohort. Measure realized minutes
and start probability t..t+5 posthoc. No outcomes of future games enter
cohort selection. DGW or unmapped rounds are not assumed zero.

Compare stable 5-straight-start baselines and return-from-available-zero.
Return baseline conditional start minute = average PRE-INJURY 2-4 starts,
not arbitrary 90. Outputs research, never changes locked MM.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl,validate_strict_projection
H=ROOT/'analysis/results/fa-match-importance-20261006-v1/all_features_fa_mi.csv.gz'
N=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2'
OUT=ROOT/'work/live-final-model/mm_medical_return_forward_trajectory.json'
RNG=np.random.default_rng(20261012)

def main():
    h=pd.read_csv(H,usecols=['gw','player_uuid','y','minutes','outcome_known_at'],low_memory=False)
    h['gw']=pd.to_numeric(h.gw,errors='raise').astype(int)
    strict=validate_strict_projection(read_split_gzip_jsonl(N,'predeadline_strict.jsonl.gz'))
    news={(int(v.gw),str(v.player_uuid)):str(v.normalized_availability_state) for v in strict.itertuples()}
    if not all(h.y.isin([0,1])):raise AssertionError('Start flags not binary')
    present={}
    duplicates=0
    for (pid,gw),g in h.groupby(['player_uuid','gw']):
        if len(g)!=1:
            duplicates+=1;continue
        z=g.iloc[0]
        present[(str(pid),int(gw))]=(int(z.y),float(z.minutes))
    medical={'OUT','DOUBT','MAJOR_DOUBT'}
    ready={'AVAILABLE','RETURNED_AVAILABLE'}
    known_pids=set(h.player_uuid.astype(str))
    groups={'medical_recovered':[],'unexplained_recovered':[],'steady_starter':[]}
    for pid in sorted(known_pids):
        # At least two verified FPL-round labels prior to target. No data leakage.
        for origin in range(13,34):
            seq=[present.get((pid,origin-i)) for i in range(1,7)]
            if not all(x is not None for x in seq[:5]):continue
            def started(z):return z is not None and z[0]==1
            def zero(z):return z is not None and z[1]==0
            current_state=news.get((origin,pid),'UNKNOWN')
            prev_state=news.get((origin-2,pid),'UNKNOWN')
            anchor=int(sum(started(z) for z in seq[2:]))
            if started(seq[0]) and zero(seq[1]) and anchor>=2 and current_state in ready:
                if prev_state in medical:
                    kind='medical_recovered'
                elif prev_state in ready:
                    kind='unexplained_recovered'
                else:continue
            elif all(started(z) for z in seq[:5]) and current_state in ready:
                kind='steady_starter'
            else:continue
            # Historical "normal" starter duration before missed match, separated
            # from return-game minutes and from prospective target results.
            before=[z[1] for z in seq[2:6] if started(z)]
            avg_before=float(np.mean(before)) if len(before)>=2 else np.nan
            raw=[present.get((pid,origin+j)) for j in range(6)]
            # Some later weeks may not be observed. Missing != zero.
            groups[kind].append(dict(pid=pid,origin=origin,prior_medical=prev_state,
                                     before_mean=avg_before,returned_minutes=seq[0][1],
                                     trajectory=raw))
    def score(cohorts):
        rows=[]
        for gw_ahead in range(6):
            valid=[v for v in cohorts if v['trajectory'][gw_ahead] is not None]
            if not valid:continue
            y=np.asarray([v['trajectory'][gw_ahead][0] for v in valid],float)
            m=np.asarray([v['trajectory'][gw_ahead][1] for v in valid],float)
            pre=np.asarray([v['before_mean'] for v in valid],float)
            ret=np.asarray([v['returned_minutes'] for v in valid],float)
            n=len(valid)
            # Bootstrap at player level rather than each correlated cohort row:
            # same player can occur several times, so this is only exploratory.
            def ci(z):
                if n<10:return None
                means=z[RNG.integers(0,n,(1000,n))].mean(axis=1)
                return [round(float(w),4) for w in np.quantile(means,[.025,.975])]
            rows.append(dict(steps_after_return=gw_ahead+1,
                n=n,players=len(set(v['pid'] for v in valid)),
                actual_start_fraction=round(float(y.mean()),5),
                start_ci95=ci(y),
                actual_mean_minutes=round(float(m.mean()),3),
                minutes_ci95=ci(m),
                conditional_minutes_given_start=round(float(m[y==1].mean()),3) if (y==1).any() else None,
                prior_healthy_conditional_minutes=round(float(np.nanmean(pre)),3),
                return_game_minutes=round(float(ret.mean()),3),
                pct_started_and_80plus=round(float(np.mean((y==1)&(m>=80))),5),
                pct_available_to_play_unobserved=None))
        return rows
    result=dict(classification='READ_ONLY_2025_26_FPL_MEDICAL_RETURN_6GAME_TRAJECTORY',
       eligibility='Origin classification uses only previous rounds plus strict FPL news at origin; later outcomes are labels only',
       data_counts=dict(historical_rows=len(h),distinct_player_gw=len(present),duplicates_ignored=duplicates,
                        strict_fpl_predeadline_status_rows=len(strict)),
       cohort_counts={k:dict(cohort_origins=len(v),distinct_players=len(set(r['pid'] for r in v))) for k,v in groups.items()},
       trajectory={k:score(v) for k,v in groups.items()},
       data_caveats=['Conditioning on an actual return start defines a selected population, not a guarantee of future starts',
                     'Steady starter is a reference, not a directly exchangeable or causal cohort',
                     'Same 2025/26 used in previous development: not independent model certification',
                     'Player may face cup/international matches between PL events',
                     'GW with missing or multiple fixtures are ignored, not converted to zero'],
       production_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('MM_RETURN_TRAJECTORY_COHORTS',json.dumps(result['cohort_counts'],ensure_ascii=False))
    for key,v in result['trajectory'].items():
        print('MM_RETURN_TRAJECTORY_'+key.upper(),json.dumps(v,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
