"""Opt-in B normal-match timeline, not independent cameos.

No fitted parameters or production activation. Finite conditional ensembles
define the same analytical MM marginals and PM sampling law. Original start
marginals and the existing exclusive goalkeeper process are retained.
"""
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache
import numpy as np
from scipy.special import ndtr, ndtri
from scipy.stats import qmc

from .experimental_mean_preserving_minutes import normal_location


def decompose_starts(ids, probability):
    """Exact convex decomposition of the ten-starter uniform-matroid polytope."""
    p=np.asarray(probability,float).copy();remaining=1.;rows=[]
    if len(p)<10 or not np.isfinite(p).all() or (p<0).any() or (p>1).any() or abs(p.sum()-10)>1e-6:
        raise ValueError('Ten valid outfield start marginals required')
    fixed=np.flatnonzero(p==1);excluded=p==0
    for _ in range(len(p)+2):
        # The upstream projection allows sub-micro numerical mass residuals.
        # Remove those from fractional entries, never from hard endpoints.
        delta=10-float(p.sum())
        free=np.flatnonzero((p>0)&(p<1))
        for j in free:
            if abs(delta)<1e-14:break
            step=float(np.clip(delta,-p[j],1-p[j]));p[j]+=step;delta-=step
        candidates=np.flatnonzero(~excluded & ~np.isin(np.arange(len(p)),fixed))
        chosen=np.r_[fixed,candidates[np.argsort(-p[candidates],kind='stable')[:10-len(fixed)]]]
        if remaining<=1e-10:
            rows.append((tuple(sorted(ids[i]for i in chosen)),remaining));remaining=0.;break
        outside=np.ones(len(p),bool);outside[chosen]=False
        weight=min(float(p[chosen].min()),float((1-p[outside]).min()) if outside.any() else 1.)
        if weight<=1e-12:raise ValueError('Degenerate starter decomposition')
        rows.append((tuple(sorted(ids[i]for i in chosen)),remaining*weight))
        remaining*=1-weight
        if remaining<1e-12:break
        indicator=np.zeros(len(p));indicator[chosen]=1
        p=np.clip((p-weight*indicator)/(1-weight),0,1)
    if remaining>1e-9:raise ValueError('Starter decomposition did not terminate')
    return rows


def _keeper_mass(p):
    if p.goalkeeper_start_pmf is not None:
        return np.asarray(p.goalkeeper_start_pmf,float)
    mean=p.start_minutes_mean
    if mean<=1:mass=np.zeros(91);mass[1]=1.;return mass
    if mean>=90:mass=np.zeros(91);mass[90]=1.;return mass
    cdf=ndtr((np.arange(1,90)+.5-normal_location(mean,10.))/10.)
    return np.r_[0.,cdf[0],np.diff(cdf),1-cdf[-1]]


@lru_cache(maxsize=256)
def _uniforms(n,states):
    u=qmc.Sobol(d=3*n,scramble=True,seed=20261024).random_base2(int(np.log2(states)))
    u.setflags(write=False)
    return u


def _states(players, selected, cap, windows, states):
    n=len(players);ids=[p.player_id for p in players]
    start=np.array([uid in selected for uid in ids]);starters=np.flatnonzero(start)
    bench=np.flatnonzero(~start)
    u=_uniforms(n,states)
    eligible=np.zeros((states,n),bool)
    duration=np.zeros((states,n),int)
    for j in bench:
        # Floor the inclusion count so the finite approximation cannot exceed
        # the caller's conditional availability/cameo ceiling.
        count=int(np.floor(players[j].p_cameo_given_bench*states+1e-10))
        eligible[np.argsort(u[:,j],kind='stable')[:count],j]=True
        c=players[j].cameo_minutes_mean
        if c<=1:duration[:,j]=1
        elif c>=90:duration[:,j]=89
        else:duration[:,j]=np.clip(np.rint(normal_location(c,7.)+7*ndtri(np.clip(u[:,n+j],1e-12,1-1e-12))),1,89).astype(int)
    loss=np.array([max(0.,90-p.start_minutes_mean) for p in players])
    available=start & (loss>1e-10)
    cap=min(cap,int(available.sum()))
    minutes=np.zeros((states,n),np.int16);minutes[:,starters]=90
    if cap:
        priority=-np.log(np.clip(u[:,2*n:],1e-12,1.))/np.maximum([p.p_cameo_given_bench for p in players],1e-12)
        incoming=np.argsort(np.where(eligible,priority,np.inf),axis=1,kind='stable')[:,:cap]
        count=np.minimum(eligible.sum(axis=1),cap)
        exit_priority=-np.log(np.clip(u[:,:n],1e-12,1.))/np.maximum(loss,1e-12)
        outgoing=np.argsort(np.where(available,exit_priority,np.inf),axis=1,kind='stable')[:,:cap]
        valid=np.arange(cap)[None,:]<count[:,None]
        values=np.take_along_axis(duration,incoming,axis=1)
        order=np.argsort(np.where(valid,values,np.inf),axis=1,kind='stable')
        total=np.take_along_axis(values,order,axis=1)*valid
        size=valid.astype(int)
        members=np.eye(cap,dtype=np.int16)[order]*valid[:,:,None]
        remaining=count.copy()
        # Integer group sums reproduce exactly the previous per-row mean,
        # including half-integer rounding and stable tie resolution.
        while (remaining>windows).any():
            active=np.flatnonzero(remaining>windows)
            means=total/np.maximum(size,1)
            gap=np.diff(means[active],axis=1)
            gap=np.where(np.arange(cap-1)[None,:]<remaining[active,None]-1,gap,np.inf)
            j=np.argmin(gap,axis=1)
            total[active,j]+=total[active,j+1];size[active,j]+=size[active,j+1]
            members[active,j]|=members[active,j+1]
            for column in range(cap-1):
                rows=active[j<column]
                total[rows,column]=total[rows,column+1];size[rows,column]=size[rows,column+1]
                members[rows,column]=members[rows,column+1]
            total[active,-1]=0;size[active,-1]=0;members[active,-1]=0
            remaining[active]-=1
        rounded=np.rint(total/np.maximum(size,1)).astype(int)
        actual=(rounded[:,:,None]*members).sum(axis=1)
        rows,columns=np.where(valid)
        minutes[rows,incoming[rows,columns]]=actual[rows,columns]
        minutes[rows,outgoing[rows,columns]]=90-actual[rows,columns]
    if not (minutes.sum(axis=1)==900).all() or ((minutes>0).sum(axis=1)>10+cap).any():
        raise AssertionError('Physical conditional ensemble invalid')
    return minutes,start


class PhysicalKernel:
    def __init__(self,inp,role_distributions=None,*,states=128):
        if states<2 or states&(states-1):raise ValueError('Power-of-two state count required')
        if not inp.experimental_joint_goalkeepers or not inp.experimental_mean_preserving_minutes:
            raise ValueError('Physical candidate requires the existing B GK/minute contract')
        from .joint_simulator import validate_joint_goalkeepers
        if len({p.player_id for p in inp.players})!=len(inp.players):
            raise ValueError('Duplicate physical player identity')
        self.input=inp
        self.audit=dict(version='B-normal-timeline-v1',clock='normalized_regulation_0_90',
            scope='normal match before dismissal/removal events',draws=0,
            physical_outfield_minutes=900,physical_keeper_minutes=90,
            paired_entry_exit=True,substitution_limit=5,window_limit=3,
            reported_FPL_minutes_required_to_sum_990=False,
            physical_to_FPL_clock_calibrated=False,red_card_removals_modeled=False,
            concussion_exceptions_modeled=False,max_substitutions=0,max_windows=0)
        self.teams={};self.moments={};role_distributions=role_distributions or {}
        for team in (inp.home_team,inp.away_team):
            field=sorted((p for p in inp.players if p.team==team and not p.is_keeper),key=lambda p:p.player_id)
            keepers=tuple(p for p in inp.players if p.team==team and p.is_keeper)
            validate_joint_goalkeepers(keepers,team,inp.verified_goalkeeper_roster_teams)
            ids=tuple(p.player_id for p in field)
            given=role_distributions.get(int(team),role_distributions.get(str(team))) if str(team).isdigit() else role_distributions.get(team)
            raw=[(tuple(sorted(r.players)),r.weight)for r in given] if given else decompose_starts(ids,[p.p_start for p in field])
            weights=defaultdict(float)
            for selected,w in raw:
                if len(selected)!=10 or len(set(selected))!=10 or not set(selected)<=set(ids) or not np.isfinite(w) or w<0:
                    raise ValueError('Invalid physical starter mixture')
                weights[selected]+=w
            if abs(sum(weights.values())-1)>1e-7:raise ValueError('Starter weights do not sum to one')
            marginal=np.array([sum(w for s,w in weights.items()if uid in s)for uid in ids])
            if not np.allclose(marginal,[p.p_start for p in field],atol=1e-6,rtol=0):
                raise ValueError('Physical kernel would change starter marginals')
            swap=float(sum(p.p_start*(1-_keeper_mass(p)[90])for p in keepers))
            pmf=np.zeros((len(field),91));ensembles={}
            for selected,w in sorted(weights.items()):
                for changed,prob in [(False,1-swap),(True,swap)]:
                    if prob<=1e-14:continue
                    minutes,start=_states(field,selected,4 if changed else 5,2 if changed else 3,states)
                    ensembles[selected,changed]=(minutes,start)
                    for j in range(len(field)):
                        pmf[j]+=w*prob*np.bincount(minutes[:,j],minlength=91)/states
            for j,p in enumerate(field):
                pstart=float(marginal[j]);play=float(1-pmf[j,0]);mean=float(pmf[j]@np.arange(91))
                start_mean=sum(w*prob*float(ensembles[s,b][0][:,j].mean()) for s,w in weights.items()if p.player_id in s
                               for b,prob in [(False,1-swap),(True,swap)]if (s,b)in ensembles)/pstart if pstart else p.start_minutes_mean
                bench_mass=max(0.,play-pstart)
                cameo=(mean-pstart*start_mean)/bench_mass if bench_mass>1e-12 else p.cameo_minutes_mean
                q=max(0.,bench_mass/(1-pstart))if pstart<1-1e-12 else 0.
                if play>p.p_start+(1-p.p_start)*p.p_cameo_given_bench+2e-6:
                    raise AssertionError('Physical process exceeded availability ceiling')
                self.moments[p.player_id]=dict(p=pstart,q=q,s=float(start_mean),c=float(cameo),x=mean,
                    p_play=play,p60=float(pmf[j,60:].sum()),p90=float(pmf[j,90]),pmf=pmf[j].tolist())
            self.teams[team]=dict(field=field,keepers=keepers,weights=weights,ensembles=ensembles)
        for team,data in self.teams.items():
            if abs(sum(self.moments[p.player_id]['x']for p in data['field'])-900)>1e-6:
                raise AssertionError('Physical analytical minute budget differs from 900')

    def sample(self,rng):
        from .joint_simulator import _weighted_choice
        timeline={}
        for team,data in self.teams.items():
            gks=data['keepers'];starter=_weighted_choice(rng,gks,[p.p_start for p in gks])
            mass=_keeper_mass(starter);duration=int(rng.choice(len(mass),p=mass))
            for p in gks:timeline[p.player_id]=(0,90,90)
            timeline[starter.player_id]=(duration,0,duration)
            changed=duration<90
            if changed:
                remaining=[p for p in gks if p.player_id!=starter.player_id and p.p_cameo_given_bench>0]
                sub=_weighted_choice(rng,remaining,[p.p_cameo_given_bench for p in remaining])
                if sub is None:raise ValueError('No available replacement goalkeeper')
                timeline[sub.player_id]=(90-duration,duration,90)
            rows=list(data['weights']);selected=rows[int(rng.choice(len(rows),p=list(data['weights'].values())))];ensemble,start=data['ensembles'][selected,changed]
            minutes=ensemble[int(rng.integers(len(ensemble)))]
            for j,p in enumerate(data['field']):
                m=int(minutes[j]);timeline[p.player_id]=(m,0,m)if start[j]else(m,90-m,90)
        validate_timeline(self.input,timeline)
        self.audit['draws']+=1
        for team in (self.input.home_team,self.input.away_team):
            ps=[p for p in self.input.players if p.team==team]
            arrivals=[timeline[p.player_id][1]for p in ps
                      if timeline[p.player_id][0]>0 and timeline[p.player_id][1]>0]
            self.audit['max_substitutions']=max(self.audit['max_substitutions'],len(arrivals))
            self.audit['max_windows']=max(self.audit['max_windows'],len(set(arrivals)-{45}))
        return timeline


def validate_timeline(inp,timeline):
    if set(timeline)!={p.player_id for p in inp.players}:raise ValueError('Incomplete physical timeline')
    for team in (inp.home_team,inp.away_team):
        ps=[p for p in inp.players if p.team==team];field=[p for p in ps if not p.is_keeper];gks=[p for p in ps if p.is_keeper]
        for p in ps:
            m,a,b=timeline[p.player_id]
            if not 0<=a<=b<=90 or m!=b-a or int(m)!=m:raise ValueError('Invalid physical player interval')
        if sum(timeline[p.player_id][0]for p in field)!=900 or sum(timeline[p.player_id][0]for p in gks)!=90:
            raise ValueError('Physical minute coverage failed')
        if sum(timeline[p.player_id][0]>0 for p in ps)>16:raise ValueError('More than five substitutions')
        windows={timeline[p.player_id][1]for p in ps if timeline[p.player_id][0]>0 and timeline[p.player_id][1]>0}
        if len(windows-{45})>3:raise ValueError('More than three substitution windows')
        cuts=sorted({0,90}|windows|{timeline[p.player_id][2]for p in ps if timeline[p.player_id][0]>0})
        for a,b in zip(cuts,cuts[1:]):
            t=(a+b)/2
            if sum(timeline[p.player_id][1]<=t<timeline[p.player_id][2]for p in field)!=10 or sum(timeline[p.player_id][1]<=t<timeline[p.player_id][2]for p in gks)!=1:
                raise ValueError('Physical active-player coverage failed')
    return True


@contextmanager
def physical_sampler(kernel):
    from . import joint_simulator as simulator
    original=simulator.simulate_match
    def sample(inp,rng,*,trace=None):
        if inp!=kernel.input:raise ValueError('Physical kernel belongs to different fixture inputs')
        return original(inp,rng,trace=trace,timeline=kernel.sample(rng))
    simulator.simulate_match=sample
    try:yield
    finally:simulator.simulate_match=original
