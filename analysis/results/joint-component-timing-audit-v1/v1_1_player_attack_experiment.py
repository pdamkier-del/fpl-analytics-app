"""Phase 3C: allocate forecast team attack to players using current-season recency xG/xA.

Historical-core experiment only.  No previous-season player attack prior is used.
Player rates are exposure weighted, shrunk only toward the current-season
position mean available before the target fixture, and multiplied by v1.1 xMins.
The resulting propensities are normalized inside each team so player goal means
sum to the independently forecast team goal lambda.  Assists use the same
construction with xA and a cutoff-safe season-to-date FPL-assists-per-goal rate.
"""
from __future__ import annotations
import argparse,json,math,sqlite3,time
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

DEV=('2023-24','2024-25'); HOLD='2025-26'; POS=('GK','GKP','DEF','MID','FWD')

def load_pf(db,seasons):
    c=sqlite3.connect(db);c.row_factory=sqlite3.Row;q=','.join('?' for _ in seasons)
    return c.execute(f"""select season,gw,fixture_uuid,player_uuid,team_id,opponent_team_id,was_home,kickoff_at,
        fpl_position,started,minutes,xg,xa,goals,fpl_assists
        from player_fixture_observations where season in ({q}) and fpl_position in ('GK','GKP','DEF','MID','FWD')
        order by season,kickoff_at,fixture_uuid,team_id,player_uuid""",tuple(seasons)).fetchall()

def load_tf(db,seasons):
    c=sqlite3.connect(db);c.row_factory=sqlite3.Row;q=','.join('?' for _ in seasons)
    return c.execute(f"select season,gw,fixture_uuid,team_id,opponent_team_id,was_home,kickoff_at,gf,ga,xg,xga from team_fixture_observations where season in ({q}) order by season,kickoff_at,fixture_uuid,was_home desc",tuple(seasons)).fetchall()

def team_lambdas(rows,p,min_gw=6):
    ha=p['attack_half_life'];hd=p['defence_half_life'];alpha=p['xg_weight_alpha'];beta=p['xga_weight_beta'];intercept=p['intercept'];home=p['home_log_effect']
    da=2**(-1/ha);dd=2**(-1/hd);out={};byseason=defaultdict(list)
    for r in rows:byseason[r['season']].append(r)
    for season,rs in byseason.items():
        fixtures=defaultdict(list)
        for r in rs:fixtures[(r['kickoff_at'],r['fixture_uuid'])].append(r)
        att={};deff={};lg=0.;ln=0
        for key in sorted(fixtures):
            cur=fixtures[key]
            for r in cur:
                t=r['team_id'];o=r['opponent_team_id']
                if int(r['gw'])>=min_gw and t in att and o in deff and ln:
                    aw,gf,xg=att[t];dw,ga,xga=deff[o]
                    A=alpha*(xg/aw)+(1-alpha)*(gf/aw);D=beta*(xga/dw)+(1-beta)*(ga/dw);league=lg/ln
                    lam=math.exp(intercept+home*int(r['was_home']))*max(.05,A)*max(.05,D)/max(.3,league)
                    out[(season,r['fixture_uuid'],int(t))]=min(5.,max(.05,lam))
            for r in cur:
                t=int(r['team_id']);a=att.get(t,[0.,0.,0.]);d=deff.get(t,[0.,0.,0.]);a=[x*da for x in a];d=[x*dd for x in d]
                a[0]+=1;a[1]+=float(r['gf']);a[2]+=float(r['xg']);d[0]+=1;d[1]+=float(r['ga']);d[2]+=float(r['xga']);att[t]=a;deff[t]=d;lg+=float(r['gf']);ln+=1
    return out

def precompute_context(rows,minfit,preg,min_gw=6):
    hr=minfit['role_half_life'];hd=minfit['duration_half_life'];ar=2**(-1/hr);ad=2**(-1/hd);aa=float(preg['selected']['intercept']);bb=float(preg['selected']['slope'])
    # states keyed season/player.  League position totals and assist ratio are cutoff-safe.
    role={}; out={}; pos_tot=defaultdict(lambda:[0.,0.,0.]); league=defaultdict(lambda:[0.,0.])
    fixtures=defaultdict(list)
    for r in rows: fixtures[(r['season'],r['kickoff_at'],r['fixture_uuid'])].append(r)
    for key in sorted(fixtures):
        cur=fixtures[key]; season=key[0]
        # snapshot priors before this fixture
        for r in cur:
            pid=(season,r['player_uuid']);s=role.get(pid,[0.]*8);sw,ss,nw,cc,dw,dm,cw,cm=s
            if int(r['gw'])>=min_gw and sw>0:
                ps=ss/sw;ps=min(1-1e-6,max(1e-6,ps));ps=1/(1+math.exp(-(aa+bb*math.log(ps/(1-ps)))))
                pc=cc/nw if nw else .20;sm=dm/dw if dw else 78.;cameo=cm/cw if cw else 16.;xm=ps*sm+(1-ps)*pc*cameo
                pt=pos_tot[(season,r['fpl_position'])];pxg90=90*pt[0]/pt[2] if pt[2]>0 else 0.;pxa90=90*pt[1]/pt[2] if pt[2]>0 else 0.
                lt=league[season];qassist=lt[1]/lt[0] if lt[0]>0 else .90;qassist=min(1.,max(.5,qassist))
                out[(season,r['fixture_uuid'],r['player_uuid'])]=(xm,pxg90,pxa90,qassist)
        # update role and league priors after all target contexts are captured
        for r in cur:
            pid=(season,r['player_uuid']);s=role.get(pid,[0.]*8);sw,ss,nw,cc,dw,dm,cw,cm=s
            sw*=ar;ss*=ar;nw*=ar;cc*=ar;dw*=ad;dm*=ad;cw*=ad;cm*=ad
            st=int(r['started'] or 0);m=float(r['minutes'] or 0);sw+=1;ss+=st
            if not st:nw+=1;cc+=float(m>0)
            if st:dw+=1;dm+=m
            elif m>0:cw+=1;cm+=m
            role[pid]=[sw,ss,nw,cc,dw,dm,cw,cm]
            pt=pos_tot[(season,r['fpl_position'])];pt[0]+=float(r['xg'] or 0);pt[1]+=float(r['xa'] or 0);pt[2]+=m
            lt=league[season];lt[0]+=float(r['goals'] or 0);lt[1]+=float(r['fpl_assists'] or 0)
    return out

def build_matrix(rows,contexts,teamlam):
    import pandas as pd
    rec=[]
    for idx,r in enumerate(rows):
        ctx=contexts.get((r['season'],r['fixture_uuid'],r['player_uuid']));lk=(r['season'],r['fixture_uuid'],int(r['team_id']))
        if ctx is None or lk not in teamlam:continue
        xm,pxg90,pxa90,qassist=ctx
        rec.append((idx,r['season'],int(r['gw']),r['fixture_uuid'],r['player_uuid'],int(r['team_id']),float(r['goals']),float(r['fpl_assists']),xm,pxg90,pxa90,qassist,teamlam[lk]))
    df=pd.DataFrame(rec,columns=['rowidx','season','gw','fixture_uuid','player_uuid','team_id','goals','assists','xmins','pxg90','pxa90','qassist','team_lambda'])
    keys=list(zip(df.season,df.fixture_uuid,df.team_id));mp={};gid=[]
    for k in keys:
        if k not in mp:mp[k]=len(mp)
        gid.append(mp[k])
    df['group_id']=gid
    return df

def state_arrays(rows,matrix,h):
    decay=2**(-1/h);state={};sxg=np.zeros(len(rows));sxa=np.zeros(len(rows));smin=np.zeros(len(rows))
    for i,r in enumerate(rows):
        key=(r['season'],r['player_uuid']);a,b,c=state.get(key,(0.,0.,0.));sxg[i]=a;sxa[i]=b;smin[i]=c
        state[key]=(a*decay+float(r['xg'] or 0),b*decay+float(r['xa'] or 0),c*decay+float(r['minutes'] or 0))
    idx=matrix.rowidx.to_numpy(dtype=int);return sxg[idx],sxa[idx],smin[idx]

def predict_matrix(rows,matrix,h,tau,kind,state_cache):
    key=round(float(h),7)
    if key not in state_cache:state_cache[key]=state_arrays(rows,matrix,h)
    sxg,sxa,smin=state_cache[key];num=sxg if kind=='goal' else sxa;prior=matrix.pxg90.to_numpy() if kind=='goal' else matrix.pxa90.to_numpy();den=smin+tau
    rate=np.divide(90*(num+tau*prior/90),den,out=prior.copy(),where=den>0)
    prop=matrix.xmins.to_numpy()/90*rate;gid=matrix.group_id.to_numpy(dtype=int);sums=np.bincount(gid,weights=prop,minlength=int(gid.max())+1)
    share=np.divide(prop,sums[gid],out=np.zeros_like(prop),where=sums[gid]>0);target=matrix.team_lambda.to_numpy()*(matrix.qassist.to_numpy() if kind=='assist' else 1.0)
    return np.clip(target*share,1e-9,None)

def score(y,mu):
    mu=np.clip(mu,1e-9,None);return float(np.mean(mu-y*np.log(mu)))

def score_for(rows,matrix,h,tau,kind,seasons,state_cache):
    mu=predict_matrix(rows,matrix,h,tau,kind,state_cache);mask=matrix.season.isin(seasons).to_numpy();y=(matrix.goals if kind=='goal' else matrix.assists).to_numpy();return score(y[mask],mu[mask])

def fit_fast(rows,matrix,kind):
    cache={}
    def obj(z):return score_for(rows,matrix,math.exp(z[0]),math.exp(z[1]),kind,DEV,cache)
    starts=[(16,360)] if kind=='goal' else [(28,360)];best=None
    for st in starts:
        r=minimize(obj,np.log(st),method='Nelder-Mead',options={'maxiter':35,'xatol':1e-3,'fatol':1e-8})
        if best is None or r.fun<best.fun:best=r
    return math.exp(best.x[0]),math.exp(best.x[1]),float(best.fun),cache

def metrics(y,mu):
    e=mu-y;return {'n':int(len(y)),'poisson_nll_no_constant':score(y,mu),'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e)),'sum_mu':float(mu.sum()),'sum_actual':float(y.sum())}

def evaluate(rows,matrix,h,tau,kind,seasons,cache=None):
    cache={} if cache is None else cache;mu=predict_matrix(rows,matrix,h,tau,kind,cache);mask=matrix.season.isin(seasons).to_numpy();y=(matrix.goals if kind=='goal' else matrix.assists).to_numpy();return metrics(y[mask],mu[mask]),mu,mask

def no_recency_ablation(rows,matrix,kind):
    cache={}
    def obj(z):return score_for(rows,matrix,1e6,math.exp(z),kind,DEV,cache)
    r=minimize(lambda x:obj(float(x[0])),[math.log(360)],method='Nelder-Mead',options={'maxiter':30});tau=math.exp(float(r.x[0]));dev,_,_=evaluate(rows,matrix,1e6,tau,kind,DEV,cache);hold,_,_=evaluate(rows,matrix,1e6,tau,kind,(HOLD,),cache);return {'half_life':'infinity','tau':tau,'development':dev,'holdout':hold}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',type=Path,default=Path('data_v1_1/normalized/fpl_v1_1.sqlite3'));ap.add_argument('--team-fit',type=Path,default=Path('outputs/v1_1/phase3b_team_goals/team_goal_fit.json'));ap.add_argument('--minutes-fit',type=Path,default=Path('outputs/v1_1/phase3a_minutes/continuous_half_life_fit.json'));ap.add_argument('--pstart-fit',type=Path,default=Path('outputs/v1_1/phase3a_minutes/pstart_regularization.json'));ap.add_argument('--out',type=Path,default=Path('outputs/v1_1/phase3c_player_attack'));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    pf=load_pf(a.db,DEV+(HOLD,));tf=load_tf(a.db,DEV+(HOLD,));teamfit=json.loads(a.team_fit.read_text())['fit'];minfit=json.loads(a.minutes_fit.read_text());preg=json.loads(a.pstart_fit.read_text());tl=team_lambdas(tf,teamfit);ctx=precompute_context(pf,minfit,preg);matrix=build_matrix(pf,ctx,tl)
    result={'development_seasons':list(DEV),'holdout_season':HOLD,'inputs':{'team_goal_fit':teamfit,'minutes_half_lives':{'role':minfit['role_half_life'],'duration':minfit['duration_half_life']},'pstart_regularization':preg['selected']}}
    import csv
    for kind in ('goal','assist'):
        h,tau,_,cache=fit_fast(pf,matrix,kind);dev,mu,_=evaluate(pf,matrix,h,tau,kind,DEV,cache);hold,_,hm=evaluate(pf,matrix,h,tau,kind,(HOLD,),cache);result[kind]={'recency_half_life':h,'current_season_position_prior_minutes_tau':tau,'development':dev,'holdout':hold,'no_recency_ablation':no_recency_ablation(pf,matrix,kind)}
        y=(matrix.goals if kind=='goal' else matrix.assists).to_numpy()
        with (a.out/f'{kind}_holdout_predictions.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['season','fixture_uuid','player_uuid','gw','team_id','actual','mu']);
            for (_,r),yy,mm,keep in zip(matrix.iterrows(),y,mu,hm):
                if keep:w.writerow([r.season,r.fixture_uuid,r.player_uuid,int(r.gw),int(r.team_id),yy,mm])
    result['notes']=['No previous-season player attack prior is used.','The current-season position mean supplies the only weak small-sample prior; its pseudo-minutes tau is fitted on development seasons.','Historical Core has FPL/Opta xG but no verified native npxG. Penalty separation is therefore deferred rather than faked as xG-0.79*penalties.','Player propensities are normalized to the independent team goal lambda, avoiding double-counting team strength and player xG.','Recency is selected on development seasons only; 2025/26 is untouched until evaluation.']
    (a.out/'player_attack_fit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
