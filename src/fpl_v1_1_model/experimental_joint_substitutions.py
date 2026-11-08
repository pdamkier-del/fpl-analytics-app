"""Opt-in hierarchical substitution kernel; original model modules are untouched."""
import hashlib,json
import numpy as np
from scipy.special import expit,logit
from scipy.optimize import linear_sum_assignment
from .experimental_physical_timeline import PhysicalKernel as OriginalKernel
from .experimental_physical_timeline import validate_timeline,_keeper_mass
from .joint_simulator import _weighted_choice

def propensity(p,head,model):
 base=np.clip(p.p_cameo_given_bench,1e-5,1-1e-5)if head=='incoming'else np.clip((90-p.start_minutes_mean)/25,.02,.98)
 x=np.array([1.,logit(base),p.position=='DEF',p.position=='MID'],float);prob=float(expit(x@model['heads'][head]));return prob/(1-prob)
def time_draw(model,event,pos,u):
 item=model['time'][event];personal=item['by_position'].get(pos,[]);pool=item['pool'];w=len(personal)/(len(personal)+20)
 return personal[min(len(personal)-1,int(u/w*len(personal)))]if u<w else pool[min(len(pool)-1,int((u-w)/(1-w)*len(pool)))]
def states(field,selected,gkchanged,nstates,medical,model,seed):
 n=len(field);starter=np.array([p.player_id in selected for p in field]);sidx=np.flatnonzero(starter);bench=np.flatnonzero(~starter);rng=np.random.default_rng(seed);u=rng.random((nstates,n,5));available=np.zeros((nstates,n),bool)
 incoming=np.array([propensity(p,'incoming',model)for p in field]);outgoing=np.array([propensity(p,'outgoing',model)for p in field])
 for j in bench:
  p=field[j];cap=medical[p.player_id];remaining=max(0.,(cap-p.p_start)/(1-p.p_start))if p.p_start<1-1e-12 else 0.
  count=int(np.floor(remaining*nstates+1e-10))if p.p_start+p.p_cameo_given_bench>1e-12 else 0
  available[np.argsort(u[:,j,0],kind='stable')[:count],j]=True
 m=np.zeros((nstates,n),np.int16);m[:,sidx]=90;capacity=4 if gkchanged else 5;windows=2 if gkchanged else 3;pmf=np.asarray(model['count'][:capacity+1]);pmf=pmf/pmf.sum();kdraw=np.searchsorted(np.cumsum(pmf),rng.random(nstates),side='right')
 for z in range(nstates):
  eligible=np.flatnonzero(available[z]);k=min(int(kdraw[z]),len(eligible),capacity)
  if not k:continue
  a=eligible[np.argsort(-np.log(np.maximum(u[z,eligible,1],1e-12))/incoming[eligible],kind='stable')[:k]]
  b=sidx[np.argsort(-np.log(np.maximum(u[z,sidx,2],1e-12))/outgoing[sidx],kind='stable')[:k]]
  # Pairing preference is explicit engineering, not fabricated observed pair labels.
  cost=np.array([[float(field[i].position!=field[j].position)+.01*u[z,j,4]for j in a]for i in b]);ii,jj=linear_sum_assignment(cost);pairs=[(int(b[i]),int(a[j]))for i,j in zip(ii,jj)]
  times=np.array([int(np.clip(np.rint((time_draw(model,'exit',field[o].position,u[z,o,3])+90-time_draw(model,'cameo',field[i].position,u[z,i,3]))/2),1,89))for o,i in pairs])
  groups=[[j]for j in np.argsort(times,kind='stable')]
  while len(groups)>windows:
   means=[float(times[g].mean())for g in groups];j=int(np.argmin(np.diff(means)));groups[j:j+2]=[groups[j]+groups[j+1]]
  for group in groups:
   minute=int(np.clip(np.rint(times[group].mean()),1,89))
   for j in group:o,i=pairs[j];m[z,o]=minute;m[z,i]=90-minute
 assert (m.sum(1)==900).all()
 return m,starter

class JointSubstitutionKernel:
 def __init__(self,inp,dist,medical,fixture,model,conditional_states=128):
  if conditional_states<2 or conditional_states&(conditional_states-1):raise ValueError('Power-of-two conditional state count required')
  required={p.player_id for p in inp.players if not p.is_keeper}
  if not required<=set(medical) or any(not np.isfinite(medical[pid]) or not 0<=medical[pid]<=1 for pid in required):raise ValueError('Explicit finite availability caps required')
  if any(p.p_start>medical[p.player_id]+2e-6 for p in inp.players if not p.is_keeper):raise ValueError('Starter probability exceeds availability cap')
  count=np.asarray(model['count'],float)
  if count.shape!=(6,) or not np.isfinite(count).all() or (count<0).any() or abs(count.sum()-1)>1e-8:raise ValueError('Valid substitution count PMF required')
  self.base=OriginalKernel(inp,dist);self.input=inp;self.teams=self.base.teams;self.audit=dict(self.base.audit);self.audit.update(version='joint-substitution-research-v1',draws=0,max_substitutions=0,max_windows=0);self.moments={};self.ensembles={};self.model=model
  for team,data in self.teams.items():
   field=data['field'];n=len(field);pmf=np.zeros((n,91));start_total=np.zeros(n);swap=sum(p.p_start*(1-_keeper_mass(p)[90])for p in data['keepers'])
   for p in field:assert p.p_start<=medical[p.player_id]+2e-6
   for selected,w in data['weights'].items():
    for changed,prob in [(False,1-swap),(True,swap)]:
     if prob<=1e-14:continue
     seed=int(hashlib.sha256(json.dumps([fixture,str(team),selected,changed],sort_keys=True).encode()).hexdigest()[:16],16)
     m,start=states(field,selected,changed,conditional_states,medical,self.model,seed);self.ensembles[team,selected,changed]=(m,start)
     for j in range(n):pmf[j]+=w*prob*np.bincount(m[:,j],minlength=91)/conditional_states
     start_total+=w*prob*start*m.mean(0)
   for j,p in enumerate(field):
    ps=self.base.moments[p.player_id]['p'];play=float(1-pmf[j,0]);x=float(pmf[j]@np.arange(91));s=float(start_total[j]/ps)if ps>1e-12 else p.start_minutes_mean;bench=max(0.,play-ps);c=float((x-ps*s)/bench)if bench>1e-12 else p.cameo_minutes_mean
    self.moments[p.player_id]={'p':ps,'p_play':play,'x':x,'s':s,'c':c,'q':float(bench/(1-ps))if ps<1-1e-12 else 0.,'p60':float(pmf[j,60:].sum()),'p90':float(pmf[j,90]),'pmf':pmf[j].tolist()}
    assert play<=medical[p.player_id]+2e-6
   assert abs(sum(self.moments[p.player_id]['x']for p in field)-900)<1e-6
   assert abs(sum(self.moments[p.player_id]['p90']+self.moments[p.player_id]['p_play']for p in field)-20)<1e-6
 def sample(self,rng):
  timeline={}
  for team,data in self.teams.items():
   gks=data['keepers'];starter=_weighted_choice(rng,gks,[p.p_start for p in gks]);mass=_keeper_mass(starter);duration=int(rng.choice(len(mass),p=mass))
   for p in gks:timeline[p.player_id]=(0,90,90)
   timeline[starter.player_id]=(duration,0,duration);changed=duration<90
   if changed:
    reserves=[p for p in gks if p.player_id!=starter.player_id and p.p_cameo_given_bench>0];reserve=_weighted_choice(rng,reserves,[p.p_cameo_given_bench for p in reserves]);assert reserve is not None;timeline[reserve.player_id]=(90-duration,duration,90)
   support=list(data['weights']);selected=support[int(rng.choice(len(support),p=list(data['weights'].values())))];ensemble,start=self.ensembles[team,selected,changed];minutes=ensemble[int(rng.integers(len(ensemble)))]
   for j,p in enumerate(data['field']):
    m=int(minutes[j]);timeline[p.player_id]=(m,0,m)if start[j]else(m,90-m,90)
  validate_timeline(self.input,timeline);self.audit['draws']+=1
  for team in self.teams:
   arrivals=[timeline[p.player_id][1]for p in self.input.players if p.team==team and timeline[p.player_id][0]>0 and timeline[p.player_id][1]>0];self.audit['max_substitutions']=max(self.audit['max_substitutions'],len(arrivals));self.audit['max_windows']=max(self.audit['max_windows'],len(set(arrivals)-{45}))
  return timeline
