"""Facit interventions for diagnostics only. Not a forecasting API.

Goal oracle conditions the original Bernoulli-own-goal + thinned Poisson law
on the exact team score. It does NOT replace lambda with realized goals.
Scoring/BPS tail is compiled unchanged from the pinned B simulator.
"""
import ast,inspect,itertools,math
from dataclasses import replace
import numpy as np
from scipy.special import logsumexp
from scipy.stats import poisson
from fpl_v1_1_model import b_event_simulator as B
from gk_joint_bridge import UNKNOWN
from fpl_v1_1_model.experimental_physical_timeline import validate_timeline,PhysicalKernel

def pb_suffix(probabilities):
    n=len(probabilities);d=np.zeros((n+1,n+1));d[n,0]=1
    for i in range(n-1,-1,-1):
        d[i]=d[i+1]*(1-probabilities[i]);d[i,1:]+=d[i+1,:-1]*probabilities[i]
    return d

def own_subset(probabilities,goal_count,poisson_mean,rng):
    p=np.asarray(probabilities,float);d=pb_suffix(p);k=np.arange(min(goal_count,len(p))+1)
    with np.errstate(divide='ignore'):log=np.log(d[0,k])+poisson.logpmf(goal_count-k,poisson_mean)
    if not np.isfinite(log).any():raise ValueError('Observed score has zero probability under source event law')
    count=int(rng.choice(k,p=np.exp(log-logsumexp(log))));selected=[]
    for i,v in enumerate(p):
        if count==0:break
        den=d[i,count];num=v*d[i+1,count-1]
        if den<=0:raise ValueError('Degenerate conditioned own-goal law')
        if rng.random()<num/den:selected.append(i);count-=1
    return selected

def score_conditioned_events(inp,rng,ps,intervals,actual_goals):
    """Equivalent exact conditioning, including penalty misses independent of goals."""
    events=[];misses=[];mass={};attempts={};means={};opens={};conversions={}
    def active(team,t):return[p for p in ps if p.team==team and intervals[p.player_id][0]<=t<intervals[p.player_id][1]]
    for team in (inp.home_team,inp.away_team):
        other=inp.away_team if team==inp.home_team else inp.home_team
        own=[p for p in ps if p.team==other and intervals[p.player_id][1]>intervals[p.player_id][0]]
        prob=[p.p_own_goal for p in own];mass[team]=sum(prob)
        attempts[team]=float(inp.lambda_home_penalties if team==inp.home_team else inp.lambda_away_penalties)
        means[team]=float(inp.lambda_home_goals if team==inp.home_team else inp.lambda_away_goals)
        conv=B.conditional_penalty_conversion(inp,intervals,team);conversions[team]=conv
        ordinary=means[team]-attempts[team]*conv-mass[team]
        if ordinary< -1e-12:raise ValueError('Invalid inclusive budget')
        opens[team]=max(0.,ordinary);mu=opens[team]+attempts[team]*conv;g=int(actual_goals[team])
        chosen=own_subset(prob,g,mu,rng)
        for i in chosen:
            p=own[i];a,b=intervals[p.player_id];events.append(B.GoalEvent(float(rng.uniform(a,b)),team,'own_goal',own_goal_committer=p.player_id))
        left=g-len(chosen);nordinary=int(rng.binomial(left,opens[team]/mu))if mu else 0
        for _ in range(nordinary):
            t=float(rng.uniform(0,90));on=active(team,t);scorer=B.legacy._weighted_choice(rng,on,[p.goal_weight for p in on])
            if scorer is None:raise ValueError('Oracle ordinary scorer missing')
            assister=None
            if rng.random()<inp.assist_probability_per_goal:
                eligible=[p for p in on if p.player_id!=scorer.player_id];assister=B.legacy._weighted_choice(rng,eligible,[p.assist_weight for p in eligible])
            events.append(B.GoalEvent(t,team,'ordinary',scorer.player_id,assister.player_id if assister else None,assist_eligible=assister is not None))
        cuts=sorted({0,90,*[v for p in ps if p.team==team for v in intervals[p.player_id]]});segments=[]
        for a,b in zip(cuts,cuts[1:]):
            if b<=a:continue
            candidates,weights=B.takers(inp,active(team,(a+b)/2));w=np.asarray(weights,float)
            if w.sum()<=0:
                if attempts[team]>0:raise ValueError('Oracle has no penalty taker')
                continue
            w/=w.sum();c=np.clip([p.penalty_conversion for p in candidates],0,1);segments.append((a,b,candidates,w,c))
        for success,count in [(True,left-nordinary),(False,int(rng.poisson(attempts[team]*(1-conv))))]:
            if not count:continue
            segment_weights=np.array([(b-a)/90*float(w@(c if success else 1-c))for a,b,ps0,w,c in segments]);segment_weights/=segment_weights.sum()
            for _ in range(count):
                a,b,candidates,w,c=segments[int(rng.choice(len(segments),p=segment_weights))];weight=w*(c if success else 1-c);taker=B.legacy._weighted_choice(rng,candidates,weight);t=float(rng.uniform(a,b))
                if success:events.append(B.GoalEvent(t,team,'penalty',taker.player_id))
                else:
                    keeper=next((p for p in active(other,t)if p.is_keeper),None);save=keeper.player_id if keeper is not None and rng.random()<inp.p_penalty_save_given_miss else None;misses.append((taker.player_id,save))
    return mass,events,attempts,means,opens,conversions,misses



def actual_timeline(inp,actual):
    timeline={}
    for p in inp.players:
        r=actual.get(p.player_id)
        if r is None:
            if p.player_id.startswith(UNKNOWN):timeline[p.player_id]=(0,90,90);continue
            raise ValueError('Missing oracle player outcome')
        m=int(r['minutes']);start=bool(r['started'])
        if m==0 and start:raise ValueError('Zero-minute starter cannot be timed')
        timeline[p.player_id]=(m,0,m)if start else(m,90-m,90)
    validate_timeline(inp,timeline);return timeline



# The historical FPL minute clock is NOT forced to sum to 990. This isolated
# measurement layer uses reported FPL minutes for scoring and reconciles a
# separate physical clock when true substitution timestamps are unavailable.
def reconcile_timeline(inp,actual,use_actual_starts):
    from scipy.optimize import linear_sum_assignment
    timeline={};all_errors=[]
    for team in (inp.home_team,inp.away_team):
        ps=[p for p in inp.players if p.team==team];played=[p for p in ps if actual.get(p.player_id,{}).get('minutes',0)>0]
        if use_actual_starts:starters=[p for p in played if actual[p.player_id]['started']]
        else:
            starters=[]
            for keeper,need in [(True,1),(False,10)]:
                options=sorted([p for p in played if p.is_keeper==keeper],key=lambda p:(-actual[p.player_id]['minutes'],-p.p_start,p.player_id));starters+=options[:need]
        if sum(p.is_keeper for p in starters)!=1 or len(starters)!=11:raise ValueError('Incomplete observed starting roster')
        starts={p.player_id for p in starters};bench=[p for p in played if p.player_id not in starts]
        if len(bench)>5:raise ValueError('Observed >5 substitutions: exception not modeled')
        for p in ps:timeline[p.player_id]=(90,0,90)if p.player_id in starts else(0,90,90)
        if not bench:continue
        costs=np.zeros((len(bench),len(starters)));targets={}
        for i,b in enumerate(bench):
            for j,s in enumerate(starters):
                mb=float(actual[b.player_id]['minutes']);ms=float(actual[s.player_id]['minutes']);t=float(np.clip((ms+90-mb)/2,1,89));targets[i,j]=t
                costs[i,j]=(t-ms)**2+(90-t-mb)**2-(90-ms)**2 if b.is_keeper==s.is_keeper else 1e12
        ii,jj=linear_sum_assignment(costs)
        if any(costs[i,j]>1e10 for i,j in zip(ii,jj)):raise ValueError('No physical positional substitution pairing')
        pairs=sorted([(targets[i,j],starters[j],bench[i])for i,j in zip(ii,jj)],key=lambda x:x[0]);n=len(pairs);best=None
        for bits in itertools.product([False,True],repeat=max(0,n-1)):
            groups=[];start=0
            for i,cut in enumerate(bits,1):
                if cut:groups.append(list(range(start,i)));start=i
            groups.append(list(range(start,n)))
            for half in [-1,*range(len(groups))]:
                times=[]
                for k,indices in enumerate(groups):times.append(45 if k==half else int(np.clip(np.rint(np.mean([pairs[i][0]for i in indices])),1,89)))
                if len(set(times)-{45})>3:continue
                error=sum((times[k]-pairs[i][0])**2 for k,group in enumerate(groups)for i in group)
                if best is None or error<best[0]:best=(error,groups,times)
        for group,t in zip(best[1],best[2]):
            for i in group:
                _,s,b=pairs[i];timeline[s.player_id]=(t,0,t);timeline[b.player_id]=(90-t,t,90)
    validate_timeline(inp,timeline)
    discrepancy={p.player_id:timeline[p.player_id][0]-actual.get(p.player_id,{}).get('minutes',0)for p in inp.players}
    return timeline,discrepancy

# Override only the standalone audit wrapper, never the application module.
class OracleTimeline:
    def __init__(self,inp,dist,actual,mask):
        self.input=inp;self.mask=mask;self.actual=actual;self.point_minutes=None
        if mask&1:
            self.exact,self.clock_discrepancy=reconcile_timeline(inp,actual,bool(mask&2));self.point_minutes={p.player_id:int(actual.get(p.player_id,{}).get('minutes',0))for p in inp.players}
        else:
            if mask&2:inp=replace(inp,players=tuple(replace(p,p_start=float(actual.get(p.player_id,{}).get('started',0)))for p in inp.players));dist={}
            self.kernel=PhysicalKernel(inp,dist)
    def sample(self,rng):return self.exact if self.mask&1 else self.kernel.sample(rng)

def _compile_point_clock(goal_conditioned):
    tree=ast.parse(inspect.getsource(B.simulate_match));fn=tree.body[0]
    class Clock(ast.NodeTransformer):
        def visit_Assign(self,node):
            if any(isinstance(t,ast.Attribute)and t.attr=='minutes'for t in node.targets):node.value=ast.parse('_point_minutes.get(p.player_id,m) if _point_minutes is not None else m',mode='eval').body
            return node
    tree=Clock().visit(tree);fn=tree.body[0]
    if goal_conditioned:
        start=next(i for i,n in enumerate(fn.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='mass'for t in n.targets));end=next(i for i,n in enumerate(fn.body)if isinstance(n,ast.Expr)and isinstance(n.value,ast.Call)and isinstance(n.value.func,ast.Attribute)and isinstance(n.value.func.value,ast.Name)and n.value.func.value.id=='events'and n.value.func.attr=='sort')
        fn.body[start:end]=ast.parse('''mass,events,attempts,means,open_means,conversion,misses=_condition(inp,rng,ps,intervals,_actual_goals)
for taker,keeper in misses:
    out[taker].penalty_miss+=1
    if keeper is not None:
        out[keeper].penalty_saves+=1
        out[keeper].saves+=1
''').body
    ast.fix_missing_locations(tree);namespace=dict(B.simulate_match.__globals__);namespace.update(_condition=score_conditioned_events,_actual_goals=None,_point_minutes=None);exec(compile(tree,'<audit-two-clock-oracle>','exec'),namespace);return namespace['simulate_match'],namespace
POINT_CLOCK,POINT_NS=_compile_point_clock(False)
CONDITIONED,GOAL_NS=_compile_point_clock(True)

def simulate(inp,rng,timeline,goals=None,point_minutes=None):
    if goals is None and point_minutes is None:return B.simulate_match(inp,rng,timeline=timeline)
    fn,ns=(POINT_CLOCK,POINT_NS)if goals is None else(CONDITIONED,GOAL_NS);ns['_actual_goals']=goals;ns['_point_minutes']=point_minutes;result=fn(inp,rng,timeline=timeline)
    if goals is not None:
        for team in (inp.home_team,inp.away_team):
            total=sum(result[p.player_id].goals for p in inp.players if p.team==team)+sum(result[p.player_id].own_goal for p in inp.players if p.team!=team)
            if total!=goals[team]:raise AssertionError('Goal oracle failed exact score')
    if point_minutes is not None and any(result[p].minutes!=m for p,m in point_minutes.items()):raise AssertionError('FPL minute oracle did not preserve actual scoring minutes')
    return result
