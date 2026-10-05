"""Develop soft-role priors, freeze event inputs, then run paired v4 points."""
import gzip
import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
from fpl_v1_1_model.role_event_priors import KEYS,QCOLS,EVENTS,role_priors_at_deadline
from fpl_v1_1_model.role_history import RoleHistory
from fpl_v1_1_model.role_classifier import ROLES
from fpl_v1_1_model.deadline_components import weighted_totals
from fpl_v1_1_model.paired_joint import read_frozen_table,build_pair,run_pair

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/role-event-priors-20261005-v1'
FROZEN=ROOT/'analysis/results/deadline-joint-inputs-v1'

def pack(name,frame):
    raw=frame.to_csv(index=False).encode();blob=gzip.compress(raw,mtime=0);parts=[]
    for i,start in enumerate(range(0,len(blob),32768)):
        path=f'{name}.csv.gz.part-{i:04d}';b=blob[start:start+32768];(OUT/path).write_bytes(b)
        parts.append(dict(path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    return dict(name=name,rows=len(frame),parts=parts,compressed_sha256=hashlib.sha256(blob).hexdigest(),uncompressed_sha256=hashlib.sha256(raw).hexdigest())

def deviance(y,mu):
    y=np.asarray(y,float);mu=np.maximum(np.asarray(mu,float),1e-12)
    t=mu-y;positive=y>0;t[positive]+=y[positive]*np.log(y[positive]/mu[positive])
    return float(2*t.mean())

def metrics(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(mae=float(abs(e).mean()),rmse=float(np.sqrt((e**2).mean())),bias=float(e.mean()))

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    protocol=dict(primary='conditional event-prior Poisson deviance on development GW16-21',
        candidates=['position',900,3600,9000],selection='per component; position wins ties within 1e-10',
        role_state='full predeadline q slow distribution, half-life 10 completed team matches',
        historical_roles='prior predicted q; no actual target-role labels used to attribute event pools',
        pooling='fractional minutes and event masses within each broad FPL position; role rates shrink toward position',
        selection_scope='prior distribution only; oracle actual exposure for conditional rate evaluation, not an end-to-end forecast score',
        integration='selected priors replace position priors inside existing frozen individual shrinkage; all nuisance parameters unchanged',
        development_caveat='retrospective historical rosters; verified predeadline roster scope available only for the 144-fixture joint diagnostic',
        evaluated='144 identical fixtures, current v4 minutes both arms, original simulator, 80 draws, seed 26092501',
        holdout='GW22-38 reused diagnostic; no independent test',policy='no transfer/chip change')
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    featurepath=ROOT/'analysis/results/workload-recovered-v4/all_features.csv.gz'
    f=pd.read_csv(featurepath)
    roles=f[KEYS+QCOLS+['cutoff','max_history_known_at']].copy()
    with sqlite3.connect(ROOT/'work/core.sqlite3') as con:
        h=pd.read_sql_query("SELECT DISTINCT fixture_uuid,player_uuid,team_id,gw,minutes,started,fpl_position,kickoff_at,xg,xa,defcon_count FROM player_fixture_observations WHERE season='2025-26'",con)
    assert not h[KEYS].duplicated().any()
    h['kickoff_at']=pd.to_datetime(h.kickoff_at,utc=True);h['available_at']=h.kickoff_at+pd.Timedelta(hours=3)
    # Independently reconstruct every saved q from completed historical lineups.
    rolepath=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
    labels=pd.read_csv(rolepath)
    joined=h.merge(labels[KEYS+['final_role']],on=KEYS,how='left',validate='one_to_one')
    history=RoleHistory()
    for (fixture,team),g in joined.groupby(['fixture_uuid','team_id']):
        history.add_game(team,g.available_at.iloc[0],fixture,[dict(player_uuid=r.player_uuid,
            minutes=r.minutes,started=bool(r.started),role=r.final_role,disagreement=False) for r in g.itertuples()])
    audit=[]
    for (gw,team),g in f.groupby(['gw','team_id']):
        cutoff=pd.Timestamp(g.cutoff.iloc[0]);states,_,games=history.state(team,cutoff,10)
        reconstructed=np.array([[states.get(r.player_uuid,{}).get('q',{}).get(role,0.) for role in ROLES] for r in g.itertuples()])
        delta=float(np.abs(reconstructed-g[QCOLS].to_numpy()).max())
        assert delta<1e-10,(gw,team,delta)
        audit.append(dict(gw=int(gw),team_id=int(team),rows=len(g),max_q_error=delta,history_fixtures=len(games)))
    pd.DataFrame(audit).to_csv(OUT/'role_state_audit.csv',index=False)
    dev=f[f.gw.between(16,21)].merge(h[KEYS+['xg','xa','defcon_count']],on=KEYS,validate='one_to_one')
    predictions=[]
    for gw,g in dev.groupby('gw'):
        for tau in [900,3600,9000]:
            rates=role_priors_at_deadline(h,roles,g,roles[roles.fixture_uuid.isin(g.fixture_uuid)],g.cutoff.iloc[0],tau)
            rates=rates.merge(g[KEYS+['minutes','xg','xa','defcon_count']],on=KEYS,validate='one_to_one')
            rates['gw']=gw;rates['tau']=tau;predictions.append(rates)
    d=pd.concat(predictions,ignore_index=True);scores=[];selected={}
    for kind,event in EVENTS.items():
        baseline=d[d.tau==900]
        base=deviance(baseline[event],baseline[kind+'_position_prior90']*baseline.minutes/90)
        scores.append(dict(component=kind,candidate='position',rows=len(baseline),deviance=base))
        selected[kind]=None;best=base
        for tau,g in d.groupby('tau',sort=True):
            loss=deviance(g[event],g[kind+'_role_prior90']*g.minutes/90)
            scores.append(dict(component=kind,candidate=str(tau),rows=len(g),deviance=loss))
            if loss<best-1e-10:selected[kind]=int(tau);best=loss
    pd.DataFrame(scores).to_csv(OUT/'development_metrics.csv',index=False)
    (OUT/'selection.json').write_text(json.dumps(dict(selected_tau_minutes=selected,period='GW16-21',selected_before_joint_test=True),indent=2)+'\n')
    print('Development selection:',selected,flush=True)
    baseline=read_frozen_table(FROZEN,'inputs')
    common=read_frozen_table(ROOT/'analysis/results/deadline-player-components-v1','components')
    attackpath=ROOT/'analysis/results/joint-component-recovery-v1/player_attack_fit.json'
    dcpath=ROOT/'analysis/results/joint-component-recovery-v1/defcon_fit.json'
    attack=json.loads(attackpath.read_text());dc=json.loads(dcpath.read_text())['selected']
    allrows=[];priorrows=[]
    for gw,g in baseline.groupby('gw',sort=True):
        cutoff=g.cutoff.iloc[0];past=h[h.available_at<pd.Timestamp(cutoff)].sort_values(['kickoff_at','fixture_uuid'])
        players={pid:z for pid,z in past.groupby('player_uuid',sort=False)}
        result=g.copy().set_index(KEYS)
        base_dc=common.set_index(['fixture_uuid','player_uuid']).loc[list(zip(g.fixture_uuid,g.player_uuid))].dc_rate90.to_numpy()
        result['role_dc_rate90']=base_dc
        priors={tau:role_priors_at_deadline(h,roles,g,roles[roles.fixture_uuid.isin(g.fixture_uuid)],cutoff,tau).set_index(KEYS).loc[result.index] for tau in set(selected.values()) if tau is not None}
        for kind,event in EVENTS.items():
            tau=selected[kind]
            if tau is None:continue
            prior=priors[tau]
            recency=dc['player_dc_half_life'] if kind=='dc' else attack[kind]['recency_half_life']
            individual_tau=dc['position_prior_minutes_tau'] if kind=='dc' else attack[kind]['current_season_position_prior_minutes_tau']
            den=np.array([weighted_totals(players.get(pid,past.iloc[:0]),event,recency)[1] for pid in g.player_uuid])
            adjustment=individual_tau/(den+individual_tau)*(prior[kind+'_role_prior90'].to_numpy()-prior[kind+'_position_prior90'].to_numpy())
            col='role_dc_rate90' if kind=='dc' else kind+'_rate90'
            result[col]=np.maximum(0,result[col].to_numpy()+adjustment)
            priorrows.append(prior.reset_index()[KEYS+['role_known','pooled_role_minutes',kind+'_role_prior90',kind+'_position_prior90']].assign(component=kind,gw=gw))
        result=result.reset_index()
        factor=common.set_index(['fixture_uuid','player_uuid']).loc[list(zip(g.fixture_uuid,g.player_uuid))].dc_opponent_factor.to_numpy()
        result['mu_dc']=g.control_xmins.to_numpy()/90*result.role_dc_rate90.to_numpy()*factor
        allrows.append(result)
    candidate=pd.concat(allrows,ignore_index=True)
    lambdas=np.where(candidate.team_id==candidate.home_team_id,candidate.lambda_home_goals,candidate.lambda_away_goals)
    for kind in ['goal','assist']:
        prop=candidate.control_xmins/90*candidate[kind+'_rate90'];total=prop.groupby([candidate.fixture_uuid,candidate.team_id]).transform('sum')
        assert total.gt(0).all()
        candidate[kind+'_mu']=lambdas*prop/total*(candidate.assist_probability_per_goal if kind=='assist' else 1)
    candidate=candidate.sort_values(['gw','fixture_uuid','team_id','player_uuid']).reset_index(drop=True)
    baseline=baseline.sort_values(['gw','fixture_uuid','team_id','player_uuid']).reset_index(drop=True)
    allowed={'goal_rate90','assist_rate90','goal_mu','assist_mu','mu_dc'}
    for col in baseline:
        if col not in allowed:pd.testing.assert_series_equal(baseline[col],candidate[col])
    outputs=[pack('candidate_inputs',candidate),pack('development_prior_predictions',d)]
    if priorrows:outputs.append(pack('role_prior_trace',pd.concat(priorrows,ignore_index=True)))
    paths=[featurepath,rolepath,attackpath,dcpath,Path(__file__),ROOT/'src/fpl_v1_1_model/role_event_priors.py']
    manifest=dict(classification='experimental_soft_role_event_priors_reused_diagnostic',outputs=outputs,
        selected=selected,role_q_rows_verified=len(f),role_q_team_deadlines_verified=len(audit),
        no_minute_or_policy_changes=True,model_promoted=False,
        sources=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Joint evaluator: both arms use current v4 minute forecasts.
    predictions=[]
    for i,(fixture,g) in enumerate(baseline.groupby('fixture_uuid',sort=True)):
        _,control=build_pair(g);_,treatment=build_pair(candidate[candidate.fixture_uuid==fixture])
        a=asdict(control);b=asdict(treatment);ap=a.pop('players');bp=b.pop('players');assert a==b
        for x,y in zip(ap,bp):
            assert {k:v for k,v in x.items() if k not in ['goal_weight','assist_weight','dc_mu_90']}=={k:v for k,v in y.items() if k not in ['goal_weight','assist_weight','dc_mu_90']}
        cs,vs=run_pair(control,treatment,n=80,seed=26092501+i)
        for r in g.itertuples():
            row=dict(fixture_uuid=fixture,player_uuid=r.player_uuid,gw=r.gw,team_id=r.team_id)
            for arm,values in [('current_v4',cs[r.player_uuid]),('role_candidate',vs[r.player_uuid])]:
                row.update({arm+'_'+k:v for k,v in values.items()})
            predictions.append(row)
        if (i+1)%20==0:print('Paired role fixtures:',i+1,flush=True)
    pred=pd.DataFrame(predictions);outputs.append(pack('predictions',pred))
    manifest['outputs']=outputs;(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    actual=read_frozen_table(FROZEN,'targets');scored=pred.merge(actual,on=['fixture_uuid','player_uuid'],validate='one_to_one')
    report=dict(rows=len(pred),fixtures=pred.fixture_uuid.nunique(),draws=80,seed=26092501,
        selected=selected,nonbonus={arm:metrics(scored.total_points-scored.bonus,scored[arm+'_xPts_nonbonus']) for arm in ['current_v4','role_candidate']},
        classification='reused_diagnostic_not_new_holdout',model_promoted=False,
        limitations=['original BPS season mismatch: nonbonus is primary','fixed 80 draws are technical sensitivity, not a precise ranking',
                     'development prior selection uses actual exposure; production uses current v4 minutes','q history begins GW6; missing role history uses position fallback'])
    (OUT/'joint_metrics.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
