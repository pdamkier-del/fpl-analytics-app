"""Ephemeral private manager API: no account credentials, payload logging or public plans."""
import json,os,secrets,subprocess,threading,time,tempfile,shutil,sys
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
def cleanup():
    with lock:
        for key,job in list(jobs.items()):
            if time.time()-job['created']>TTL and job['status']!='running':
                shutil.rmtree(job['directory'],ignore_errors=True);del jobs[key]
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
@app.route('/health')
def health():return jsonify(status='ready',runtime='original_locked_python',locked_model_active=False)
@app.route('/plans',methods=['POST','OPTIONS'])
def create():
    if request.method=='OPTIONS':return ('',204)
    if request.headers.get('Origin')!=ORIGIN:return jsonify(error='Invalid app origin'),403
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
            (directory/'input.json').write_text(json.dumps(dict(forecast=forecast,state=body['state'])))
            if forecast.get('tc_scenarios'):(directory/'tc.csv.gz').write_bytes(get_public('tc-samples.csv.gz'))
            completed=subprocess.run([sys.executable,str(ROOT/'scripts/locked_numerical_runtime.py'),str(ROOT/'service/manager_job.py'),str(directory)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1800)
            if completed.returncode!=0:raise ValueError('Original computation rejected input')
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
    if job['status']=='completed':return jsonify(status='completed',plan=json.loads((job['directory']/'result.json').read_text()))
    return jsonify(status='running')
