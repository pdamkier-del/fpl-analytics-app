"""Offline player-first PM. No production imports or changed scoring rules.

Gamma intervals are conditional EB/quasi-Poisson intervals, NOT complete
uncertainty about roles, xG provider, parameters, or lineups.
"""
from contextlib import contextmanager
from dataclasses import replace
import numpy as np
import pandas as pd
from scipy.stats import gamma
from . import joint_simulator


def posterior(y, exposure, prior, strength):
    if not np.isfinite([y, exposure, prior, strength]).all() or min(y, exposure, prior)<0 or strength<=0:
        raise ValueError('Invalid profile evidence')
    shape=y+strength*prior; rate=exposure+strength
    return dict(mean=float(shape/rate), sd=float(np.sqrt(shape)/rate),
                interval95=gamma.ppf([.025,.975],shape,scale=1/rate).tolist() if shape>0 else [0.,0.],
                shape=float(shape),rate=float(rate))


def team_context(obs, cut, season, team, opponent, home, strength=10.):
    """All context uses completed observations BEFORE cut. IDs scoped by season."""
    h=obs[obs.known<cut]
    if h.empty:raise ValueError('No prior context')
    keys=['season','fixture_uuid','team_id','opponent_team_id','was_home']
    t=h.groupby(keys,as_index=False).agg(xg=('xg','sum'),xa=('xa','sum'))
    lg=float(t.xg.mean());la=float(t.xa.mean())
    current=t[t.season.eq(season)]
    opposition=current[current.team_id.eq(opponent)]
    conceded=opposition[['season','fixture_uuid','opponent_team_id']].merge(t[['season','fixture_uuid','team_id','xg']],left_on=['season','fixture_uuid','opponent_team_id'],right_on=['season','fixture_uuid','team_id'],validate='one_to_one')
    defense=(float(conceded.xg.sum())+strength*lg)/(len(conceded)+strength)/lg
    sides=t[t.was_home.eq(int(home))]
    venue=(float(sides.xg.sum())+strength*lg)/(len(sides)+strength)/lg
    own=current[current.team_id.eq(team)]
    return dict(opponent=float(defense),venue=float(venue),
                xa_anchor=float((own.xa.sum()+strength*la)/(len(own)+strength)),
                xg_anchor=float((own.xg.sum()+strength*lg)/(len(own)+strength)),
                matches=len(own),opponent_matches=len(conceded))


def historical_opponent_offsets(obs):
    """Causal fixed offsets; update only after the source's proxy known time.

    No target xG enters its own exposure. Neutral factor one is an explicit
    cold-history prior; it is not an invented observation.
    """
    t=obs.groupby(['season','fixture_uuid','team_id','opponent_team_id','was_home','known','kickoff_at'],as_index=False).xg.sum()
    opp=t[['season','fixture_uuid','team_id','xg']].rename(columns={'team_id':'opponent_team_id','xg':'against'})
    t=t.merge(opp,on=['season','fixture_uuid','opponent_team_id'],validate='one_to_one')
    t['kick']=pd.to_datetime(t.kickoff_at,utc=True);t=t.sort_values(['kick','fixture_uuid','team_id'])
    pending=sorted(t.to_dict('records'),key=lambda r:r['known']);j=0;by={};lg=0.;n=0;venue={0:[0.,0],1:[0.,0]};rows=[]
    for r in t.to_dict('records'):
        while j<len(pending) and pending[j]['known']<r['kick']:
            z=pending[j];key=(z['season'],int(z['team_id']));s=by.setdefault(key,[0.,0]);s[0]+=z['against'];s[1]+=1;lg+=z['xg'];n+=1
            v=venue[int(z['was_home'])];v[0]+=z['xg'];v[1]+=1;j+=1
        if n==0:factor=1.
        else:
            mean=lg/n;s=by.get((r['season'],int(r['opponent_team_id'])),[0.,0]);v=venue[int(r['was_home'])]
            factor=((s[0]+10*mean)/(s[1]+10)/mean)*((v[0]+10*mean)/(v[1]+10)/mean) if mean>0 else 1.
        rows.append(dict(season=r['season'],fixture_uuid=r['fixture_uuid'],team_id=r['team_id'],opponent_offset=factor))
    return pd.DataFrame(rows)


class ProfileFit:
    def __init__(self, obs, cut, season, half=365., strength=10., hierarchical=True):
        self.cut=pd.Timestamp(cut);self.season=season;self.strength=float(strength);self.hierarchical=hierarchical
        h=obs[obs.known<self.cut].copy()
        if h.empty:raise ValueError('No past profile observations')
        if 'opponent_offset' not in h:raise ValueError('Missing causal opponent offsets')
        h['role']=h.fpl_position.replace({'GKP':'GK','G':'GK'})
        h['w']=np.exp2(-(self.cut-h.known).dt.total_seconds()/86400/half)
        h['exposure']=h.minutes/90*h.opponent_offset
        self.history=h;self.maximum_known=str(h.known.max())
        cols=['xg','xa','goals','fpl_assists','minutes','exposure']
        weighted=h[cols].mul(h.w,axis=0);weighted['player_uuid']=h.player_uuid;weighted['role']=h.role;weighted['team_id']=h.team_id;weighted['season']=h.season
        self.players=weighted.groupby(['player_uuid','role'])[cols].sum()
        self.positions=weighted.groupby('role')[cols].sum()
        self.teams=weighted[weighted.season.eq(season)].groupby(['team_id','role'])[cols].sum()
        self.by_player={str(pid):g for pid,g in h.groupby('player_uuid')}
        self.cache={}

    def profile(self, p):
        cache_key=(str(p.player_id),str(p.position),str(p.team))
        if cache_key in self.cache:return self.cache[cache_key]
        role='GK' if p.position in ['GK','GKP','G'] else p.position
        if role not in self.positions.index:raise ValueError('Unavailable role prior')
        pop=self.positions.loc[role];key=(str(p.player_id),role)
        row=self.players.loc[key] if key in self.players.index else pd.Series({c:0. for c in ['xg','xa','goals','fpl_assists','minutes','exposure']})
        team=self.teams.loc[(int(p.team),role)] if (int(p.team),role) in self.teams.index else None
        out={}
        for field in ['xg','xa']:
            prior=float(pop[field]/pop.exposure) if pop.exposure>0 else 0.
            if self.hierarchical and team is not None:
                prior=posterior(float(team[field]),float(team.exposure),prior,4*self.strength)['mean']
            out[field+'90']=posterior(float(row[field]),float(row.exposure),prior,self.strength)
        # Calibration proxy: all-xG contains penalty xG; no isolated skill claim.
        out['finishing']=posterior(float(row.goals),float(row.xg),1.,20.)
        out['assist_conversion']=posterior(float(row.fpl_assists),float(row.xa),1.,20.)
        g=self.by_player.get(str(p.player_id),self.history.iloc[:0]).sort_values(['known','fixture_uuid']);played=g[g.minutes.gt(0)]
        last=g.tail(6);old_team=int(g.iloc[-1].team_id) if len(g) else None
        old_role=str(g.iloc[-1].role) if len(g) else None
        current=g[g.season.eq(self.season)].tail(6)
        moved=bool(len(current) and (int(current.iloc[-1].team_id)!=int(p.team) or current.team_id.nunique()>1))
        out.update(weighted_minutes=float(row.minutes),history_rows=len(g),role=role,last_team=old_team,
                   club_change=moved,role_change=old_role is not None and (old_role!=role or last.role.nunique()>1),
                   group='regular' if len(last)==6 and last.started.eq(1).all() else ('reserve' if len(last)>=3 and last.started.mean()<=.2 else 'rotation_or_short'),
                   limited_history=bool(row.minutes<450),maximum_known=self.maximum_known,
                   set_piece='Not Available: no cutoff-certified role order in these test seasons',
                   creator_receiver='Not Available: no failed-shot creator links')
        # Descriptive defensive/BPS profiles only. Never overwrite locked BPS.
        for field in ['defcon_count','tackles','recoveries','clearances_blocks_interceptions','saves','bps']:
            v=g[g[field].notna() & g.minutes.gt(0)] if field in g else g.iloc[:0]
            if not len(v):out[field+'90']=None
            else:
                weights=v.w.to_numpy();rates=90*v[field].to_numpy()/v.minutes.to_numpy()
                out[field+'90']=dict(mean=float(np.average(rates,weights=weights)),observations=len(v),
                    weighted_rate_sd=float(np.sqrt(np.average((rates-np.average(rates,weights=weights))**2,weights=weights))),
                    used_in_scoring=False,note='Raw rate, includes outcome/context effects; original simulator component retained')
        self.cache[cache_key]=out
        return out


def expected_exposure(p):
    return (p.p_start*p.start_minutes_mean+(1-p.p_start)*p.p_cameo_given_bench*p.cameo_minutes_mean)/90


def prepare(inp, fit, contexts, anchor_weight=0., creativity=0., finishing=True):
    if not 0<=anchor_weight<=1 or creativity<0:raise ValueError('Invalid player PM mixing')
    profiles={p.player_id:fit.profile(p) for p in inp.players}
    players=tuple(replace(p,goal_weight=profiles[p.player_id]['xg90']['mean']*(profiles[p.player_id]['finishing']['mean'] if finishing else 1.),
                          assist_weight=profiles[p.player_id]['xa90']['mean']) for p in inp.players)
    spec=dict(profiles=profiles,contexts=contexts,anchor_weight=anchor_weight,creativity=creativity,finishing=finishing)
    return replace(inp,players=players),spec


def lineup_rates(inp, spec, exposure):
    """90 piecewise constant rates. Individual intensities sum to total exactly.

    exposure maps player_id to scalar expected exposure or a 90-vector of
    sampled on-pitch indicators. Opponent strength is applied exactly once.
    """
    result={};all_players={}
    for team,anchor,pen,conv in [(inp.home_team,inp.lambda_home_goals,inp.lambda_home_penalties,inp.home_penalty_conversion),(inp.away_team,inp.lambda_away_goals,inp.lambda_away_penalties,inp.away_penalty_conversion)]:
        ps=[p for p in inp.players if p.team==team];c=spec['contexts'][str(team)];pr=spec['profiles']
        e=np.array([np.broadcast_to(exposure[p.player_id],(90,)) for p in ps]);g=np.array([pr[p.player_id]['xg90']['mean'] for p in ps])[:,None]*e
        a=np.array([pr[p.player_id]['xa90']['mean'] for p in ps])[:,None]*e
        mult=c['opponent']*c['venue'];raw=g.sum(0)*mult;qa=a.sum(0)*mult
        h=spec['anchor_weight'];chance=(1-h)*raw+h*anchor
        if spec['creativity']:
            denom=c['xa_anchor']*mult
            if denom<=0:raise ValueError('Unavailable creative anchor')
            chance*=np.power(qa/denom,spec['creativity'])
        theta=np.array([pr[p.player_id]['finishing']['mean'] if spec['finishing'] else 1. for p in ps])[:,None]
        weighted=g*theta;den=g.sum(0);effective=np.divide(weighted.sum(0),den,out=np.ones(90),where=den>0)
        ordinary=np.maximum(0,chance-pen*conv)*effective
        # No active ordinary scorer means no ordinary goal, even in hybrid.
        ordinary=np.where(weighted.sum(0)>0,ordinary,0.)
        share=np.divide(weighted,weighted.sum(0),out=np.zeros_like(weighted),where=weighted.sum(0)>0)
        individual=share*ordinary
        if not np.allclose(individual.sum(0),ordinary,atol=1e-12):raise ValueError('Goal conservation failed')
        result[str(team)]=dict(xg=float(chance.mean()),ordinary=float(ordinary.mean()),total=float(ordinary.mean()+pen*conv),bins=ordinary.tolist(),active_exposure=float(e.mean(1).sum()))
        for i,p in enumerate(ps):all_players[p.player_id]=float(individual[i].mean())
    return result,all_players


@contextmanager
def shadow_player_intensity(spec, diagnostics=None):
    """Original event simulator/scoring, player-dependent ordinary Poisson/time.

    Serial offline context only. First two Poisson draws and their ordinary
    timestamps are replaced. Penalty process, minutes, discipline, BPS and
    scoring functions retain their original code. Restored even on exception.
    """
    saved_match=joint_simulator.simulate_match;saved_minutes=joint_simulator._sample_minutes
    intervals={};active_input=[None];diag=diagnostics if diagnostics is not None else {}
    def minutes(rng,p):
        val=saved_minutes(rng,p);intervals[p.player_id]=val;return val
    class RandomProxy:
        def __init__(self,rng):self.rng=rng;self.calls=0;self.queue=[];self.rates=None
        def __getattr__(self,k):return getattr(self.rng,k)
        def poisson(self,lam,*args,**kwargs):
            if self.calls<2:
                if args or kwargs:raise ValueError('Unexpected ordinary Poisson signature')
                if self.rates is None:
                    exposure={pid:((np.arange(90)+.5>=v[1]) & (np.arange(90)+.5<v[2]) & (v[0]>0)).astype(float) for pid,v in intervals.items()}
                    self.rates,_=lineup_rates(active_input[0],spec,exposure)
                team=[active_input[0].home_team,active_input[0].away_team][self.calls];r=self.rates[str(team)];n=int(self.rng.poisson(r['ordinary']));self.queue.extend([np.asarray(r['bins'])]*n);self.calls+=1
                d=diag.setdefault(str(team),dict(draws=0,xg_sum=0.,goal_mean_sum=0.,exposure_sum=0.));d['draws']+=1;d['xg_sum']+=r['xg'];d['goal_mean_sum']+=r['total'];d['exposure_sum']+=r['active_exposure']
                return n
            return self.rng.poisson(lam,*args,**kwargs)
        def uniform(self,low=0.,high=1.,size=None):
            if self.queue:
                if low!=0 or high!=90 or size is not None:raise ValueError('Unexpected goal-time request')
                bins=self.queue.pop(0);u=float(self.rng.uniform(0,90))/90;cdf=np.cumsum(bins);q=u*cdf[-1];i=min(int(np.searchsorted(cdf,q,side='right')),89);before=cdf[i-1] if i else 0.
                return i+(q-before)/bins[i]
            return self.rng.uniform(low,high,size)
    def match(inp,rng):
        intervals.clear();active_input[0]=inp
        return saved_match(inp,RandomProxy(rng))
    try:
        joint_simulator._sample_minutes=minutes;joint_simulator.simulate_match=match
        yield diag
    finally:
        joint_simulator._sample_minutes=saved_minutes;joint_simulator.simulate_match=saved_match
