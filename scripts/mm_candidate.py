"""Versioned, preview-only MM. Never imported by the production forecast.

PR9 B owns marginal p/q/s/c. PR11 owns historical role/formation evidence.
PR13 supplies a mean-matched duration PMF. XI is a constrained point selection,
not a claim that its members have marginal probability one.
"""
from collections import defaultdict
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.special import logit
from fpl_v1_1_model.role_classifier import template, role_family
from research_mm_predictive_distribution import conditional

VERSION = 'individual-B-formation-pmf-preview.1'
CONTRACT = 'fpl.mm/1.0'
KEY = ['season', 'fixture_uuid', 'player_uuid']
TOL = 1e-6


def validate_frame(frame):
    f = frame.copy()
    required = set(KEY + ['team_id', 'gw', 'cutoff', 'p', 'q', 's', 'c', 'x', 'pos'])
    if required - set(f):
        raise ValueError('Missing MM fields: ' + str(sorted(required-set(f))))
    if f.duplicated(KEY).any() or f[list(required)].isna().any().any():
        raise ValueError('Duplicate identity or missing MM input')
    v = f[['p','q','s','c','x']].to_numpy(float)
    if not np.isfinite(v).all() or (v < 0).any():
        raise ValueError('Nonfinite/negative MM input')
    if (v[:,:2] > 1+1e-12).any() or (v[:,2:] > 90+1e-10).any():
        raise ValueError('MM outside support')
    if ((f.q > 0) & (f.c < 1)).any():
        raise ValueError('Positive cameo probability requires positive duration')
    expected = f.p*f.s+(1-f.p)*f.q*f.c
    if not np.allclose(expected, f.x, atol=TOL, rtol=0):
        raise ValueError('Inconsistent MM expectation')
    cuts = pd.to_datetime(f.cutoff, utc=True, errors='raise')
    for col in ['max_history_known_at', 'physical_last_known_at']:
        if col in f:
            clock = pd.to_datetime(f[col], utc=True, errors='raise')
            if not (clock.isna() | clock.lt(cuts)).all():
                raise ValueError('Future history: '+col)
    if 'news_eligible' in f:
        known=f.news_eligible.eq(True)
        if 'news_effective_at' not in f:
            raise ValueError('Missing news clock')
        clock=pd.to_datetime(f.news_effective_at, utc=True, errors='raise')
        if not (clock[known].notna() & clock[known].lt(cuts[known])).all():
            raise ValueError('News not known before cutoff')
        hard=known & f.news_state.isin(['OUT','SUSPENDED'])
        if not f.loc[hard,['p','q','x']].eq(0).all().all():
            raise ValueError('Applicable hard unavailable source contradicts forecast')
    return f


def minute_masses(f, sigma=30.):
    """Fixed PR13 development-selected sigma; endpoints exactly degenerate.

    Tighten PR13's numerical approximation without fitting a new distribution.
    A final affine mixture with the endpoint repairs any remaining mean residual
    at machine precision and keeps support/normalization intact.
    """
    def duration(mu, low):
        mu=np.asarray(mu,float)
        z=conditional(mu,sigma,minimum=low)
        grid=np.arange(low,91.)
        mean=z@grid
        for i in range(len(mu)):
            delta=mu[i]-mean[i]
            end=90 if delta>=0 else low
            den=end-mean[i]
            if abs(den)>1e-15:
                alpha=np.clip(delta/den,0,1)
                z[i]*=1-alpha;z[i,end-low]+=alpha
            if mu[i]==low or mu[i]==90:
                z[i]=0;z[i,int(mu[i])-low]=1
        return z
    st=duration(f.s,0);ca=duration(f.c,1)
    p=f.p.to_numpy(float);q=f.q.to_numpy(float)
    mass=p[:,None]*st
    mass[:,1:]+=((1-p)*q)[:,None]*ca
    mass[:,0]+=(1-p)*(1-q)
    if not np.allclose(mass.sum(axis=1),1,atol=1e-12,rtol=0):
        raise ValueError('PMF not normalized')
    if not np.allclose(mass@np.arange(91),f.x,atol=TOL,rtol=0):
        raise ValueError('PMF expectation moved B')
    return mass


def intervals(mass, level, method='central'):
    cdf=np.cumsum(mass,axis=1)
    if method=='central':
        return np.argmax(cdf >= (1-level)/2,axis=1),np.argmax(cdf >= 1-(1-level)/2-1e-12,axis=1)
    if method!='shortest':raise ValueError('Unknown interval method')
    # Shortest contiguous integer interval containing >= requested model mass.
    # Tie: greater contained mass, then lower endpoint; no observed truth used.
    lows=np.zeros(len(mass),int);highs=np.full(len(mass),90,int)
    for i,row in enumerate(mass):
        cum=np.r_[0.,np.cumsum(row)];best=(91,0.,0,90)
        for lo in range(91):
            hi=int(np.searchsorted(cum,cum[lo]+level-1e-12,side='left'))-1
            if hi>90:continue
            hi=max(lo,hi);contained=cum[hi+1]-cum[lo]
            option=(hi-lo,-contained,lo,hi)
            if option<best:best=option
        lows[i],highs[i]=best[2],best[3]
    return lows,highs


class FormationSelector:
    """PR11 decay/compatibility, with hard GK and unavailable constraints.

    Unlike PR11's soft 1e-4 penalties, incompatible GK slots are impossible.
    Only historical complete classified XIs enter the ledger. Target XI is never
    consulted. Unknown detailed outfield roles stay unknown, not inferred fact.
    """
    def __init__(self, ledger):
        self.games=defaultdict(list)
        h=ledger.copy()
        h['known_at']=pd.to_datetime(h.kickoff,utc=True)+pd.Timedelta(hours=3)
        for (season,team,fix),g in h.groupby(['season','team_id','fixture_uuid'],sort=True):
            if len(g)!=11 or g.player_uuid.nunique()!=11 or g.formation.nunique()!=1:continue
            form=str(g.formation.iloc[0]);slots=['GK']+[r for line in template(form) for r in line]
            if len(slots)!=11:continue
            self.games[(str(season),int(team))].append(dict(fixture=str(fix),known_at=g.known_at.max(),formation=form,players=g[['player_uuid','final_role']].to_dict('records')))
        for key in self.games:self.games[key].sort(key=lambda g:(g['known_at'],g['fixture']))

    def choose(self,g):
        if g.cutoff.nunique()!=1:raise ValueError('Mixed team cutoffs')
        cut=pd.Timestamp(g.cutoff.iloc[0]);team=int(g.team_id.iloc[0]);season=str(g.season.iloc[0])
        games=[x for x in self.games.get((season,team),[]) if x['known_at']<cut and x['fixture']!=str(g.fixture_uuid.iloc[0])]
        weights=defaultdict(float)
        for lag,game in enumerate(games[-12:][::-1]):weights[game['formation']]+=2**(-lag/5.)
        forms={k:v/sum(weights.values()) for k,v in sorted(weights.items())} if weights else {}
        roles={str(pid):defaultdict(float) for pid in g.player_uuid}
        for game in games:
            w=2**(-max(0,(cut-game['known_at']).total_seconds()/86400)/70.)
            for pl in game['players']:
                pid=str(pl['player_uuid'])
                if pid in roles:roles[pid][str(pl['final_role'])]+=w
        profiles={}
        for pid,rr in roles.items():
            ordered=sorted(rr,key=lambda k:(-rr[k],k));den=sum(rr.values())
            profiles[pid]=dict(primary=ordered[0] if ordered else None,secondary=ordered[1] if len(ordered)>1 else None,probabilities={k:rr[k]/den for k in ordered},status='historical' if ordered else 'Not Available')
        empty=dict(formation=None,formation_distribution=forms,assignments={},profiles=profiles,status='Not Available: fewer than three prior complete role XIs',last_known_at=max([x['known_at'] for x in games],default=None))
        if len(games)<3:return empty
        # Most frequent prior formation first; alternative historical formations
        # only when primary assignment is infeasible. Marginals remain unchanged.
        for form in sorted(forms,key=lambda k:(-forms[k],k)):
            slots=['GK']+[r for line in template(form) for r in line]
            ids=g.player_uuid.astype(str).tolist();mat=np.full((11,len(ids)),-np.inf)
            for j,row in enumerate(g.itertuples()):
                if row.p<=0:continue
                rr=roles[str(row.player_uuid)];total=sum(rr.values());isgk=row.pos in ['GK','GKP']
                for si,slot in enumerate(slots):
                    if isgk!=(slot=='GK'):continue
                    exact=rr.get(slot,0)/total if total else 0
                    family=sum(v for k,v in rr.items() if role_family(k)==role_family(slot))/total if total else 0
                    mat[si,j]=logit(np.clip(row.p,1e-7,1-1e-7))+.5*np.log(.02+.78*exact+.20*family)
            try:a,b=linear_sum_assignment(-mat)
            except ValueError:continue
            if len(a)!=11 or not np.isfinite(mat[a,b]).all():continue
            assignments={ids[j]:dict(slot=slots[i],slot_index=int(i)) for i,j in zip(a,b)}
            if len(assignments)!=11:raise ValueError('Duplicate assignment')
            return dict(**{k:v for k,v in empty.items() if k not in ['formation','assignments','status']},formation=form,assignments=assignments,status='preview historical formation selection')
        return dict(**{k:v for k,v in empty.items() if k!='status'},status='Not Available: no feasible historical formation under current availability')


def build_contract(frame, selector, *, scope, source_hash, model_data_at):
    f=validate_frame(frame).reset_index(drop=True)
    rows=[];teams=[]
    for _,g in f.groupby(['season','fixture_uuid','team_id'],sort=True):
        chosen=selector.choose(g);mass=minute_masses(g)
        lo,hi=intervals(mass,.8,'shortest')
        teams.append(dict(season=str(g.season.iloc[0]),fixture_id=str(g.fixture_uuid.iloc[0]),club_id=int(g.team_id.iloc[0]),formation=chosen['formation'],formation_distribution=chosen['formation_distribution'],status=chosen['status'],last_role_known_at=str(chosen['last_known_at']) if chosen['last_known_at'] is not None else None))
        for i,r in enumerate(g.itertuples()):
            pid=str(r.player_uuid);pr=chosen['profiles'][pid];slot=chosen['assignments'].get(pid)
            rows.append(dict(player_id=pid,club_id=int(r.team_id),fixture_id=str(r.fixture_uuid),season=str(r.season),gw=int(r.gw),forecast_at=str(r.cutoff),data_at=str(model_data_at),normal_role=str(getattr(r,'prior_type','unknown')),primary_role=pr['primary'],secondary_role=pr['secondary'],role_probabilities=pr['probabilities'],role_status=pr['status'],formation=chosen['formation'],expected_xi=bool(slot),slot=slot['slot'] if slot else None,slot_index=slot['slot_index'] if slot else None,p_start=float(r.p),p_sub_given_not_start=float(r.q),start_minutes=float(r.s),sub_minutes=float(r.c),xmins=float(r.x),minute_probabilities=[float(mass[i,0]),float(mass[i,1:16].sum()),float(mass[i,16:61].sum()),float(mass[i,61:].sum())],minute_pmf=mass[i].tolist(),interval80=[int(lo[i]),int(hi[i])],interval_method='shortest contiguous, at least nominal model mass',uncertainty_status='experimental, not independently calibrated',availability=str(getattr(r,'news_state','UNKNOWN')),model_version=VERSION))
    doc=dict(contract=CONTRACT,model_version=VERSION,scope=scope,locked_model_active=False,independently_validated=False,source_sha256=source_hash,data_at=str(model_data_at),teams=teams,players=rows)
    doc['content_sha256']=hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return doc
