#!/usr/bin/env python3
"""Isolated club-priority research. No production MM/PM/TS execution.

Observed normal-player usage is a response; the current XI is NEVER a feature.
All source clocks remain explicitly uncertified where only +4h proxies exist.
"""
from pathlib import Path
from collections import defaultdict
import hashlib,json,sqlite3,re,inspect
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.metrics import brier_score_loss,log_loss
from analyze_mm_competition_rotation import load24,team_games,jl,RAW24,save_json
from experimental_mm_role_profiles import infer_player_roles

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/mm-club-importance-20261016'
SELECTION='role_chance_return_duration'
VARIANTS=['control','A_objective','B_global_history','B_club_history','C_combined','D_dynamic','D_individual']
OUTCOMES={'normal_share':(0,1),'xi_changes':(0,11),'normal_minute_share':(0,1)}
ROLE_DEFAULTS={k:v.default for k,v in inspect.signature(infer_player_roles).parameters.items()}


def prior_role(events,cutoff):
    """Reuse existing start/duration priors, allowing unknown bench minutes.

    Unknown minutes never become zero, and missing/absent players never count
    as tactical bench evidence. Only historical named matchday selections enter.
    """
    e=[v for v in events if known_before(v['known_at'],cutoff)]
    w=np.array([2**(-(cutoff-v['known_at']).total_seconds()/86400/ROLE_DEFAULTS['half_life_days'])for v in e])
    starts=np.array([v['started']for v in e],bool)
    weight=w.sum();sw=w[starts].sum()
    prior=ROLE_DEFAULTS['prior_exposure'];dp=ROLE_DEFAULTS['duration_exposure']
    known=[(v,float(ww))for v,ww in zip(e,w)if v['started']and pd.notna(v['minutes'])]
    return dict(p=(ROLE_DEFAULTS['start_prior']*prior+sw)/(prior+weight),
        duration=(ROLE_DEFAULTS['starter_minutes_prior']*dp+sum(v['minutes']*ww for v,ww in known))/(dp+sum(ww for v,ww in known)),exposure=weight,existing=False)


def known_before(clock,cutoff):
    return pd.notna(clock) and pd.Timestamp(clock)<pd.Timestamp(cutoff)


def phase(comp,stage):
    if comp=='Premier League':return 'league'
    if stage in ['final','1/2','1/4','1/8']:return comp+':'+stage
    return comp+':recorded_round_'+str(stage)


def smoothed_usage(history,comp,default):
    """Raw histories supplied as features. Shrinkage is learned by Ridge, not a score rule."""
    values=[r['normal_share']for r in history if r['competition']==comp]
    return (float(np.mean(values))if values else default,len(values),float(np.mean(values[-3:]))if values else default)


def select_normal(profiles):
    # No named/manual stars: pre-existing or empirical role * conditional duration.
    return sorted(profiles,key=lambda k:(-profiles[k]['p']*profiles[k]['duration'],k))[:11]


def build_samples(players,games,snapshots,core,news):
    """Sequential match features first; outcomes are appended only afterwards.

    Historical named bench selection is evidence of matchday availability, not
    proof of medical clearance. Missing players never become tactical negatives.
    """
    p=players.copy();p['kickoff']=pd.to_datetime(p.kickoff,utc=True,format='mixed')
    snapshots=snapshots.copy();snapshots['cutoff']=pd.to_datetime(snapshots.cutoff,utc=True,format='mixed')
    snapshots['normal_role_asof']=pd.to_datetime(snapshots.normal_role_asof,utc=True,errors='coerce',format='mixed')
    news=news.copy();news['cutoff']=pd.to_datetime(news.cutoff,utc=True,format='mixed')
    news['news_effective_at']=pd.to_datetime(news.news_effective_at,utc=True,format='mixed',errors='coerce')
    source_news={(r.fixture_uuid,r.player_uuid):r for r in news.itertuples()}
    meta=core.copy();meta['kickoff']=pd.to_datetime(meta.kickoff_at,utc=True,format='mixed')
    meta=meta[['fixture_uuid','kickoff','team_id','cutoff']].drop_duplicates()
    # 2024 match UUIDs in FotMob ledger differ from Core. Map through exact PL kickoff/club.
    clubids={club:int(g.team_id.iloc[0])for club,g in snapshots.groupby('club')}
    metakeys={(r.kickoff,int(r.team_id)):r for r in meta.itertuples()}
    groups={(c,m):g for (c,m),g in p.groupby(['club','match_id'])}
    byclub={c:g.sort_values('cutoff')for c,g in snapshots.groupby('club')}
    rows=[];individual=[];coverage=[]
    # Accumulate all competition histories; only PL informs normal hierarchy.
    for club,gg in games.groupby('club'):
        histories=[];pl_events=defaultdict(list);uuidmap={};pastplayers=defaultdict(list)
        responses={role:[]for role in ['objective','existing']}
        for match in gg.sort_values(['kickoff','match_id']).to_dict('records'):
            current=groups[(club,match['match_id'])]
            cm=metakeys.get((pd.Timestamp(match['kickoff']),clubids[club]))if match['competition']=='Premier League'else None
            cutoff=pd.Timestamp(cm.cutoff)if cm is not None else pd.Timestamp(match['kickoff'])-pd.Timedelta(seconds=1)
            if cutoff>=pd.Timestamp(match['kickoff']):raise ValueError('Cutoff after kickoff')
            past=[h for h in histories if known_before(h['known_at'],cutoff)]
            # Current match response is unavailable while all features/normal lists are made.
            existing=byclub[club];existing=existing[(existing.cutoff.le(cutoff))&existing.normal_role_asof.lt(cutoff)&existing.normal_role_p.notna()]
            ext={r.player_uuid:r for r in existing.drop_duplicates('player_uuid',keep='last').itertuples()}
            latestfixture=str(cm.fixture_uuid)if cm is not None else None
            priorpl=[h for h in past if h['competition']=='Premier League']
            enough=len(priorpl)>=3 and len(pl_events)>=11 and match['complete_xi']
            for role in ['objective','existing']:
                profiles={}
                for pid,events in pl_events.items():
                    d=prior_role(events,cutoff)
                    if d['exposure']<=0:continue
                    uuid=uuidmap.get(pid)
                    if role=='existing'and uuid in ext:
                        e=ext[uuid];d=dict(p=float(e.normal_role_p),duration=float(e.normal_role_s),existing=True)
                    profiles[pid]=d
                if not enough or len(profiles)<11:continue
                normal=select_normal(profiles)
                currentrows={r.player_id:r for r in current.itertuples()}
                hist=[h for h in responses[role]if known_before(h['known_at'],cutoff)]
                glob=float(np.mean([h['normal_share']for h in hist]))if hist else 0.65
                long,n,short=smoothed_usage(hist,match['competition'],glob)
                pllong,pln,plshort=smoothed_usage(hist,'Premier League',glob)
                statuses={};detail=[]
                for pid in normal:
                    nr=source_news.get((latestfixture,uuidmap.get(pid)))
                    # News is fixture/deadline scoped; never carry old AVAILABLE into a cup.
                    state='UNKNOWN';url=None;effective=None
                    if nr is not None and nr.news_eligible and known_before(nr.news_effective_at,cutoff)and pd.Timestamp(nr.cutoff)==cutoff:
                        state=str(nr.news_state);url=nr.news_source;effective=nr.news_effective_at
                    statuses[pid]=state
                    ph=[h for h in pastplayers[pid]if known_before(h['known_at'],cutoff)]
                    loads={days:sum(float(h['minutes'])for h in ph if pd.notna(h['minutes'])and 0<(cutoff-h['kickoff']).total_seconds()/86400<=days)for days in [7,14]}
                    active=[h for h in ph if pd.notna(h['minutes'])and h['minutes']>0]
                    rest=(cutoff-active[-1]['kickoff']).total_seconds()/86400 if active else np.nan
                    cr=currentrows.get(pid)
                    # Missing current player is not called rested; only explicit pre-known AVAILABLE gives that endpoint.
                    detail.append(dict(player_id=pid,player_uuid=uuidmap.get(pid),role_p=profiles[pid]['p'],role_duration=profiles[pid]['duration'],existing_profile=profiles[pid]['existing'],minutes_7=loads[7],minutes_14=loads[14],player_rest=rest,
                        availability_state=state,availability_known_at=effective,availability_source=url,
                        started=int(cr is not None and cr.started is True),recorded_minutes=float(cr.minutes)if cr is not None and pd.notna(cr.minutes)else np.nan,
                        explicit_available=state in ['AVAILABLE','RETURNED_AVAILABLE']))
                def teamload(days):return sum(h['recorded_minutes']for h in past if 0<(cutoff-h['kickoff']).total_seconds()/86400<=days)
                key=dict(season='2024-25',club=club,club_id=clubids[club],match_id=match['match_id'],fixture_uuid=latestfixture,competition=match['competition'],competition_id=match['competition'],role_definition=role,
                    cutoff=cutoff,kickoff=match['kickoff'],cutoff_kind='FPL_deadline'if cm is not None else'pre_kickoff_diagnostic',
                    raw_stage=match['stage'],phase=phase(match['competition'],match['stage']),
                    rest_days=(cutoff-past[-1]['kickoff']).total_seconds()/86400 if past else 0.,
                    team_minutes_7=teamload(7),team_minutes_14=teamload(14),
                    prior_turnover=float(np.nanmean([h['xi_changes_from_previous_recorded']for h in past[-3:]]))if len(past)>1 else 0.,
                    role_mean=np.mean([d['role_p']for d in detail]),role_sd=np.std([d['role_p']for d in detail]),
                    prior_usage=long,prior_usage_n=n,prior_recent_usage=short,prior_pl_usage=pllong,prior_pl_n=pln,prior_pl_recent_usage=plshort,
                    season_days=(cutoff-pd.Timestamp('2024-08-01',tz='UTC')).total_seconds()/86400,
                    top_minutes_7=np.mean([d['minutes_7']for d in detail]),top_minutes_14=np.mean([d['minutes_14']for d in detail]),
                    top_rest=float(np.nanmean([d['player_rest']for d in detail])),
                    known_available=sum(d['explicit_available']for d in detail)/11,
                    known_out=sum(d['availability_state']in ['OUT','SUSPENDED']for d in detail)/11,
                    unknown_availability=sum(d['availability_state']=='UNKNOWN'for d in detail)/11,
                    existing_profile_share=np.mean([d['existing_profile']for d in detail]),
                    history_last_known=max([h['known_at']for h in past])if past else None,
                    deadline_correct=False,source_publication_at=None,source_clock='kickoff_plus_4h_proxy',
                    raw_source_url=str(current.iloc[0].source_url),next_known_fixture_at=None,tie_state=None,
                    transfer_registration_verified=False)
                # Only now access the current XI/minutes as labels.
                key['normal_share']=sum(d['started']for d in detail)/11
                key['xi_changes']=match['xi_changes_from_previous_recorded']
                total=current.minutes.sum(min_count=1)
                key['normal_minute_share']=sum(d['recorded_minutes']for d in detail if pd.notna(d['recorded_minutes']))/total if total>0 else np.nan
                key['normal_nonselection_unknown']=sum(not d['started']and d['availability_state']=='UNKNOWN'for d in detail)
                key['verified_available_not_started']=sum(not d['started']and d['explicit_available']for d in detail)
                rows.append(key)
                for d in detail:individual.append({**{k:key[k]for k in ['season','club','club_id','match_id','competition','cutoff','role_definition','deadline_correct']},**d})
                responses[role].append(dict(competition=match['competition'],normal_share=key['normal_share'],known_at=pd.Timestamp(match['kickoff'])+pd.Timedelta(hours=4)))
            # Update historical evidence after constructing both role responses.
            h={**match,'known_at':pd.Timestamp(match['kickoff'])+pd.Timedelta(hours=4),'recorded_minutes':float(current.minutes.sum())}
            histories.append(h)
            for rr in current.itertuples():
                uuidmap[rr.player_id]=rr.player_uuid
                pastplayers[rr.player_id].append(dict(kickoff=pd.Timestamp(match['kickoff']),known_at=h['known_at'],minutes=rr.minutes))
                if match['competition']=='Premier League'and rr.started in [True,False]:
                    # Named starter/bench in historical source = selected matchday; unknown absence excluded.
                    pl_events[rr.player_id].append(dict(known_at=h['known_at'],fixture_uuid=rr.match_id,available=True,started=bool(rr.started),minutes=float(rr.minutes)if pd.notna(rr.minutes)else None))
    return pd.DataFrame(rows),pd.DataFrame(individual)


BASE_NUM=['rest_days','team_minutes_7','team_minutes_14','prior_turnover','role_mean','known_available','known_out','unknown_availability']
OBJECTIVE_NUM=['season_days','pl_rank_fraction','pl_points_per_game','pl_gap_to_top_per_game','pl_gap_to_bottom3_per_game','opponent_pl_points_per_game']
HISTORY_NUM=['global_usage','global_usage_n']
DYNAMIC_NUM=['prior_recent_usage','prior_pl_usage','priority_gap','recent_change']
INDIVIDUAL_NUM=['top_minutes_7','top_minutes_14','top_rest','role_sd','existing_profile_share']


def feature_dicts(frame,variant,player=False,counter_pl=False):
    f=frame.copy()
    if counter_pl:
        f['competition']='Premier League';f['phase']='league'
        f['prior_usage']=f.prior_pl_usage;f['prior_usage_n']=f.prior_pl_n;f['prior_recent_usage']=f.prior_pl_recent_usage
        f['global_usage']=f.global_pl_usage;f['global_usage_n']=f.global_pl_n
    f['priority_gap']=f.prior_usage-f.prior_pl_usage
    f['recent_change']=f.prior_recent_usage-f.prior_usage
    numeric=BASE_NUM.copy();cats=['club']
    if variant=='A_objective' or variant in ['C_combined','D_dynamic','D_individual']:
        numeric+=OBJECTIVE_NUM;cats+=['competition','phase']
    if variant in ['B_global_history','B_club_history','C_combined','D_dynamic','D_individual']:
        cats+=['competition'];numeric+=HISTORY_NUM
    if variant in ['B_club_history','C_combined','D_dynamic','D_individual']:
        cats+=['club_comp'];numeric+=['prior_usage','prior_usage_n']
    if variant in ['D_dynamic','D_individual']:numeric+=DYNAMIC_NUM
    if variant=='D_individual':numeric+=INDIVIDUAL_NUM
    if player:numeric+=['role_p','role_duration','minutes_7','minutes_14','player_rest']
    out=[]
    for r in f.to_dict('records'):
        d={k:(float(r[k])if pd.notna(r.get(k))else 0.)for k in numeric}
        for k in numeric:d['missing:'+k]=float(pd.isna(r.get(k)))
        for c in set(cats):d[c]=str(r['club'])+'::'+str(r['competition'])if c=='club_comp'else str(r[c])
        # Time-varying club/competition deviation is regularized like other features.
        if variant in ['D_dynamic','D_individual']:d['slope:'+str(r['club'])+'::'+str(r['competition'])]=float(r['season_days'])/300
        out.append(d)
    return out


class Model:
    def __init__(self,alpha=10.,classification=False):
        self.alpha=alpha;self.classification=classification
        self.vector=DictVectorizer(sparse=True,sort=True);self.scale=StandardScaler(with_mean=False)
    def fit(self,features,y):
        x=self.scale.fit_transform(self.vector.fit_transform(features))
        # Explicit nested interaction coefficients shrink to zero/global competition effect.
        # Sparse category columns not individually variance-scaled: rare one-hot effects must not escape shrinkage.
        names=self.vector.get_feature_names_out();self.scale.scale_[np.array(['='in n or n.startswith('slope:')for n in names])]=1.
        x=self.scale.transform(self.vector.transform(features))
        self.fit_x=x;self.y=np.asarray(y)
        self.estimator=(LogisticRegression(C=1/self.alpha,max_iter=2000,tol=1e-9,solver='lbfgs')if self.classification else Ridge(alpha=self.alpha,solver='lsqr',tol=1e-12))
        self.estimator.fit(x,y);return self
    def transform(self,features):return self.scale.transform(self.vector.transform(features))
    def predict(self,features):
        x=self.transform(features)
        return self.estimator.predict_proba(x)[:,1]if self.classification else self.estimator.predict(x)
    def contrast_uncertainty(self,features,reference,weeks,groups):
        """Week-cluster sandwich for penalized coefficients; conditional on fit/hyperparameters."""
        x=self.fit_x.toarray();x=np.column_stack([np.ones(len(x)),x]);pen=np.eye(x.shape[1])*self.alpha;pen[0,0]=0
        inv=np.linalg.pinv(x.T@x+pen,rcond=1e-12)
        residual=self.y-self.estimator.predict(self.fit_x)
        scores=[]
        for w in sorted(set(weeks)):
            mask=np.asarray(weeks)==w;scores.append(x[mask].T@residual[mask])
        scores=np.asarray(scores);cov=inv@scores.T@scores@inv
        d=(self.transform(features)-self.transform(reference)).toarray();d=np.column_stack([np.zeros(len(d)),d])
        se=np.sqrt(np.maximum(np.einsum('ij,jk,ik->i',d,cov,d),0))
        groupse={}
        for key in sorted(set(groups)):
            z=d[np.array([v==key for v in groups])].mean(0)
            groupse[key]=float(np.sqrt(max(z@cov@z,0)))
        return se,groupse


def sporting_context(frame,ledger,clubmap):
    """Past PL results only; no inferred ambitions, future standings or tie states."""
    past=[]
    for r in ledger:
        if r['competition']!='prem':continue
        score=re.fullmatch(r'(\d+)\s*-\s*(\d+)',str(r['result']))
        if not score:continue
        past.append((pd.Timestamp(r['kickoff'])+pd.Timedelta(hours=4),clubmap[r['home_team']],clubmap[r['away_team']],*map(int,score.groups())))
    matches={r['match_id']:r for r in ledger};out=[]
    for r in frame.to_dict('records'):
        stats={c:[0,0,0,0]for c in clubmap.values()} # PL points, games, goal diff, goals for
        for t,home,away,hg,ag in past:
            if t>=pd.Timestamp(r['cutoff']):continue
            for club,gf,ga in [(home,hg,ag),(away,ag,hg)]:
                stats[club][0]+=3 if gf>ga else 1 if gf==ga else 0;stats[club][1]+=1;stats[club][2]+=gf-ga;stats[club][3]+=gf
        ordered=sorted(stats,key=lambda c:(-stats[c][0],-stats[c][2],-stats[c][3],c));me=stats[r['club']];den=max(me[1],1)
        mm=matches[r['match_id']];home=clubmap.get(mm['home_team']);away=clubmap.get(mm['away_team']);opp=away if home==r['club']else home
        ranking=1+sum((s[0],s[2],s[3])>(me[0],me[2],me[3])for s in stats.values())
        r.update(pl_rank_fraction=ranking/len(ordered),pl_points_per_game=me[0]/den,
            pl_gap_to_top_per_game=(stats[ordered[0]][0]-me[0])/den,
            pl_gap_to_bottom3_per_game=(me[0]-stats[ordered[-3]][0])/den,
            opponent_pl_points_per_game=stats[opp][0]/max(stats[opp][1],1)if opp in stats else np.nan)
        out.append(r)
    return pd.DataFrame(out)


def pooled_history(frame):
    result=[]
    for _,g in frame.groupby('role_definition'):
        for row in g.to_dict('records'):
            old=g[pd.to_datetime(g.kickoff,utc=True)+pd.Timedelta(hours=4)<pd.Timestamp(row['cutoff'])]
            for comp,prefix in [(row['competition'],'global'),('Premier League','global_pl')]:
                values=old.loc[old.competition.eq(comp),'normal_share']
                row[prefix+'_usage']=float(values.mean())if len(values)else .65
                row[prefix+'_n']=len(values)
            # Uniform prefix for the current competition.
            row['global_usage_n']=row.pop('global_n')
            result.append(row)
    return pd.DataFrame(result)


def bootstrap_delta(frame,baseline,candidate,outcome):
    d=abs(frame[candidate]-frame[outcome])-abs(frame[baseline]-frame[outcome])
    return block_interval(frame.cutoff,d)


def block_interval(clocks,values):
    week=((pd.to_datetime(clocks,utc=True)-pd.Timestamp('2025-01-01',tz='UTC')).dt.days//7).to_numpy()
    w=pd.DataFrame(dict(week=week,d=np.asarray(values))).groupby('week').agg(total=('d','sum'),n=('d','size')).reindex(range(int(week.min()),int(week.max())+1),fill_value=0)
    rng=np.random.default_rng(20261016);ix=(rng.integers(len(w),size=(1000,int(np.ceil(len(w)/4)),1))+np.arange(4)).reshape(1000,-1)[:,:len(w)]%len(w)
    b=w.total.to_numpy()[ix].sum(1)/w.n.to_numpy()[ix].sum(1)
    return dict(delta=float(np.mean(values)),low=float(np.quantile(b,.025)),high=float(np.quantile(b,.975)))


def metrics(y,p,classification=False):
    y=np.asarray(y);p=np.asarray(p);e=p-y
    d=dict(n=len(y),mae=float(abs(e).mean()),rmse=float(np.sqrt((e**2).mean())),bias=float(e.mean()))
    if classification:d.update(brier=float(brier_score_loss(y,p)),log_loss=float(log_loss(y,np.clip(p,1e-12,1-1e-12),labels=[0,1])))
    return d


def validate(frame,individual):
    records=[];predictions=[];calibration=[];importance=[];selection=[]
    for role,allrows in frame.groupby('role_definition'):
        f=allrows.sort_values(['cutoff','club','match_id']).reset_index(drop=True)
        early=f.cutoff.lt(pd.Timestamp('2024-12-01',tz='UTC'));val=f.cutoff.between(pd.Timestamp('2024-12-01',tz='UTC'),pd.Timestamp('2025-01-01',tz='UTC'),inclusive='left');dev=early|val;test=~dev
        weights={};saved={}
        for variant in VARIANTS:
            features=feature_dicts(f,variant)
            # Tune only normal starter-share MAE in December; fix before later evaluation.
            scores=[]
            for alpha in [1.,10.,100.]:
                m=Model(alpha).fit([features[i]for i in np.flatnonzero(early)],f.loc[early,'normal_share'])
                err=metrics(f.loc[val,'normal_share'],np.clip(m.predict([features[i]for i in np.flatnonzero(val)]),0,1))['mae'];scores.append((err,alpha))
            alpha=min(scores)[1];weights[variant]=alpha
            selection.append(dict(role_definition=role,model=variant,alpha=alpha,validation_mae=min(scores)[0],development_rows=int(dev.sum()),evaluation_rows=int(test.sum())))
            for outcome,(lo,hi)in OUTCOMES.items():
                use=f[outcome].notna();train=dev&use;ev=test&use
                m=Model(alpha).fit([features[i]for i in np.flatnonzero(train)],f.loc[train,outcome])
                pred=np.clip(m.predict([features[i]for i in np.flatnonzero(ev)]),lo,hi)
                v=f.loc[ev,['club','club_id','competition','match_id','cutoff',outcome]].copy();v['prediction']=pred;v['model']=variant;v['outcome']=outcome;v['role_definition']=role
                predictions.append(v.rename(columns={outcome:'observed'}));saved[(variant,outcome)]=v
                records.append(dict(role_definition=role,model=variant,outcome=outcome,**metrics(v[outcome],pred)))
                if outcome=='normal_share':
                    refs=feature_dicts(f.loc[ev],variant,counter_pl=True);fs=[features[i]for i in np.flatnonzero(ev)]
                    effect=m.predict(fs)-m.predict(refs)
                    keys=[(r.club,r.competition)for r in f.loc[ev].itertuples()]
                    se,groupse=m.contrast_uncertainty(fs,refs,pd.to_datetime(f.loc[train,'cutoff']).dt.strftime('%G-%V').to_numpy(),keys)
                    im=f.loc[ev].copy();im['model']=variant;im['importance_estimate']=effect*100;im['importance_se']=se*100
                    im['importance_low']=(effect-1.96*se)*100;im['importance_high']=(effect+1.96*se)*100
                    im['club_comp_mean_se']=[groupse[k]*100 for k in keys]
                    im['predicted_normal_share']=pred;importance.append(im)
        # Individual probability endpoint: 11 prior-defined normal players, not current-XI-selected sample.
        ip=individual[individual.role_definition.eq(role)].merge(f,on=['season','club','club_id','match_id','competition','cutoff','role_definition','deadline_correct'],validate='many_to_one',suffixes=('','_team'))
        # Strict available and unknown strata both reported. Inference is not labelled intentional rest.
        ip=ip.sort_values(['cutoff','club','player_id']).reset_index(drop=True)
        train=ip.cutoff.lt(pd.Timestamp('2025-01-01',tz='UTC'));ev=~train
        for variant in VARIANTS:
            features=feature_dicts(ip,variant,player=True)
            m=Model(weights[variant],classification=True).fit([features[i]for i in np.flatnonzero(train)],ip.loc[train,'started'])
            pred=m.predict([features[i]for i in np.flatnonzero(ev)])
            v=ip.loc[ev,['club','competition','match_id','cutoff','player_id','started','availability_state','explicit_available']].copy();v['prediction']=pred;v['role_definition']=role;v['model']=variant;v['outcome']='normal_player_started'
            predictions.append(v.rename(columns={'started':'observed'}));saved[(variant,'normal_player_started')]=v
            for group,mask in [('all_unknown_included',np.ones(len(v),bool)),('explicit_predeadline_available',v.explicit_available.to_numpy()),('unknown_availability',v.availability_state.eq('UNKNOWN').to_numpy())]:
                if mask.sum():records.append(dict(role_definition=role,model=variant,outcome='normal_player_started',availability_group=group,**metrics(v.loc[mask,'started'],pred[mask],True)))
            bins=pd.cut(pred,np.linspace(0,1,11),include_lowest=True)
            for b,g in v.groupby(bins,observed=True):calibration.append(dict(role_definition=role,model=variant,bin=str(b),n=len(g),predicted=float(g.prediction.mean()),observed=float(g.started.mean())))
        # All comparisons use matched samples and group all same-week games/players together.
        contrasts=[('control','A_objective'),('control','B_global_history'),('B_global_history','B_club_history'),('A_objective','C_combined'),('B_club_history','C_combined'),('C_combined','D_dynamic'),('D_dynamic','D_individual')]
        for before,after in contrasts:
            for outcome in list(OUTCOMES)+['normal_player_started']:
                b=saved[(before,outcome)];a=saved[(after,outcome)]
                key=['club','match_id','cutoff']+(['player_id']if outcome=='normal_player_started'else[])
                j=a.merge(b[key+['prediction']],on=key,suffixes=('','_baseline'),validate='one_to_one')
                y=j['started'if outcome=='normal_player_started'else outcome]
                loss=(j.prediction-y)**2-(j.prediction_baseline-y)**2 if outcome=='normal_player_started'else abs(j.prediction-y)-abs(j.prediction_baseline-y)
                records.append(dict(role_definition=role,model=after,outcome=outcome,contrast_before=before,loss='brier'if outcome=='normal_player_started'else'mae',**block_interval(j.cutoff,loss)))
    return pd.DataFrame(records),pd.concat(predictions,ignore_index=True),pd.DataFrame(calibration),pd.concat(importance,ignore_index=True),pd.DataFrame(selection)


def require_deadline_features(frame):
    if not frame.deadline_correct.eq(True).all():raise ValueError('Not Available: uncertified source clocks/schedule/availability')
    if 'source_publication_at'not in frame or frame.source_publication_at.isna().any():raise ValueError('Missing verified publication')
    if not (pd.to_datetime(frame.source_publication_at,utc=True)<pd.to_datetime(frame.cutoff,utc=True)).all():raise ValueError('Future publication')
    if not (pd.to_datetime(frame.history_last_known,utc=True)<pd.to_datetime(frame.cutoff,utc=True)).all():raise ValueError('Future historical feature')
    return frame


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(ROOT/'work/core.sqlite3')as c:
        core=pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,team_id,kickoff_at,started,minutes FROM player_fixture_observations WHERE is_final=1 AND season='2024-25'",c)
    coverage=pd.read_csv(ROOT/'analysis/results/role-injury-mm-20261016/coverage.csv')
    names={(r.season,int(r.team_id)):r.club for r in coverage.itertuples()}
    players,audit=load24(core,names);games=team_games(players)
    from individual_mm_evidence import load_frame
    frozen=load_frame(ROOT/'analysis/results/role-injury-mm-20261016/predictions.npz')
    frozen=frozen[frozen.season.eq('2024-25')&frozen['mode'].eq(SELECTION)].copy()
    frozen['club']=[names[('2024-25',int(t))]for t in frozen.team_id]
    snapshots=frozen[['club','team_id','player_uuid','cutoff','normal_role_p','normal_role_s','normal_role_asof']].drop_duplicates()
    news=frozen[['fixture_uuid','player_uuid','cutoff','news_eligible','news_state','news_source','news_effective_at']].copy()
    core=core.merge(frozen[['fixture_uuid','team_id','cutoff']].drop_duplicates(),on=['fixture_uuid','team_id'],how='left',validate='many_to_one')
    # First five PL GWs have no frozen deadline; use pre-kickoff diagnostic, never silently an FPL deadline.
    core['cutoff']=core.cutoff.fillna(pd.to_datetime(core.kickoff_at,utc=True,format='mixed')-pd.Timedelta(seconds=1))
    f,ip=build_samples(players,games,snapshots,core,news)
    ledger=jl(RAW24/'all_competition_match_actuals.jsonl.gz')
    f=pooled_history(sporting_context(f,ledger,audit['club_mapping']))
    f['cutoff']=pd.to_datetime(f.cutoff,utc=True,format='mixed');ip['cutoff']=pd.to_datetime(ip.cutoff,utc=True,format='mixed')
    metrics_,pred,cal,importance,sel=validate(f,ip)
    for name,d in [('match_samples',f),('individual_role_features',ip),('validation_metrics',metrics_),('validation_predictions',pred),('calibration',cal),('pre_match_features',importance),('hyperparameter_selection',sel)]:
        d.to_csv(OUT/(name+'.csv.gz'if name in ['individual_role_features','validation_predictions','pre_match_features']else name+'.csv'),index=False,compression={'method':'gzip','mtime':0}if name in ['individual_role_features','validation_predictions','pre_match_features']else None)
    observed=[]
    for (role,club,comp),g in f.groupby(['role_definition','club','competition']):
        observed.append(dict(role_definition=role,club=club,competition=comp,games=len(g),normal_starter_share=g.normal_share.mean(),normal_minute_share=g.normal_minute_share.mean(),xi_changes=g.xi_changes.mean(),mean_unknown_availability=g.unknown_availability.mean(),explicit_available_nonstarts=int(g.verified_available_not_started.sum()),unknown_nonselection=int(g.normal_nonselection_unknown.sum())))
    pd.DataFrame(observed).to_csv(OUT/'observed_club_priorities.csv',index=False)
    clubpri=[];monthly=[]
    for (role,model,club,comp),g in importance.groupby(['role_definition','model','club','competition']):
        # Average coefficient contrasts, not a subjective 0-100 score.
        mean=g.importance_estimate.mean();se=g.club_comp_mean_se.iloc[0]
        clubpri.append(dict(role_definition=role,model=model,club=club,competition=comp,evaluation_games=len(g),relative_priority_pp=mean,conditional_low=mean-1.96*se,conditional_high=mean+1.96*se,predicted_normal_share=g.predicted_normal_share.mean(),observed_normal_share=g.normal_share.mean(),deadline_correct=False))
        for month,h in g.groupby(pd.to_datetime(g.cutoff).dt.strftime('%Y-%m')):monthly.append(dict(role_definition=role,model=model,club=club,competition=comp,month=month,games=len(h),relative_priority_pp=h.importance_estimate.mean(),observed_normal_share=h.normal_share.mean(),deadline_correct=False))
    pd.DataFrame(clubpri).to_csv(OUT/'club_priorities.csv',index=False);pd.DataFrame(monthly).to_csv(OUT/'monthly_priorities.csv',index=False)
    inputs=[ROOT/'scripts/experimental_club_match_importance.py',ROOT/'scripts/analyze_mm_competition_rotation.py',ROOT/'scripts/experimental_mm_role_profiles.py',RAW24/'all_competition_player_observations.jsonl.gz',RAW24/'all_competition_match_actuals.jsonl.gz',ROOT/'analysis/results/role-injury-mm-20261016/predictions.npz',ROOT/'analysis/results/role-injury-mm-20261016/coverage.csv']
    save_json(OUT/'source_manifest.json',dict(inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs},source_audit=audit,deadline_correct=False,locked_model_active=False,production_changed=False,mm_pm_ts_points_chips_run=False,
        validation='2024/25 pre-Dec train, Dec validation, refit pre-Jan, later evaluation; previously reused season, not independent holdout',
        unknowns=['2025/26 FA missing and Europe IDs/quarantines prevent comparable all-competition validation','Historical schedule/phase publication clocks missing','No verified predeadline tie state or next-known-fixture calendar','Unknown absence is not deliberate rotation','Hierarchy is prior selection/conditional minutes, not measured player ability','Normal-player events conditioned on historical named matchday selection; no unknown absence counted as bench'],
        feature_contract='importance_estimate is raw predicted normal-XI-share contrast with same-club PL, in percentage points; no absolute latent causal scale; consumer must call require_deadline_features'))
    content={}
    import gzip
    for p in sorted(OUT.glob('*')):
        if p.name in ['content_manifest.json','report.md']:continue
        b=gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes();content[p.name]=dict(sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
    save_json(OUT/'content_manifest.json',content)
    print('Executed priority candidates:',len(f),'team-role rows;',len(ip),'individual rows;',len(pred),'predictions')


if __name__=='__main__':main()
