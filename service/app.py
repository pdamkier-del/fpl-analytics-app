"""Ephemeral private manager API: no account credentials, payload logging or public plans."""
import json,os,secrets,subprocess,threading,time,tempfile,shutil,sys,hashlib
from datetime import datetime,timezone,timedelta
from functools import lru_cache
from pathlib import Path
from urllib.request import Request,urlopen
from flask import Flask,request,jsonify
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://pdamkier-del.github.io'
PUBLIC='https://pdamkier-del.github.io/fpl-analytics-app/'
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=32768
jobs={};lock=threading.Lock();TTL=3600

def get_public(name):
    with urlopen(Request(PUBLIC+name,headers={'Cache-Control':'no-cache','User-Agent':'FPLAnalyticsPrivateCompute/1'}),timeout=30) as r:return r.read()
def verify_current_window(forecast,bootstrap,now=None):
    from scripts.verify_official_forecast_window import verify
    now=now or datetime.now(timezone.utc)
    if forecast.get('locked_model_active') is not False or forecast.get('model')!='original_locked_vFinal_diagnostic':raise ValueError('Invalid original forecast contract')
    cutoff=datetime.fromisoformat(forecast['data_asof'].replace('Z','+00:00'))
    limit=forecast.get('freshness_limit_hours')
    if not isinstance(limit,(int,float)) or not 0<limit<=24 or not cutoff<=now<=cutoff+timedelta(hours=limit):raise ValueError('Forecast freshness expired')
    return verify(forecast,bootstrap,now)
def verify_official_now(forecast):
    with urlopen(Request('https://fantasy.premierleague.com/api/bootstrap-static/',headers={'Cache-Control':'no-cache'}),timeout=30) as r:bootstrap=json.load(r)
    return verify_current_window(forecast,bootstrap)
def cleanup():
    with lock:
        for key,job in list(jobs.items()):
            if time.time()-job['created']>TTL and job['status']!='running':
                shutil.rmtree(job['directory'],ignore_errors=True);del jobs[key]
def janitor():
    while True:
        time.sleep(60)
        cleanup()
threading.Thread(target=janitor,daemon=True).start()

@app.after_request
def headers(response):
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    if request.headers.get('Origin')==ORIGIN:
        response.headers['Access-Control-Allow-Origin']=ORIGIN
        response.headers['Vary']='Origin'
        response.headers['Access-Control-Allow-Headers']='Content-Type, X-Plan-Key'
        response.headers['Access-Control-Allow-Methods']='GET, POST, OPTIONS'
    return response
@lru_cache(maxsize=1)
def original_runtime_ready():
    try:
        from service.manager_job import calculate
        return callable(calculate)
    except (ImportError, OSError, ValueError):
        return False

@app.route('/health')
def health():
    ready=original_runtime_ready()
    return jsonify(status='ready' if ready else 'unavailable',
                   runtime='original_locked_python',locked_model_active=False,
                   adapter_sha256=hashlib.sha256((ROOT/'service/app.py').read_bytes()+(ROOT/'service/manager_job.py').read_bytes()).hexdigest()), (200 if ready else 503)
@app.route('/plans',methods=['POST','OPTIONS'])
def create():
    if request.method=='OPTIONS':return ('',204)
    if request.headers.get('Origin')!=ORIGIN:return jsonify(error='Invalid app origin'),403
    if not original_runtime_ready():return jsonify(error='Original Python-beregningstjeneste er ikke klar. Prøv igen senere.'),503
    cleanup()
    body=request.get_json(silent=True)
    if not isinstance(body,dict) or not isinstance(body.get('state'),dict) or not isinstance(body.get('forecast_cutoff'),str):return jsonify(error='Ugyldigt manager-state'),400
    with lock:
        if any(j['status']=='running' for j in jobs.values()):return jsonify(error='Beregningstjenesten er optaget. Prøv igen om lidt.'),429
        if len(jobs)>=12:return jsonify(error='Midlertidig kapacitetsgrænse. Prøv igen senere.'),429
        key=secrets.token_urlsafe(32);identifier=secrets.token_hex(16);directory=Path(tempfile.mkdtemp(prefix='fpl-private-'))
        jobs[identifier]={'key':key,'directory':directory,'created':time.time(),'status':'running'}
    def work():
        try:
            forecast=json.loads(get_public('vfinal-diagnostic.json'))
            official=json.loads(get_public('current-players.json'))
            if forecast['data_asof']!=body['forecast_cutoff'] or forecast['gws'][0]!=official['next_gw']:raise ValueError('Forecast changed')
            verify_official_now(forecast)
            (directory/'input.json').write_text(json.dumps(dict(forecast=forecast,state=body['state'])))
            if forecast.get('tc_scenarios'):(directory/'tc.csv.gz').write_bytes(get_public('tc-samples.csv.gz'))
            completed=subprocess.run([sys.executable,str(ROOT/'scripts/locked_numerical_runtime.py'),str(ROOT/'service/manager_job.py'),str(directory)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1800)
            if completed.returncode!=0:raise ValueError('Original computation rejected input')
            verify_official_now(forecast)
            if json.loads(get_public('vfinal-diagnostic.json'))['data_asof']!=forecast['data_asof']:raise ValueError('Forecast changed during calculation')
            jobs[identifier]['status']='completed'
        except Exception:
            jobs[identifier]['status']='failed'
        finally:
            (directory/'input.json').unlink(missing_ok=True);(directory/'tc.csv.gz').unlink(missing_ok=True)
    threading.Thread(target=work,daemon=True).start()
    return jsonify(id=identifier,key=key),202
@app.route('/plans/<identifier>',methods=['GET','OPTIONS'])
def status(identifier):
    if request.method=='OPTIONS':return ('',204)
    job=jobs.get(identifier)
    if not job or not secrets.compare_digest(job['key'],request.headers.get('X-Plan-Key','')):return jsonify(error='Beregningen findes ikke længere. Beregn igen.'),404
    if time.time()-job['created']>TTL:return jsonify(error='Beregningen er udløbet. Beregn igen.'),410
    if job['status']=='failed':return jsonify(status='failed',error='Beregningen bestod ikke kontrollerne. Kontrollér hold, tidspunkt og forecast, og prøv igen.'),422
    if job['status']=='completed':
        try:
            result=json.loads((job['directory']/'result.json').read_text())
            if not isinstance(result,dict):raise ValueError('Invalid private result')
        except (OSError,ValueError,TypeError):
            return jsonify(status='failed',error='Det private resultat kunne ikke valideres. Beregn igen.'),422
        return jsonify(status='completed',plan=result)
    return jsonify(status='running')
