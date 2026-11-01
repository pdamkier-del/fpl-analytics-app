"""Opt-in B role/importance assignment distribution. No default model imports.

A fractional matching, including the outside/bench outcome, determines start
marginals before PM. Birkhoff decomposition supplies the same marginals as
whole, distinct-player lineups. Injury caps are explicit constraints. There is
no player-specific override and no manual allocation of spare start mass.
"""
from dataclasses import dataclass,replace
from contextlib import contextmanager
import numpy as np
from scipy.optimize import minimize,linear_sum_assignment,least_squares
from scipy.special import logsumexp,expit,logit
from .role_classifier import ROLES,role_family
from .xi_assignment import formation_slots


@dataclass(frozen=True)
class RoleLineup:
    weight:float
    formation:str
    players:tuple[str,...]
    roles:tuple[str,...]


def role_scores(players,formation,importance):
    """Historical evidence/explicit uninformative prior, never target outcomes."""
    if not np.isfinite(importance)or not 0<=importance<=1:raise ValueError('Importance outside [0,1]')
    slots=[s.role for s in formation_slots(formation)if s.role!='GK']
    possible=[r for r in ROLES if r!='GK'];scores=[]
    for p in players:
        q=dict(p.get('q')or{});h=dict(p.get('H')or{})
        if any(not np.isfinite(v)or v<0 for v in [*q.values(),*h.values()]):raise ValueError('Invalid role evidence')
        if q and (set(q)-set(possible)or sum(q.values())<=0):raise ValueError('Invalid outfield roles')
        q={r:v/sum(q.values())for r,v in q.items()}if q else {r:1/len(possible)for r in possible}
        reference=1/max(10,len(players));row=[]
        for slot in slots:
            exact=q.get(slot,0);family=sum(v for r,v in q.items()if role_family(r)==role_family(slot))
            compat=.02+.78*exact+.20*family
            hierarchy=h.get(slot,reference)
            row.append(np.log(compat)+importance*np.log((.05+hierarchy)/(.05+reference)))
        scores.append(row)
    return np.asarray(scores,float),tuple(slots)


def fractional_assignment(priors,scores,*,caps=None,strength=1.):
    """Entropy transport with a bench outcome and row availability bounds.

    At strength zero and feasible sum(priors)==slots, priors are preserved.
    At nonzero strength each player's marginal depends on the whole competing
    roster/role score matrix. Solving only ten column duals keeps this small.
    """
    p=np.asarray(priors,float);scores=np.asarray(scores,float);cap=np.ones(len(p))if caps is None else np.asarray(caps,float)
    if p.ndim!=1 or scores.ndim!=2 or scores.shape[0]!=len(p)or cap.shape!=p.shape:raise ValueError('Assignment shape mismatch')
    k=scores.shape[1]
    if k<1 or len(p)<k or not np.isfinite(np.r_[p,cap,scores.ravel(),strength]).all():raise ValueError('Invalid assignment input')
    if (p<0).any()or(p>1).any()or(cap<0).any()or(cap>1).any()or(p>cap+1e-9).any()or strength<0:raise ValueError('Invalid start/cap support')
    effective=np.where(p>0,cap,0.);fixed=p==1
    if fixed.sum()>k or effective.sum()<k-1e-9:raise ValueError('No available role assignment')
    if fixed.sum()==k:effective=np.where(fixed,1.,0.)
    all_caps=abs(effective.sum()-k)<1e-10
    raw=logit(np.clip(p,1e-12,1-1e-12))[:,None]+strength*scores
    def values(alpha):
        z=raw+alpha;den=logsumexp(z,axis=1);share=np.exp(z-den[:,None])
        selection=np.minimum(expit(den),effective);selection[fixed]=1.
        if all_caps:selection=effective.copy()
        selection[effective==0]=0.
        phi=np.logaddexp(0,den)
        bounded=(expit(den)>effective)&(effective>0)&(effective<1)
        u=effective[bounded];phi[bounded]=u*den[bounded]-u*np.log(u)-(1-u)*np.log1p(-u)
        phi[fixed]=den[fixed];phi[effective==0]=0.
        if all_caps:phi=effective*den
        x=selection[:,None]*share
        return float(phi.sum()-alpha.sum()),x.sum(axis=0)-1,x
    initial=np.full(k,-np.log(k))
    fit=minimize(lambda a:values(a)[:2],initial,jac=True,method='L-BFGS-B',options={'maxiter':2000,'ftol':1e-15,'gtol':1e-11,'maxls':50})
    _,grad,x=values(fit.x)
    # L-BFGS may stop on tiny objective changes while a column is still off
    # by a few 1e-7. Refine the ten column constraints directly; never repair
    # them by rescaling rows (which would alter injury bounds and marginals).
    if np.max(abs(grad))>5e-9:
        refined=least_squares(lambda a:values(a)[1],fit.x,
                              ftol=1e-13,xtol=1e-13,gtol=1e-13,max_nfev=200)
        _,grad,x=values(refined.x)
    if np.max(abs(grad))>2e-7:raise ValueError('Role transport did not converge: '+str(np.max(abs(grad))))
    if (x.sum(axis=1)>cap+1e-8).any():raise ValueError('Role transport exceeded availability')
    return x


def decompose_assignment(x,ids,roles,formation,*,tolerance=2e-7):
    """Complete rectangular matching with bench columns, then decompose.

    The resulting lineup mixture, rather than an independently rounded roster,
    is the canonical start distribution. Rounding residuals are bounded.
    """
    x=np.asarray(x,float);ids=tuple(map(str,ids));roles=tuple(roles)
    if x.shape!=(len(ids),len(roles))or len(set(ids))!=len(ids):raise ValueError('Duplicate/incorrect assignment identity')
    if not np.isfinite(x).all()or(x<0).any()or(x.sum(axis=1)>1+1e-7).any()or not np.allclose(x.sum(axis=0),1,atol=tolerance,rtol=0):raise ValueError('Invalid fractional role assignment')
    active=np.flatnonzero(x.sum(axis=1)>1e-14);z=x[active].copy();n,k=z.shape
    if n<k:raise ValueError('Too few active role candidates')
    bench=np.maximum(0,1-z.sum(axis=1))
    square=np.c_[z,np.repeat((bench/(n-k))[:,None],n-k,axis=1)]if n>k else z
    residual=square.copy();parts={};remaining=1.
    for _ in range(n*n+2):
        if remaining<tolerance:break
        costs=np.where(residual>1e-14,-residual,np.inf)
        try:a,b=linear_sum_assignment(costs)
        except ValueError:
            if remaining<=tolerance:break
            raise ValueError('No supported role decomposition at residual '+str(remaining))
        mass=float(residual[a,b].min())
        if mass<=0:raise ValueError('Zero decomposition component')
        real=sorted([(int(col),int(row))for row,col in zip(a,b)if col<k]);selected=tuple(ids[int(active[row])]for col,row in real)
        if len(selected)!=k or len(set(selected))!=k:raise ValueError('Invalid whole-lineup assignment')
        parts[selected]=parts.get(selected,0.)+mass;residual[a,b]-=mass;residual=np.maximum(residual,0);remaining-=mass
    if remaining>tolerance:raise ValueError('Role decomposition left excess mass')
    total=sum(parts.values());lineups=tuple(RoleLineup(w/total,formation,p,roles)for p,w in parts.items())
    actual=lineup_marginals(lineups,ids)
    if np.max(abs(actual-x.sum(axis=1)))>tolerance*2:raise ValueError('Decomposition changed start means')
    return lineups


def lineup_marginals(lineups,ids):
    index={str(p):i for i,p in enumerate(ids)};p=np.zeros(len(ids));total=0.
    for row in lineups:
        if not np.isfinite(row.weight)or row.weight<0 or len(row.players)!=len(row.roles)or len(set(row.players))!=len(row.players):raise ValueError('Invalid role lineup')
        for uid in row.players:p[index[uid]]+=row.weight
        total+=row.weight
    if abs(total-1)>1e-7:raise ValueError('Lineup weights not normalized')
    return p


def build_role_distribution(players,formations,importance,*,strength):
    """Mix prior observed formation alternatives; hard endpoints are retained."""
    ids=[str(p['player_uuid'])for p in players];priors=np.array([p['base_p_start']for p in players]);caps=np.array([p.get('availability_cap',1.)for p in players])
    if not formations or any(not np.isfinite(w)or w<0 for w in formations.values())or sum(formations.values())<=0:raise ValueError('Missing historical formations')
    total=sum(formations.values());result=[]
    for form,weight in sorted(formations.items()):
        if not weight:continue
        scores,roles=role_scores(players,form,importance);x=fractional_assignment(priors,scores,caps=caps,strength=strength)
        result.extend(replace(v,weight=v.weight*weight/total)for v in decompose_assignment(x,ids,roles,form))
    result=tuple(result);p=lineup_marginals(result,ids)
    if (p>caps+4e-7).any():raise ValueError('Joint role distribution exceeds cap')
    return result,p


@contextmanager
def role_lineup_sampler(team_distributions):
    """Isolated B subprocess hook; default simulator and GK kernel unchanged."""
    from . import joint_simulator as simulator
    original=simulator.simulate_match
    choices={str(t):(tuple(rows),np.array([r.weight for r in rows],float))for t,rows in team_distributions.items()}
    for rows,weights in choices.values():
        if not rows or not np.isfinite(weights).all() or (weights<0).any() or abs(weights.sum()-1)>1e-7:raise ValueError('Invalid team role distribution')
        if any(len(r.players)!=10 or len(set(r.players))!=10 or len(r.roles)!=10 or any(role not in ROLES or role=='GK' for role in r.roles) for r in rows):
            raise ValueError('Invalid outfield role lineup')
    checked=set()
    def simulate(inp,rng,*,trace=None):
        if not any(str(t)in choices for t in (inp.home_team,inp.away_team)):
            return original(inp,rng,**({'trace':trace}if trace is not None else{}))
        if not inp.experimental_joint_starters:
            raise ValueError('Role kernel requires the B joint-starter contract')
        selected=set()
        for team in (inp.home_team,inp.away_team):
            if str(team) not in choices:
                # Unknown tactical history retains the existing dependent
                # rounding kernel, rather than inventing a formation.
                from .experimental_correctness_simulator import round_pair
                field=[p for p in inp.players if str(p.team)==str(team)and not p.is_keeper]
                mass=np.array([p.p_start for p in field],float)
                if not np.isfinite(mass).all() or (mass<0).any() or (mass>1).any() or abs(mass.sum()-10)>1e-8:
                    raise ValueError('Outfield start mass must equal ten')
                while True:
                    free=np.flatnonzero((mass>0)&(mass<1))
                    if len(free)<2:break
                    round_pair(mass,int(free[0]),int(free[1]),rng)
                chosen=[p.player_id for p,v in zip(field,mass)if v>.5]
                if len(chosen)!=10:raise ValueError('Fallback XI does not contain ten players')
                selected.update(chosen)
                continue
            rows,weights=choices[str(team)];row=rows[int(rng.choice(len(rows),p=weights))]
            expected={p.player_id for p in inp.players if str(p.team)==str(team)and not p.is_keeper}
            if len(row.players)!=10 or not set(row.players)<=expected:raise ValueError('Role distribution/simulator roster mismatch')
            # Validate the complete mixture before using it, not just the drawn
            # row: a hidden incompatible alternative must not pass by chance.
            signature=(str(team),tuple((p.player_id,p.p_start)for p in inp.players if str(p.team)==str(team)and not p.is_keeper))
            if signature not in checked:
                ids=tuple(sorted(expected))
                if any(not set(r.players)<=expected for r in rows):raise ValueError('Role distribution/simulator roster mismatch')
                marginal=lineup_marginals(rows,ids)
                by={p.player_id:p.p_start for p in inp.players if str(p.team)==str(team)and not p.is_keeper}
                if not np.allclose(marginal,[by[uid]for uid in ids],atol=5e-7,rtol=0):raise ValueError('Role distribution changes MM start marginals')
                checked.add(signature)
            selected.update(row.players)
        players=tuple(p if p.is_keeper else replace(p,p_start=float(p.player_id in selected))for p in inp.players)
        return original(replace(inp,players=players,experimental_joint_starters=False),rng,
                        **({'trace':trace}if trace is not None else{}))
    simulator.simulate_match=simulate
    try:yield
    finally:simulator.simulate_match=original
