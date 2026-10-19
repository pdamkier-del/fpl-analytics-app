"""Past-only uncertainty for one available, established goalkeeper.

Competing established keepers retain B's existing probabilities. Registration
alone is not evidence of a competitive role. This is preview-only.
"""
from pathlib import Path
import gzip,json
import numpy as np
import pandas as pd
from scipy.stats import beta as beta_distribution


def verified_squads(root):
    root=Path(root)
    old=pd.read_csv(root/'work/current-B-role-training/verified_observations.csv.gz',low_memory=False)
    old=old[old.pos.eq('GK')][['season','fixture_uuid','team_id','player_uuid','kickoff_at','known_at','started','confirmed_squad']].copy()
    live_path=root/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz'
    if live_path.exists():
        live=pd.read_csv(live_path,low_memory=False);live=live[live.fpl_position.eq('GK')].copy()
        live['known_at']=live.available_at;live['confirmed_squad']=live.minutes.gt(0)|live.started.eq(1)
        # Link actual confirmed benches by player and exact kickoff, not names.
        matches={}
        with gzip.open(root/'work/live-final-model/match_actuals.jsonl.gz','rt')as stream:
            for line in stream:
                m=json.loads(line)
                if m['tournament']=='prem':matches[m['match_id']]=pd.Timestamp(m['kickoff_time'])
        lineup=pd.read_csv(root/'data_v1_1/raw/all-competitions-2026-27/lineups.csv',low_memory=False)
        keys={(r.player_uuid,matches[r.match_id])for r in lineup.itertuples()if r.match_id in matches and r.lineup_status=='confirmed'}
        live['confirmed_squad']|=np.array([(r.player_uuid,pd.Timestamp(r.kickoff_at))in keys for r in live.itertuples()],dtype=bool)
        old=pd.concat([old,live[old.columns]],ignore_index=True)
        # A recently selected unlisted keeper blocks a false sole-candidate
        # claim. Keep its provider identity internal; never invent a FPL ID.
        extras=[]
        details=root/'data_v1_1/raw/live-captures'
        for capture in sorted(details.glob('*/fotmob/details/*.json'),reverse=True):
            mid=capture.stem
            match='26-27-prem-'+mid
            if match not in matches:continue
            raw=json.loads(capture.read_text());lineups=raw.get('content',{}).get('lineup')or{}
            kickoff=matches[match]
            for side in ['home','away']:
                team=lineups.get(side+'Team')or{}
                selected=list(team.get('starters',[]))+list(team.get('subs',[]))
                known=live[pd.to_datetime(live.kickoff_at,utc=True,format='mixed').eq(kickoff)]
                # Provider/FPL IDs are linked through an already mapped keeper.
                linked=lineup[(lineup.match_id.eq(match))&lineup.team_side.eq(side)]
                linked_keepers=known[known.player_uuid.isin(linked.player_uuid)]
                if linked_keepers.team_id.nunique()!=1:continue
                tid=int(linked_keepers.team_id.iloc[0]);mapped=set(linked.provider_player_id.dropna().astype(int))
                provider_starters=[p for p in team.get('starters',[])if p.get('usualPlayingPositionId')==0]
                team_observed=known[known.team_id.eq(tid)]
                if len(provider_starters)==1 and team_observed.started.eq(1).sum()==1:mapped.add(provider_starters[0]['id'])
                for p in selected:
                    if p.get('usualPlayingPositionId')!=0 or p.get('id')in mapped:continue
                    extras.append(dict(season='2026-27',fixture_uuid='provider-'+mid,team_id=tid,player_uuid='unlisted-provider:'+str(p['id']),kickoff_at=kickoff.isoformat(),known_at=(kickoff+pd.Timedelta(hours=4)).isoformat(),started=int(p in team.get('starters',[])),confirmed_squad=True))
        if extras:old=pd.concat([old,pd.DataFrame(extras)],ignore_index=True)
    old['clock']=pd.to_datetime(old.known_at,utc=True,format='mixed')
    old['kick']=pd.to_datetime(old.kickoff_at,utc=True,format='mixed')
    return old.drop_duplicates(['season','team_id','player_uuid','kick'])


class SoloRolePolicy:
    def __init__(self,history,squads):
        self.squads=squads.copy()
        if 'clock'not in self.squads:self.squads['clock']=pd.to_datetime(self.squads.known_at,utc=True,format='mixed')
        if 'kick'not in self.squads:self.squads['kick']=pd.to_datetime(self.squads.kickoff_at,utc=True,format='mixed')
        self.teams={(str(s),str(int(t))):g for(s,t),g in self.squads.groupby(['season','team_id'])}
        self.context_cache={}
        train=history[history.season.eq('2024-25')&history.pos.eq('GK')]
        outcomes=[];solo=[];label_clocks=[]
        for (_,_,team),g in train.groupby(['season','fixture_uuid','team_id']):
            if g.y.sum()!=1 or ((g.y>0)&g.availability_cap.eq(0)).any():continue
            context=self.context('2024-25',team,g,g.cutoff.iloc[0])
            if not context['ready']:continue
            candidate=set(context['available_known'])
            if not candidate:continue
            winner=str(g.loc[g.y.eq(1),'player_uuid'].iloc[0]);outside=winner not in candidate
            outcomes.append(outside)
            if len(candidate)==1:
                pid=next(iter(candidate));candidate_rows=g[g.player_uuid.eq(pid)]
                if len(candidate_rows)==1:
                    row=candidate_rows.iloc[0]
                    if row.availability_cap==1 and row.news_state in ('AVAILABLE','RETURNED_AVAILABLE'):solo.append(outside)
            label_clocks.extend(pd.to_datetime(g.known_at,utc=True,format='mixed'))
        if len(outcomes)<100 or not solo:raise ValueError('Insufficient historical verified goalkeeper role evidence')
        # Jeffreys smoothing avoids a zero novelty risk. Borrow the project's
        # existing strength-five shrinkage, without a parameter search.
        global_rate=(sum(outcomes)+.5)/(len(outcomes)+1)
        self.alpha=sum(solo)+5*global_rate
        self.beta=len(solo)-sum(solo)+5*(1-global_rate)
        self.risk=float(self.alpha/(self.alpha+self.beta))
        self.last_training_label=max(label_clocks)
        self.receipt=dict(training_season='2024-25',global_contexts=len(outcomes),global_new_role_starts=int(sum(outcomes)),global_rate=global_rate,
            sole_contexts=len(solo),sole_new_role_starts=int(sum(solo)),shrinkage_strength=5,predictive_other_start_probability=self.risk,
            other_risk_credible90=[float(beta_distribution.ppf(.05,self.alpha,self.beta)),float(beta_distribution.ppf(.95,self.alpha,self.beta))],
            last_training_label_known_at=self.last_training_label.isoformat(),
            interval_scope='Conditional empirical-Bayes posterior; excludes uncertainty in the population-rate estimate.',limitation='Sparse sole-candidate cohort; posterior uncertainty is not independent calibration certification.')

    def context(self,season,team,rows,cutoff):
        cut=pd.Timestamp(cutoff);key=(str(season),str(int(team)),str(cut))
        if key not in self.context_cache:
            obs=self.teams.get((str(season),str(int(team))))
            past=obs[obs.clock.lt(cut)&obs.kick.ge(cut-pd.Timedelta(days=90))]if obs is not None else pd.DataFrame()
            if past.empty:base=dict(ready=False,reason='no_prior_verified_squads',known=[],fixtures=0)
            else:
                kicks=past.kick.drop_duplicates().sort_values().tail(5)
                recent=past[past.kick.isin(kicks)]
                selected=recent[recent.confirmed_squad.eq(True)]
                counts=selected.groupby('kick').size()
                ready=len(kicks)>=3 and len(counts)==len(kicks)and bool(counts.ge(2).all())
                # A returning former starter remains a real competitor even
                # after missing all five recent squads.
                known=set(selected.player_uuid)|set(past[past.started.eq(1)].player_uuid)
                base=dict(ready=ready,reason='verified_recent_squads'if ready else'insufficient_complete_squads',known=sorted(known),fixtures=len(kicks),
                    max_squad_known_at=past.clock.max().isoformat())
            self.context_cache[key]=base
        answer=dict(self.context_cache[key]);by=rows.set_index('player_uuid')
        # Missing from the forecast catalogue does not prove unavailability.
        def possibly_available(pid):
            if pid not in by.index:return True
            cap=float(by.loc[pid].get('availability_cap',np.nan))
            return not np.isfinite(cap)or cap>0
        answer['available_known']=[p for p in answer['known']if possibly_available(p)]
        return answer

    def allocate(self,season,team,rows,cutoff,weights,missing):
        cut=pd.Timestamp(cutoff)
        if self.last_training_label>=cut:raise ValueError('Future goalkeeper role training label')
        context=self.context(season,team,rows,cut)
        context['applied']=False
        if not context['ready']or len(context['available_known'])!=1:return weights,missing,context
        pid=context['available_known'][0];by=rows.set_index('player_uuid')
        cap=float(by.loc[pid].get('availability_cap',np.nan))if pid in by.index else np.nan
        state=str(by.loc[pid].get('verified_news_state',by.loc[pid].get('news_state','UNKNOWN')))if pid in by.index else'UNKNOWN'
        if pid not in weights or not np.isfinite(cap)or cap<1 or state not in ('AVAILABLE','RETURNED_AVAILABLE')or weights[pid]<=0:
            context['reason']='sole_candidate_not_fully_available';return weights,missing,context
        outside=sum(v for p,v in weights.items()if p!=pid)+missing
        revised={p:((1-self.risk)if p==pid else self.risk*v/outside if outside>0 else 0.)for p,v in weights.items()}
        pool=self.risk*missing/outside if outside>0 else self.risk
        context.update(applied=True,sole_candidate=pid,reason='one_fully_available_established_keeper',other_start_probability=self.risk)
        if not np.isclose(sum(revised.values())+pool,1,atol=1e-10):raise ValueError('Role allocation is not exclusive')
        return revised,pool,context


def load_policy(root,history=None):
    root=Path(root)
    if history is None:history=pd.read_csv(root/'work/current-B-inputs/history.csv.gz',low_memory=False)
    return SoloRolePolicy(history,verified_squads(root))


def mark_horizon_absences(predicted,bootstrap):
    """Carry explicit season-long loan exclusions through all forecast GWs."""
    import re
    unavailable={p['id']for p in bootstrap['elements']if p['element_type']==1 and p['status']=='u'and 'loan'in p.get('news','').lower()and re.search(r'(rest|remainder|end).{0,20}season|season.long',p.get('news',''),re.I)}
    result=predicted.copy()
    result['role_horizon_absence']=result.pos.eq('GK')&result.fpl_element.isin(unavailable)
    return result
