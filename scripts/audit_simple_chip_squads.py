import argparse,json
import run_joint_fh_wc_stopping_replay as replay
p=argparse.ArgumentParser()
p.add_argument('--vfinal',required=True)
a=p.parse_args()
gws,names,forecast=replay.load(a.vfinal)
events=[]
wc_original=replay.compare_wc_as_ts_action
fh_original=replay.optimize_free_hit_squad
def wc_capture(state,meta,origin,gw,config,**kw):
    result=wc_original(state,meta,origin,gw,config,**kw)
    before=set(state.squad)
    after=set(result.state.squad)
    events.append({'gw':gw,'chip':'wc','out':[names.get(i,str(i)) for i in sorted(before-after)],'in':[names.get(i,str(i)) for i in sorted(after-before)],'squad':[names.get(i,str(i)) for i in sorted(after)]})
    return result
def fh_capture(**kw):
    result=fh_original(**kw)
    before=set(kw['state'].squad)
    after=set(result['plan_rows'].id)
    events.append({'gw':kw['gw'],'chip':'fh','out':[names.get(i,str(i)) for i in sorted(before-after)],'in':[names.get(i,str(i)) for i in sorted(after-before)],'squad':[names.get(i,str(i)) for i in sorted(after)]})
    return result
replay.compare_wc_as_ts_action=wc_capture
replay.optimize_free_hit_squad=fh_capture
result=replay.run('squad_audit',gws,names,forecast,use_chips=True,simple_thresholds=(10,20))
selected=[x for x in events if (x['chip']=='wc' and x['gw'] in result['wc_gws']) or (x['chip']=='fh' and x['gw'] in result['fh_gws'])]
print('SQUAD_AUDIT_RESULT',json.dumps({'points':result['total_points'],'selected':selected}))
