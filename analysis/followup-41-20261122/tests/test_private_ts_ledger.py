import copy,importlib.util,json,os,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pytest
C=Path(__file__).resolve().parents[1]/'code';sys.path.insert(0,str(C));import private_ts_ledger as m

def inputs():
 now=datetime(2026,11,27,12,tzinfo=timezone.utc);gws=list(range(12,18));pos=[1]*2+[2]*5+[3]*5+[4]*3
 f={'season':'2026-27','gws':gws,'data_asof':now.isoformat(),'origin_deadline':(now+timedelta(days=1)).isoformat(),'players':[{'id':i+1,'team_id':i//3+1,'position':p,'price_tenths':50,'weeks':[{'gw':g,'xpts':4.}for g in gws]}for i,p in enumerate(pos)]};f['forecast_sha256']=m.sha(m.canonical(f))
 state={'season':'2026-27','gw':12,'source':'SYNTHETIC_TEST_ONLY','observed_at':now.isoformat(),'free_transfers':2,'bank_tenths':10,'squad':[{'id':i,'purchase_price_tenths':50}for i in range(1,16)],'chips_used':{k:[]for k in ['wildcard','free_hit','bench_boost','triple_captain']}}
 roles={1:'XI',2:'BGK',3:'XI',4:'XI',5:'XI',6:'B1',7:'B2',8:'VC',9:'XI',10:'XI',11:'XI',12:'B3',13:'C',14:'XI',15:'XI'};rows=[{'id':i,'role':r}for i,r in roles.items()]
 plan={'ts_ran':True,'gw':12,'forecast_sha256':f['forecast_sha256'],'manager_state_sha256':m.sha(m.canonical(state)),'computed_at':now.isoformat(),'lineup':rows,'plan':{'weights':[1.,.6,.36,.216,.1296,.07776],'path':[{'gw':g}for g in gws]},'comparison':{'hold_squad_without_transfers':[{'gw':g,'expected_score':48.}for g in gws]},'chips_status':'Not Available','entry_id':'SHOULD_NOT_BE_COPIED'}
 dec={'source':'SYNTHETIC_TEST_ONLY','observed_at':now.isoformat(),'semantics':'intended_predeadline_not_verified_execution','choice':'keep_squad','rows':rows,'incoming':[],'outgoing':[],'active_chip':None}
 return f,state,plan,dec,now

def test_private_append_chain_and_permissions(tmp_path):
 f,s,p,d,now=inputs();root=tmp_path/'private';before=copy.deepcopy((f,s,p,d));m.capture(root,f,s,p,d,now=now);m.capture(root,f,s,p,d,now=now+timedelta(minutes=1));assert m.verify(root)==2;assert (f,s,p,d)==before;assert root.stat().st_mode&0o777==0o700
 for x in root.iterdir():assert x.stat().st_mode&0o777==0o600
 record=json.loads(m.gzip.decompress(next(root.glob('record-*')).read_bytes()));assert 'entry_id'not in record['recommendation'];assert record['horizon_gws']==list(range(12,18));assert record['manager_state']['free_transfers']==2;assert record['clock_proof'].startswith('local_system')

def test_reject_after_deadline_without_creating_ledger(tmp_path):
 f,s,p,d,now=inputs()
 with pytest.raises(ValueError,match='before origin'):m.capture(tmp_path/'private',f,s,p,d,now=now+timedelta(days=2))
 assert not (tmp_path/'private').exists()

@pytest.mark.parametrize('case',['forecast_mutated','missing_ft','missing_control','partial_horizon','wrong_state_hash','invalid_captain','stale','chip_reuse'])
def test_invalid_contract_is_not_archived(tmp_path,case):
 f,s,p,d,now=inputs()
 if case=='forecast_mutated':f['players'][0]['weeks'][0]['xpts']=99
 if case=='missing_ft':del s['free_transfers']
 if case=='missing_control':p['comparison']['hold_squad_without_transfers'].pop()
 if case=='partial_horizon':f['gws'].pop();f['forecast_sha256']=m.sha(m.canonical({k:v for k,v in f.items()if k!='forecast_sha256'}))
 if case=='wrong_state_hash':p['manager_state_sha256']='wrong'
 if case=='invalid_captain':d['rows']=copy.deepcopy(d['rows']);d['rows'][12]['role']='XI'
 if case=='stale':f['data_asof']=(now-timedelta(hours=25)).isoformat();f['forecast_sha256']=m.sha(m.canonical({k:v for k,v in f.items()if k!='forecast_sha256'}))
 if case=='chip_reuse':s['chips_used']['wildcard']=[1];p['manager_state_sha256']=m.sha(m.canonical(s));d['active_chip']='wildcard'
 with pytest.raises(ValueError):m.capture(tmp_path/'private',f,s,p,d,now=now)
 assert not (tmp_path/'private').exists()

def test_reject_git_destination(tmp_path):
 m.subprocess.run(['git','init','-q',str(tmp_path)],check=True)
 with pytest.raises(ValueError,match='outside'):m.private_root(tmp_path/'private')

def test_tampered_record_blocks_append(tmp_path):
 f,s,p,d,now=inputs();m.capture(tmp_path,f,s,p,d,now=now);next(tmp_path.glob('record-*')).write_bytes(b'tampered')
 with pytest.raises(ValueError,match='hash'):m.capture(tmp_path,f,s,p,d,now=now+timedelta(minutes=1))
 assert len((tmp_path/'ledger.jsonl').read_text().splitlines())==1

def test_crashed_unindexed_record_blocks_next_capture(tmp_path):
 f,s,p,d,now=inputs();(tmp_path/'record-000001-orphan.json.gz').write_bytes(b'partial')
 with pytest.raises(ValueError,match='Unindexed'):m.capture(tmp_path,f,s,p,d,now=now)
 assert not (tmp_path/'ledger.jsonl').exists()

def test_cli_errors_never_print_private_payload(tmp_path,capsys,monkeypatch):
 (tmp_path/'secret.json').write_text('{"manager_token":"DO_NOT_PRINT_THIS"}')
 monkeypatch.setattr(sys,'argv',['private_ts_ledger.py','capture','--root',str(tmp_path/'ledger'),'--forecast',str(tmp_path/'secret.json'),'--state',str(tmp_path/'secret.json'),'--plan',str(tmp_path/'secret.json'),'--decision',str(tmp_path/'secret.json')])
 assert m.main()==1;out=capsys.readouterr();assert 'DO_NOT_PRINT_THIS'not in out.out+out.err;assert 'manager_token'not in out.out+out.err;assert not (tmp_path/'ledger').exists()
