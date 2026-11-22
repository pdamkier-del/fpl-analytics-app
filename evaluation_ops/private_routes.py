"""Capability-protected intentions and separately labelled execution observations."""
import fcntl,gzip,json,os,re,secrets,time
from datetime import datetime,timezone
from .ts_capture import ledger,storage,Rejected

def _original(root,capture_id):
 ledger.verify(root)
 for line in (root/'ledger.jsonl').read_text().splitlines():
  entry=json.loads(line)
  if entry['entry_sha256']==capture_id:return json.loads(gzip.decompress((root/entry['record']).read_bytes()))
 raise ValueError('Original capture missing')

def append_intention(root,capture_id,decision,now=None):
 now=now or datetime.now(timezone.utc);original=_original(root,capture_id)
 # Reuse the original validator. No substitution of the recommendation for a user choice.
 verified=ledger.validate_intention(original['forecast'],original['manager_state'],original['recommendation'],decision,now)
 body={'schema':'fpl-private-ts-observation-v1','kind':'user_intention','captured_at':now.isoformat(),'capture_id':capture_id,'decision':verified,'execution':None}
 return _append(root,body)

def append_reported_execution(root,capture_id,body,now=None):
 """Browser input is NEVER promoted to verified official execution."""
 now=now or datetime.now(timezone.utc);original=_original(root,capture_id)
 if now<ledger.clock(original['deadline']):raise ValueError('Execution observation is scored only after deadline')
 transfers=body.get('transfers')
 if not isinstance(transfers,list)or not all(isinstance(t,dict)and type(t.get('element_in'))is int and type(t.get('element_out'))is int for t in transfers):raise ValueError('Invalid execution observation')
 return _append(root,{'schema':'fpl-private-ts-observation-v1','kind':'reported_execution','captured_at':now.isoformat(),'capture_id':capture_id,'transfers':[{'element_in':t['element_in'],'element_out':t['element_out']}for t in transfers],'verified_official':False,'eligibility_for_realized_strategy_score':False})

def _append(root,body):
 folder=root/'observations';folder.mkdir(mode=0o700,exist_ok=True);os.chmod(folder,0o700);lock=os.open(root/'.events-lock',os.O_CREAT|os.O_RDWR,0o600)
 try:
  fcntl.flock(lock,fcntl.LOCK_EX);raw=ledger.canonical(body);key=secrets.token_hex(32);fd=os.open(folder/(key+'.json'),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'wb')as h:h.write(raw);h.flush();os.fsync(h.fileno())
  return {'status':'recorded_private','kind':body['kind'],'execution_verified':False}
 finally:fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)

def register(app,jobs,lock,origin,ttl):
 from flask import request,jsonify
 def handle(identifier,kind):
  if request.headers.get('Origin')!=origin:return jsonify(error='Invalid app origin'),403
  with lock:job=jobs.get(identifier)
  if not job or not secrets.compare_digest(job['key'],request.headers.get('X-Plan-Key','')):return jsonify(error='Privat jobkvittering mangler eller matcher ikke.'),404
  if time.time()-job['created']>ttl:return jsonify(error='Privat jobkvittering er udløbet.'),410
  if job['status']!='completed':return jsonify(error='Den originale beregning er ikke færdig.'),409
  try:
   result=json.loads((job['directory']/'result.json').read_text());capture_id=result.get('evaluation_capture',{}).get('capture_id')
   if not isinstance(capture_id,str)or not re.fullmatch('[a-f0-9]{64}',capture_id):return jsonify(error='Ingen gyldig privat før-deadline-capture findes for beregningen.'),409
   root=storage();body=request.get_json(silent=True)
   if not isinstance(body,dict):raise ValueError('Missing observation')
   reply=append_intention(root,capture_id,body)if kind=='intent'else append_reported_execution(root,capture_id,body)
   return jsonify(reply),201
  except Rejected as e:return jsonify(status='not_captured',reason_code=e.code,message=e.message),409
  except Exception:return jsonify(status='not_captured',reason_code='observation_rejected',message='Observationen bestod ikke identitets-, tidspunkt- eller indholdskontrollen.'),422
 app.add_url_rule('/plans/<identifier>/evaluation-intent','evaluation_intent',lambda identifier:handle(identifier,'intent'),methods=['POST'])
 app.add_url_rule('/plans/<identifier>/evaluation-execution','evaluation_execution',lambda identifier:handle(identifier,'execution'),methods=['POST'])
