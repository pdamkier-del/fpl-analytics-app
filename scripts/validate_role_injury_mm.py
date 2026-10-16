#!/usr/bin/env python3
"""Paired MM-only frozen walk-forward replay with source availability ablations."""
import argparse,base64,gzip,hashlib,io,json,sqlite3,sys,zipfile
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from individual_mm_evidence import load_frame,encode_frame
from experimental_role_injury_mm import eligible_news,medical_fields,bounded_news,carry_normal_role
from research_role_injury_club_audit import Evidence
OUT=ROOT/'analysis/results/role-injury-mm-20261016';KEY=['season','fixture_uuid','player_uuid']
PRIMARY='role_news_projected'

def save(p,d):
    def clean(v):
        if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
        if isinstance(v,(list,tuple)):return[clean(x)for x in v]
        if isinstance(v,(float,np.floating))and not np.isfinite(v):return None
        return v.item()if hasattr(v,'item')else v
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(d),indent=2,default=str,allow_nan=False)+'\n')

def read_news(path):
    with gzip.open(path,'rt')as z:return[json.loads(l)for l in z]

def evidence_catalog(rows):
    """All episode transitions use previously time-visible evidence, not outcomes."""
    result=[];state={}
    for r in sorted(rows,key=lambda r:(r['season'],str(r.get('player_uuid')),r['cutoff'],r['effective_at'])):
        if not eligible_news(r,r['cutoff'],r['team_id']):continue
        state_name=r['normalized_availability_state'];state_name='DOUBTFUL'if state_name in ['DOUBT','MAJOR_DOUBT']else'AVAILABLE'if state_name=='RETURNED_AVAILABLE'else state_name
        Evidence(r['player_uuid'],r['season']+':'+str(r['team_id']),r['effective_at'],r.get('news_added')or'',r['effective_at'],r['source_url'],'immutable_official_FPL_api_archive',state_name,confidence='official').validate()
        k=(r['season'],r['player_uuid'],r['team_id']);old=state.get(k,dict(medical=False,episode=None));fields=medical_fields(r);current=r['normalized_availability_state'];returned=old['medical']and current in ['AVAILABLE','RETURNED_AVAILABLE'];new=fields['confirmed_medical_out']and not old['medical']
        episode=(r['source_id']+':'+str(r['fpl_element']))if new else old['episode']
        result.append(dict(**r,**fields,medical_return=bool(returned),medical_episode=episode,episode_first_observed=bool(new),source_published_at=r.get('news_added'),actual_injury_onset=None,actual_training_return_at=None,tactical_role=None))
        state[k]=dict(medical=(False if returned else old['medical']or fields['confirmed_medical_out']),episode=episode)
    return pd.DataFrame(result)

def attach(f,catalog):
    lookup={(r['season'],int(r['gw']),r['player_uuid']):r for r in catalog.to_dict('records')};rows=[]
    for r in f.to_dict('records'):
        n=lookup.get((r['season'],int(r['gw']),r['player_uuid']));ok=eligible_news(n,r['cutoff'],r['team_id'])if n else False
        rows.append(dict(news_eligible=bool(ok),news_state=n['normalized_availability_state']if ok else'UNKNOWN',news_chance=n.get('scoped_chance')if ok else None,news_medical_out=bool(ok and n['confirmed_medical_out']),news_medical_return=bool(ok and n['medical_return']),news_injury_type=n['injury_type']if ok else None,news_source=n['source_url']if ok else None,news_effective_at=n['effective_at']if ok else None,news_wrong_club=bool(n is not None and int(n['team_id'])!=int(r['team_id']))))
    return pd.concat([f.reset_index(drop=True),pd.DataFrame(rows)],axis=1)

def scores(g):
    if not len(g):return dict(rows=0,status='Not Available: no matched verified cases')
    y=g.y.to_numpy(float);p=g.p.to_numpy(float);m=g.minutes.to_numpy(float);x=g.x.to_numpy(float);q=g.q.to_numpy(float);s=g.s.to_numpy(float);c=g.c.to_numpy(float);eps=1e-12;pp=np.clip(p,eps,1-eps);bench=y==0;sub=bench&(m>0);starter=y==1
    if not np.isfinite(np.c_[p,q,s,c,x,m]).all()or np.any((p<0)|(p>1)|(q<0)|(q>1)|(x<0)|(x>90+1e-9)):raise ValueError('Illegal MM output')
    components=np.c_[(p-y)*(s-q*c),y*(s-m),(1-y)*(q-(m>0))*c,(1-y)*(m>0)*(c-m)]
    if not np.allclose(components.sum(1),x-m,atol=1e-9):raise ValueError('Minute component identity failed')
    values={mask:float(abs(components[:,[j for j in range(4)if mask&(1<<j)]].sum(1)).mean())for mask in range(16)}
    import math
    shapley={name:float(sum((values[k|(1<<j)]-values[k])/(4*math.comb(3,k.bit_count()))for k in range(16)if not k&(1<<j)))for j,name in enumerate(['start_selection','starter_duration','cameo_selection','cameo_duration'])}
    return dict(rows=len(g),fixtures=int(g.fixture_uuid.nunique()),mae=float(abs(x-m).mean()),rmse=float(np.sqrt(((x-m)**2).mean())),bias=float((x-m).mean()),start_brier=float(((p-y)**2).mean()),start_log_loss=float(-(y*np.log(pp)+(1-y)*np.log1p(-pp)).mean()),conditional_starter_mae=float(abs(s[starter]-m[starter]).mean())if starter.any()else None,cameo_brier=float(((q[bench]-(m[bench]>0))**2).mean())if bench.any()else None,conditional_cameo_mae=float(abs(c[sub]-m[sub]).mean())if sub.any()else None,mean_minutes=float(x.mean()),actual_mean=float(m.mean()),component_mae_attribution=shapley,attribution_warning='Exact algebraic Shapley, not causal explanation; includes cancellation',projection_infeasible=int(g.get('projection_infeasible',pd.Series(False,index=g.index)).sum()),max_expected_starters_error=float(abs(g.groupby(['fixture_uuid','team_id']).p.sum()-11).max()))

def paired(g,base,draws=1000):
    z=g.merge(base[KEY+['p','x','y','minutes']],on=KEY,validate='one_to_one',suffixes=('','_base'))
    if len(z)!=len(g)or len(base)!=len(g)or not np.array_equal(z.y,z.y_base)or not np.array_equal(z.minutes,z.minutes_base):raise ValueError('Different paired cohort/truth')
    eps=1e-12;y=z.y.to_numpy();p=np.clip(z.p,eps,1-eps);b=np.clip(z.p_base,eps,1-eps);a=z.x-z.minutes;old=z.x_base-z.minutes
    losses=np.c_[abs(a),abs(old),a*a,old*old,(p-y)**2,(b-y)**2,-(y*np.log(p)+(1-y)*np.log1p(-p)),-(y*np.log(b)+(1-y)*np.log1p(-b))]
    ix=z.groupby('fixture_uuid',sort=True).indices;blocks=np.asarray([[len(j)]+losses[j].sum(0).tolist()for j in ix.values()]);rng=np.random.default_rng(20261016);boot=blocks[rng.integers(len(blocks),size=(draws,len(blocks)))].sum(1);out={}
    for j,k in enumerate(['mae','rmse','start_brier','start_log_loss']):
        aa=boot[:,1+j*2]/boot[:,0];bb=boot[:,2+j*2]/boot[:,0];v=losses[:,j*2:j*2+2].mean(0)
        if k=='rmse':aa=np.sqrt(aa);bb=np.sqrt(bb);v=np.sqrt(v)
        out[k]=dict(delta=float(v[0]-v[1]),interval95=np.quantile(aa-bb,[.025,.975]).tolist()if len(blocks)>=20 else None)
    return dict(fixture_blocks=len(blocks),metrics=out,warning='Reused periods; fixture bootstrap, no multiplicity correction; fewer than20 blocks have no CI')

def tactical_history(core,base):
    path=ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv'
    if not path.exists():return dict(status='Not Available')
    raw=pd.read_csv(path);truth=core[['season','fixture_uuid','player_uuid','team_id','started','kickoff_at']];r=raw.merge(truth,on=['fixture_uuid','player_uuid','team_id'],validate='many_to_one');r=r[r.started.eq(1)];r['known_at']=pd.to_datetime(r.kickoff_at,utc=True)+pd.to_timedelta(np.where(r.season.eq('2025-26'),3,4),unit='h');r=r.drop_duplicates(['fixture_uuid','player_uuid']);profiles=[]
    for (season,cut),f in base.groupby(['season','cutoff']):
        history=r[r.known_at.lt(pd.Timestamp(cut))&r.season.eq(season)]
        for pid,g in history.groupby('player_uuid'):
            counts=g.final_role.value_counts().to_dict();profiles.append(dict(season=season,cutoff=cut,player_uuid=pid,known_roles=counts,maximum_known=str(g.known_at.max()),source='reproducible-role-v1/classified_starters.csv',confidence='Retrospective provider tactical labels; postmatch clock proxy; not new medical/manager testimony',used_in_forecast=False))
    save(OUT/'tactical_profiles.json',dict(rows=len(r),profiles=profiles,note='Existing tactical labels retained as descriptive evidence only; not silently added as unvalidated numerical MM features'))
    return dict(verified_starter_rows=len(r),profiles=len(profiles),by_season=r.groupby('season').size().to_dict(),used_in_candidate=False)

def main():
    OUT.mkdir(parents=True,exist_ok=True);source24=ROOT/'work/news-2024-push-verified';source25=ROOT/'data_v1_1/derived/team_news_audit/2025-26-v2';rows24=read_news(source24/'predeadline_strict.jsonl.gz');rows25=read_news(source25/'predeadline_strict.jsonl.gz');catalog=evidence_catalog(rows24+rows25);catalog.to_csv(OUT/'source_backed_news.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    with sqlite3.connect(ROOT/'work/core.sqlite3')as c:
        core=pd.read_sql_query('SELECT * FROM player_fixture_observations WHERE is_final=1',c);names=dict(c.execute('SELECT player_uuid,canonical_name FROM players'))
    allreports={};allpred=[];coverage=[];club_names={(r['season'],int(r['team_id'])):r['team']for r in read_news(source24/'observations.jsonl.gz')+rows25};summary={};baselines=[]
    for season in ['2024-25','2025-26']:
        f=load_frame(ROOT/f'work/mm-source/{season}_candidates.npz');modes={name:attach(f[f['mode'].eq(old)].copy(),catalog)for name,old in [('original','original'),('no_role','same_logistic_without_role'),('role','role_start')]};original=modes['original']
        for k,g in modes.items():paired(g,original,draws=20)
        # Freeze interpretations before evaluation; no new coefficient fitting.
        modes['original_news']=bounded_news(original);modes['no_role_news']=bounded_news(modes['no_role']);modes['role_news']=bounded_news(modes['role']);modes[PRIMARY]=bounded_news(modes['role'],project=True);modes['role_source_chance']=bounded_news(modes['role'],chance=True,project=True);modes['role_return_carry']=bounded_news(carry_normal_role(modes['role']),project=True);modes['role_return_duration']=bounded_news(carry_normal_role(modes['role'],True),project=True)
        for name,g in modes.items():
            g=g.copy();g['mode']=name
            if not np.allclose(g.p*g.s+(1-g.p)*g.q*g.c,g.x,atol=1e-9):raise ValueError('MM probability reconciliation failed')
            allpred.append(g)
        ev={k:(v[v.gw.ge(22)]if season=='2024-25'else v)for k,v in modes.items()};report={k:dict(metrics=scores(g),vs_original=paired(g,ev['original']),vs_role=paired(g,ev['role']))for k,g in ev.items()}
        primary=ev[PRIMARY];clubs=[]
        for team,g in primary.groupby('team_id'):
            same={k:v[v.team_id.eq(team)]for k,v in ev.items()};clubs.append(dict(team_id=int(team),club=club_names.get((season,int(team)),'Not Available: no verified name bridge'),rows=len(g),metrics={k:scores(v)for k,v in same.items()},primary_vs_role=paired(g,same['role']),primary_vs_original=paired(g,same['original'])))
        clubs.sort(key=lambda r:r['metrics'][PRIMARY]['mae'],reverse=True)
        groups={}
        for field,values in [('player_type',['regular','rotation_or_short_history','reserve']),('news_medical_return',[True]),('news_medical_out',[True]),('news_eligible',[True,False])]:
            for val in values:
                group=primary[primary[field].eq(val)];key=field+':'+str(val);groups[key]=dict(models={k:scores(v[v[field].eq(val)])for k,v in ev.items()},primary_vs_role=paired(group,ev['role'][ev['role'][field].eq(val)])if len(group)else None)
        selected_players={}
        for pid in ['255ce56a-28f3-53e5-ae63-19f3c15aa12d','481b07c4-b805-52cf-a0ee-593af134790d','4448091c-aeb7-5ab3-a537-b2b547480e63']:
            selected_players[names[pid]]={k:scores(v[v.player_uuid.eq(pid)])for k,v in ev.items()}
        worst=primary.assign(abs_error=abs(primary.x-primary.minutes)).nlargest(30,'abs_error');wr=[]
        for row in worst.to_dict('records'):
            row['player']=names.get(row['player_uuid']);row['diagnosis']='source_outcome_conflict'if row['news_state']in ['OUT','SUSPENDED']and row['minutes']>0 else'start_selection_error'if (row['y']==0 and row['p']>.5)or(row['y']==1 and row['p']<.5)else'duration_error_unverified_cause';wr.append(row)
        for tid,g in original.groupby('team_id'):
            cg=catalog[catalog.season.eq(season)&catalog.team_id.eq(tid)]if len(catalog)else catalog
            coverage.append(dict(season=season,team_id=int(tid),club=club_names.get((season,int(tid)),'Not Available'),forecast_rows=len(g),strict_matched_rows=int(g.news_eligible.sum()),strict_coverage=float(g.news_eligible.mean()),unresolved_or_unavailable_rows=int((~g.news_eligible).sum()),wrong_club_rejected=int(g.news_wrong_club.sum()),source_rows=len(cg),flagged_injury_rows=int(cg.raw_status.eq('i').sum())if len(cg)else 0,typed_medical_out_rows=int(cg.confirmed_medical_out.sum())if len(cg)else 0,observed_medical_episodes=int(cg.episode_first_observed.sum())if len(cg)else 0,source_confirmed_selection_returns=int(cg.medical_return.sum())if len(cg)else 0,training_return_statements=int(cg.training_state.notna().sum())if len(cg)else 0))
        allreports[season]=dict(models=report,clubs_ranked_by_primary_error=clubs,groups=groups,focus=selected_players,worst_errors=wr,injury_out_actual_appearance_conflicts=int((primary.news_medical_out&primary.minutes.gt(0)).sum()),availability_layer_already_present_in_prior_mm=int(original.team_news_state.ne('UNKNOWN').sum()))
        summary[season]={k:r['metrics']for k,r in report.items()};baselines.append(original)
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False);pred=pd.concat(allpred,ignore_index=True);(OUT/'predictions.npz').write_bytes(encode_frame(pred));tactical=tactical_history(core,pd.concat(baselines));save(OUT/'report.json',dict(protocol=dict(primary=PRIMARY,development='Prior role model selected2024GW11-21, frozen; new source rules predeclared without tuning; availability ablations not selected on evaluation',evaluation=['2024GW22-38','2025GW6-38'],mm_only=True,pm_ts_chips_points_not_run=True),results=allreports,coverage=coverage,tactical=tactical,limitations=['Reused research seasons, not independent holdouts','Historical outcome availability remains inherited kickoff+3/4h proxy','FPL medical flags/selection returns are source evidence, not doctor clearance','Unknown injury types/dates remain null; no invented year in expected-back text','Source chance cap is a sensitivity interpretation, not calibrated medical probability','Role carry is a tested research alternative, not automatic promotion','Sparse groups under20 fixture blocks have no confidence interval'],locked_model_active=False,promotion_allowed=False));save(OUT/'summary.json',summary);save(OUT/'source_manifest.json',dict(pr4_commit='6d875a65251fb62f691dc0386ea81aeb29d27c0f',pr8_base='4f34321bb45b1aedf073aa0de6d29d9c7a35416f',files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [ROOT/'work/mm-source/capsule_manifest.json',source24/'source_manifest.json',source24/'predeadline_strict.jsonl.gz',source25/'SHA256_MANIFEST.json',source25/'predeadline_strict.jsonl.gz']},locked_model_active=False))
    print(json.dumps(summary,indent=2));print('MM only; no PM, TS, chips or FPL point simulation',flush=True)

if __name__=='__main__':main()
