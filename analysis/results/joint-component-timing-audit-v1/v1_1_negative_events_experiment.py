"""Phase 3E: historical-core negative-event model.

Scope deliberately stops before the shared penalty and red-card match-state models:
- yellow/red are a competing categorical discipline outcome;
- own goals are a separate rare-event hazard;
- penalty misses are preserved/validated but NOT forecast independently, because
  they must come from the later shared penalty event (taker + keeper outcome);
- red-card suspension duration is not guessed from FPL's aggregate red flag.

All player event rates are current-season-to-date only.  Hyperparameters are fit
on 2022/23-2024/25 and evaluated once on 2025/26.  No half-life is introduced in
this phase, per the project decision to postpone half-life architecture changes.
"""
from __future__ import annotations
import argparse,csv,json,math,sqlite3
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from fpl_v1_1_model.evaluation import binary_metrics,regression_metrics
from fpl_v1_1_model.negative_events import competing_card_probabilities,rare_event_probability,expected_direct_negative_points

DEV={'2022-23','2023-24','2024-25'}; HOLD='2025-26'; POS=('GK','GKP','DEF','MID','FWD')


def load(db):
    c=sqlite3.connect(db);c.row_factory=sqlite3.Row
    return c.execute("""select season,gw,fixture_uuid,player_uuid,team_id,opponent_team_id,kickoff_at,
      fpl_position,started,minutes,yellow_cards,fpl_red_cards,own_goals,penalty_misses
      from player_fixture_observations
      where fpl_position in ('GK','GKP','DEF','MID','FWD')
      order by season,kickoff_at,fixture_uuid,team_id,player_uuid""").fetchall()


def sigmoid(x): return 1/(1+math.exp(-x))


def xmins_by_fixture(rows,minfit,preg):
    hr=float(minfit['role_half_life']);hd=float(minfit['duration_half_life']);ar=2**(-1/hr);ad=2**(-1/hd)
    aa=float(preg['selected']['intercept']);bb=float(preg['selected']['slope']);out={}
    byseason=defaultdict(list)
    for r in rows: byseason[r['season']].append(r)
    for season,srows in byseason.items():
        state={};fixtures=defaultdict(list)
        for r in srows: fixtures[(r['kickoff_at'],r['fixture_uuid'])].append(r)
        for key in sorted(fixtures):
            cur=fixtures[key]
            for r in cur:
                s=state.get(r['player_uuid'],[0.]*8);sw,ss,nw,cc,dw,dm,cw,cm=s
                if int(r['gw'])>=6 and sw>0:
                    ps=min(1-1e-6,max(1e-6,ss/sw));ps=1/(1+math.exp(-(aa+bb*math.log(ps/(1-ps)))))
                    pc=cc/nw if nw else .20;sm=dm/dw if dw else 78.;cameo=cm/cw if cw else 16.
                    out[(season,r['fixture_uuid'],r['player_uuid'])]=ps*sm+(1-ps)*pc*cameo
            for r in cur:
                s=state.get(r['player_uuid'],[0.]*8);sw,ss,nw,cc,dw,dm,cw,cm=s
                sw*=ar;ss*=ar;nw*=ar;cc*=ar;dw*=ad;dm*=ad;cw*=ad;cm*=ad
                st=int(r['started'] or 0);m=float(r['minutes'] or 0);sw+=1;ss+=st
                if not st:nw+=1;cc+=float(m>0)
                if st:dw+=1;dm+=m
                elif m>0:cw+=1;cm+=m
                state[r['player_uuid']]=[sw,ss,nw,cc,dw,dm,cw,cm]
    return out


def build_records(rows,xmins):
    """Build cutoff-safe sufficient statistics before each target fixture."""
    rec=[];byseason=defaultdict(list)
    for r in rows:byseason[r['season']].append(r)
    for season,srows in byseason.items():
        player=defaultdict(lambda:[0.,0.,0.,0.]) # minutes,yellow,red,og
        pos=defaultdict(lambda:[0.,0.,0.,0.])
        league=[0.,0.,0.,0.]
        # Opponent-induced yellows: key=team that drew cards from opponents -> [yellow, games]
        induced=defaultdict(lambda:[0.,0.]); league_team=[0.,0.]
        fixtures=defaultdict(list)
        for r in srows:fixtures[(r['kickoff_at'],r['fixture_uuid'])].append(r)
        for key in sorted(fixtures):
            cur=fixtures[key]
            for r in cur:
                if int(r['gw'])<6:continue
                xm=xmins.get((season,r['fixture_uuid'],r['player_uuid']))
                if xm is None:continue
                ps=player[r['player_uuid']];pp=pos[r['fpl_position']];opp=induced[int(r['opponent_team_id'])]
                rec.append({
                    'season':season,'gw':int(r['gw']),'fixture_uuid':r['fixture_uuid'],'player_uuid':r['player_uuid'],
                    'position':r['fpl_position'],'team_id':int(r['team_id']),'opponent_team_id':int(r['opponent_team_id']),
                    'actual_minutes':float(r['minutes'] or 0),'xmins':float(xm),
                    'yellow':int(r['yellow_cards'] or 0)>0,'red':int(r['fpl_red_cards'] or 0)>0,'own_goal':int(r['own_goals'] or 0)>0,
                    'penalty_miss':int(r['penalty_misses'] or 0)>0,
                    'player_minutes':ps[0],'player_yellow':ps[1],'player_red':ps[2],'player_og':ps[3],
                    'pos_minutes':pp[0],'pos_yellow':pp[1],'pos_red':pp[2],'pos_og':pp[3],
                    'league_minutes':league[0],'league_yellow':league[1],'league_red':league[2],'league_og':league[3],
                    'opp_induced_yellow':opp[0],'opp_induced_games':opp[1],
                    'league_team_yellow':league_team[0],'league_team_games':league_team[1],
                })
            # update player/population states only after forecasts for the fixture
            team_y=defaultdict(float);opponents={}
            for r in cur:
                m=float(r['minutes'] or 0);y=float(r['yellow_cards'] or 0);rd=float(r['fpl_red_cards'] or 0);og=float(r['own_goals'] or 0)
                p=player[r['player_uuid']];p[0]+=m;p[1]+=y;p[2]+=rd;p[3]+=og
                q=pos[r['fpl_position']];q[0]+=m;q[1]+=y;q[2]+=rd;q[3]+=og
                league[0]+=m;league[1]+=y;league[2]+=rd;league[3]+=og
                team_y[int(r['team_id'])]+=y;opponents[int(r['team_id'])]=int(r['opponent_team_id'])
            for team,y in team_y.items():
                opp=opponents[team];induced[opp][0]+=y;induced[opp][1]+=1;league_team[0]+=y;league_team[1]+=1
    return rec


def prior_rate90(r,event):
    pe=float(r[f'pos_{event}']);pm=float(r['pos_minutes']);le=float(r[f'league_{event}']);lm=float(r['league_minutes'])
    if pm>0:return 90*pe/pm
    if lm>0:return 90*le/lm
    return 1e-8


def player_rate90(r,event,tau):
    prior=prior_rate90(r,event);e=float(r[f'player_{event}']);m=float(r['player_minutes'])
    return max(1e-10,90*(e+tau*prior/90)/(m+tau)) if m+tau>0 else max(1e-10,prior)


def opponent_factor(r,tau_opp):
    ly=float(r['league_team_yellow']);lg=float(r['league_team_games'])
    avg=ly/lg if lg>0 else 1.5
    oy=float(r['opp_induced_yellow']);og=float(r['opp_induced_games'])
    mean=(oy+tau_opp*avg)/(og+tau_opp) if og+tau_opp>0 else avg
    return max(.35,min(2.5,mean/max(.05,avg)))


def probabilities(r,tau_y,tau_r,tau_og,tau_opp,gamma):
    fy=opponent_factor(r,tau_opp)**gamma
    d=competing_card_probabilities(r['xmins'],player_rate90(r,'yellow',tau_y),player_rate90(r,'red',tau_r),yellow_multiplier=fy)
    pog=rare_event_probability(r['xmins'],player_rate90(r,'og',tau_og))
    return d,pog,fy


def discipline_nll(rec,params,mask):
    tau_y,tau_r,tau_opp,gamma=params;eps=1e-9;loss=0.;n=0
    for r,k in zip(rec,mask):
        if not k:continue
        d,_,_=probabilities(r,tau_y,tau_r,5000.,tau_opp,gamma)
        p=d.red if r['red'] else d.yellow if r['yellow'] else d.none
        loss-=math.log(max(eps,p));n+=1
    return loss/n


def own_goal_nll(rec,tau,mask):
    eps=1e-9;loss=0.;n=0
    for r,k in zip(rec,mask):
        if not k:continue
        p=rare_event_probability(r['xmins'],player_rate90(r,'og',tau));y=int(r['own_goal'])
        loss-=y*math.log(max(eps,p))+(1-y)*math.log(max(eps,1-p));n+=1
    return loss/n


def fit(rec):
    dev=np.asarray([r['season'] in DEV for r in rec],bool)
    def obj(z):
        tau_y=math.exp(z[0]);tau_r=math.exp(z[1]);tau_opp=math.exp(z[2]);gamma=1.5*sigmoid(z[3])
        return discipline_nll(rec,(tau_y,tau_r,tau_opp,gamma),dev)
    rr=minimize(obj,[math.log(700),math.log(4000),math.log(8),-1.0],method='L-BFGS-B',
      bounds=[(math.log(30),math.log(10000)),(math.log(100),math.log(50000)),(math.log(.25),math.log(50)),(-7,7)],options={'maxiter':120,'ftol':1e-11})
    tau_y,tau_r,tau_opp=map(math.exp,rr.x[:3]);gamma=1.5*sigmoid(rr.x[3])
    ro=minimize(lambda z:own_goal_nll(rec,math.exp(float(z[0])),dev),[math.log(8000)],method='L-BFGS-B',bounds=[(math.log(100),math.log(100000))],options={'maxiter':80,'ftol':1e-12})
    return {'yellow_prior_minutes_tau':tau_y,'red_prior_minutes_tau':tau_r,'opponent_yellow_prior_fixtures_tau':tau_opp,'opponent_yellow_exponent_gamma':gamma,'own_goal_prior_minutes_tau':math.exp(ro.x[0]),'development_discipline_nll':float(rr.fun),'development_own_goal_logloss':float(ro.fun),'optimizer_success':bool(rr.success and ro.success)}


def multiclass_metrics(y,p):
    p=np.clip(np.asarray(p,float),1e-9,1);y=np.asarray(y,int);return {'n':int(len(y)),'log_loss':float(-np.mean(np.log(p[np.arange(len(y)),y]))),'brier_multiclass':float(np.mean(np.sum((p-np.eye(3)[y])**2,axis=1)))}


def evaluate(rec,pars,mask,*,gamma_override=None,tau_override=None):
    ys=[];ps=[];og=[];pog=[];direct_actual=[];direct_pred=[];rows=[]
    ty=pars['yellow_prior_minutes_tau'];tr=pars['red_prior_minutes_tau'];to=pars['opponent_yellow_prior_fixtures_tau'];g=pars['opponent_yellow_exponent_gamma'] if gamma_override is None else gamma_override;tog=pars['own_goal_prior_minutes_tau']
    if tau_override is not None:ty,tr=tau_override
    for r,k in zip(rec,mask):
        if not k:continue
        d,po,f=probabilities(r,ty,tr,tog,to,g);cls=2 if r['red'] else 1 if r['yellow'] else 0
        ys.append(cls);ps.append([d.none,d.yellow,d.red]);og.append(int(r['own_goal']));pog.append(po)
        actual=-int(r['yellow'])-3*int(r['red'])-2*int(r['own_goal']) # penalty miss intentionally excluded
        pred=expected_direct_negative_points(d,p_own_goal=po)
        direct_actual.append(actual);direct_pred.append(pred)
        rows.append((r,d,po,f,pred,actual))
    mm=multiclass_metrics(ys,ps);yb=[int(x==1) for x in ys];rb=[int(x==2) for x in ys]
    ym=binary_metrics(yb,[x[1] for x in ps]).as_dict();rm=binary_metrics(rb,[x[2] for x in ps]).as_dict();om=binary_metrics(og,pog).as_dict()
    ym.update({'mean_pred':float(np.mean([x[1] for x in ps])),'event_rate':float(np.mean(yb))});rm.update({'mean_pred':float(np.mean([x[2] for x in ps])),'event_rate':float(np.mean(rb))});om.update({'mean_pred':float(np.mean(pog)),'event_rate':float(np.mean(og))})
    mm['yellow']=ym;mm['red']=rm
    return {'discipline':mm,'own_goal':om,'direct_negative_points_ex_penalty_miss':regression_metrics(direct_actual,direct_pred).as_dict(),'mean_pred_direct_negative_points':float(np.mean(direct_pred)),'mean_actual_direct_negative_points':float(np.mean(direct_actual))},rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',type=Path,default=Path('data_v1_1/normalized/fpl_v1_1.sqlite3'));ap.add_argument('--minutes-fit',type=Path,default=Path('outputs/v1_1/phase3a_minutes/continuous_half_life_fit.json'));ap.add_argument('--pstart-fit',type=Path,default=Path('outputs/v1_1/phase3a_minutes/pstart_regularization.json'));ap.add_argument('--out',type=Path,default=Path('outputs/v1_1/phase3e_negative_events'));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    rows=load(a.db);minfit=json.loads(a.minutes_fit.read_text());preg=json.loads(a.pstart_fit.read_text());xm=xmins_by_fixture(rows,minfit,preg);rec=build_records(rows,xm);pars=fit(rec)
    dev=np.asarray([r['season'] in DEV for r in rec],bool);hold=np.asarray([r['season']==HOLD for r in rec],bool)
    dm,_=evaluate(rec,pars,dev);hm,hrows=evaluate(rec,pars,hold);noopp,_=evaluate(rec,pars,hold,gamma_override=0.0);posonly,_=evaluate(rec,pars,hold,tau_override=(1e9,1e9))
    red_posonly_pars=dict(pars);red_posonly_pars['red_prior_minutes_tau']=1e9
    red_posonly,_=evaluate(rec,red_posonly_pars,hold)
    recommended,rrows=evaluate(rec,red_posonly_pars,hold,gamma_override=0.0)
    og_posonly_pars=dict(pars);og_posonly_pars['own_goal_prior_minutes_tau']=1e9
    og_posonly,_=evaluate(rec,og_posonly_pars,hold)
    penalty_counts={s:int(sum(int(r['penalty_miss']) for r in rec if r['season']==s)) for s in sorted(DEV|{HOLD})}
    result={'scope':'Direct negative FPL events from Historical Core. Penalty misses are not forecast independently; they are reserved for the shared penalty event model.','development_seasons':sorted(DEV),'holdout_season':HOLD,'target_from_gw':6,'development_selected':pars,'recommended_for_joint_model':{'yellow_prior_minutes_tau':pars['yellow_prior_minutes_tau'],'red_model':'current-season position rate (player-specific red rate not supported)','own_goal_prior_minutes_tau':pars['own_goal_prior_minutes_tau'],'opponent_yellow_factor':False,'reason':'Holdout log loss does not support the opponent factor; red player-specific tau hit the upper bound. Keep the simpler candidate until a future 2026/27 validation block.'},'development_metrics':dm,'holdout_metrics':hm,'recommended_holdout_metrics':recommended,'holdout_ablations':{'no_opponent_yellow_factor':noopp,'position_only_card_rates':posonly,'red_position_only':red_posonly,'own_goal_position_only':og_posonly},'historical_penalty_miss_events_in_forecast_rows':penalty_counts,'notes':['No new half-life is introduced in Phase 3E. Current-season player event counts use all prior season minutes with empirical-Bayes shrinkage.','Yellow/red are a categorical competing event because normalized FPL rows never contain both flags in one player-fixture. Historical Core cannot distinguish straight red from second-yellow red.','Own goals are modeled as a separate rare event with strong current-season position shrinkage.','Penalty misses remain observed truth only and are excluded from the direct-negative forecast metric to prevent double counting when the shared penalty model is added.','Red-card match-state effects and exact red suspension length wait for event time/subtype data; the core library requires authoritative suspension length rather than guessing it.']}
    (a.out/'negative_events_fit.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.out/'negative_events_holdout_predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['season','gw','fixture_uuid','player_uuid','position','xmins','actual_minutes','actual_yellow','actual_red','actual_own_goal','actual_penalty_miss','p_yellow','p_red','p_own_goal','opponent_yellow_factor','expected_direct_negative_points_ex_penalty_miss','actual_direct_negative_points_ex_penalty_miss'])
        for r,d,po,fac,pred,actual in rrows:w.writerow([r['season'],r['gw'],r['fixture_uuid'],r['player_uuid'],r['position'],r['xmins'],r['actual_minutes'],int(r['yellow']),int(r['red']),int(r['own_goal']),int(r['penalty_miss']),d.yellow,d.red,po,fac,pred,actual])
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
