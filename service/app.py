"""Ephemeral private manager API: no account credentials, payload logging or public plans."""
import json,os,secrets,subprocess,threading,time,tempfile,shutil,sys,hashlib,re
from datetime import datetime,timezone,timedelta
from functools import lru_cache
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import URLError
from flask import Flask,request,jsonify
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://pdamkier-del.github.io'
PUBLIC='https://pdamkier-del.github.io/fpl-analytics-app/'
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=32768
jobs={};lock=threading.Lock();TTL=3600

def require_forecast_snapshot(forecast,expected):
    sys.path.insert(0,str(ROOT/'src'))
    from fpl_v1_1_model.forecast_snapshot import require_snapshot,forecast_digest
    # Original clients predate content seals; preserve their API while binding
    # the server-side computation to the full content, not just its cutoff.
    if expected is None:return forecast_digest(forecast)
    return require_snapshot(forecast,expected)

def get_public(name):
    with urlopen(Request(PUBLIC+name,headers={'Cache-Control':'no-cache','User-Agent':'FPLAnalyticsPrivateCompute/1'}),timeout=30) as r:return r.read()
def verify_current_window(forecast,bootstrap,now=None,*,preview=False):
    from scripts.verify_official_forecast_window import verify
    now=now or datetime.now(timezone.utc)
    model='B_locked_PM_preview' if preview else 'original_locked_vFinal_diagnostic'
    if forecast.get('locked_model_active') is not False or forecast.get('model')!=model:raise ValueError('Invalid forecast contract')
    if preview and (forecast.get('scope')!='prospective_preview' or not forecast.get('mm_version') or forecast.get('minute_sampler_audit',{}).get('sampler')!='locked'):
        raise ValueError('Current B preview with locked minute sampler required')
    cutoff=datetime.fromisoformat(forecast['data_asof'].replace('Z','+00:00'))
    limit=forecast.get('freshness_limit_hours')
    if not isinstance(limit,(int,float)) or not 0<limit<=24 or not cutoff<=now<=cutoff+timedelta(hours=limit):raise ValueError('Forecast freshness expired')
    gw=verify(forecast,bootstrap,now)
    sys.path.insert(0,str(ROOT/'src'))
    from fpl_v1_1_model.forecast_snapshot import require_official_catalog
    require_official_catalog(forecast,bootstrap.get('elements'))
    return gw
def verify_official_now(forecast,*,preview=False):
    with urlopen(Request('https://fantasy.premierleague.com/api/bootstrap-static/',headers={'Cache-Control':'no-cache'}),timeout=30) as r:bootstrap=json.load(r)
    return verify_current_window(forecast,bootstrap,preview=preview)
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
                   supports_idempotent_submit=True,
                   supports_mm_preview=True,
                   adapter_sha256=hashlib.sha256((ROOT/'service/app.py').read_bytes()+(ROOT/'service/manager_job.py').read_bytes()).hexdigest()), (200 if ready else 503)
@app.route('/plans',methods=['POST','OPTIONS'])
def create(preview=False):
    if request.method=='OPTIONS':return ('',204)
    if request.headers.get('Origin')!=ORIGIN:return jsonify(error='Invalid app origin'),403
    if not original_runtime_ready():return jsonify(error='Original Python-beregningstjeneste er ikke klar. Prøv igen senere.'),503
    cleanup()
    body=request.get_json(silent=True)
    if not isinstance(body,dict) or not isinstance(body.get('state'),dict) or not isinstance(body.get('forecast_cutoff'),str):return jsonify(error='Ugyldigt manager-state'),400
    if preview or body.get('forecast_sha256') is not None:
        if not isinstance(body.get('forecast_sha256'),str) or not re.fullmatch('[a-f0-9]{64}',body['forecast_sha256']):return jsonify(error='Forecastets indholds-id mangler. Opdatér appen og prøv igen.'),400
    identifier=body.get('request_id');key=body.get('request_key')
    if identifier is not None or key is not None:
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier) or not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9_-]{43}',key):return jsonify(error='Ugyldig privat jobkvittering'),400
    else:identifier=secrets.token_hex(16);key=secrets.token_urlsafe(32)
    signature=hashlib.sha256(json.dumps({'state':body['state'],'forecast_cutoff':body['forecast_cutoff'],'forecast_sha256':body.get('forecast_sha256'),'preview':preview},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    with lock:
        existing=jobs.get(identifier)
        if existing:
            if not secrets.compare_digest(existing['key'],key) or existing.get('signature')!=signature:return jsonify(error='Privat jobkvittering passer ikke til hold og forecast'),409
            return jsonify(id=identifier,key=key),202
        if any(j['status']=='running' for j in jobs.values()):return jsonify(error='Beregningstjenesten er optaget. Prøv igen om lidt.'),429
        if len(jobs)>=12:return jsonify(error='Midlertidig kapacitetsgrænse. Prøv igen senere.'),429
        directory=Path(tempfile.mkdtemp(prefix='fpl-private-'))
        jobs[identifier]={'key':key,'signature':signature,'directory':directory,'created':time.time(),'status':'running'}
    def work():
        try:
            forecast_path='mm-preview/current/forecast.json' if preview else 'vfinal-diagnostic.json'
            forecast=json.loads(get_public(forecast_path))
            official=json.loads(get_public('current-players.json'))
            if forecast['data_asof']!=body['forecast_cutoff'] or forecast['gws'][0]!=official['next_gw']:raise ValueError('Forecast changed')
            expected_content=require_forecast_snapshot(forecast,body.get('forecast_sha256'))
            if preview:verify_official_now(forecast,preview=True)
            else:verify_official_now(forecast)
            (directory/'input.json').write_text(json.dumps(dict(forecast=forecast,state=body['state'])))
            if forecast.get('tc_scenarios'):(directory/'tc.csv.gz').write_bytes(get_public('mm-preview/current/tc-samples.csv.gz' if preview else 'tc-samples.csv.gz'))
            completed=subprocess.run([sys.executable,str(ROOT/'scripts/locked_numerical_runtime.py'),str(ROOT/'service/manager_job.py'),str(directory)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1800)
            if completed.returncode!=0:raise ValueError('Original computation rejected input')
            require_forecast_snapshot(forecast,body.get('forecast_sha256'))
            if preview:verify_official_now(forecast,preview=True)
            else:verify_official_now(forecast)
            latest_content=require_forecast_snapshot(json.loads(get_public(forecast_path)),body.get('forecast_sha256'))
            if latest_content!=expected_content:raise ValueError('Forecast content changed during calculation')
            if preview:
                # Presentation identity only; original worker/TS decisions stay unchanged.
                result=json.loads((directory/'result.json').read_text())
                result['forecast_sha256']=expected_content
                result['forecast_variant']='B_locked_PM_preview'
                (directory/'result.json').write_text(json.dumps(result,allow_nan=False))
            jobs[identifier]['status']='completed'
        except subprocess.TimeoutExpired:
            jobs[identifier]['status']='failed';jobs[identifier]['failure']='timeout'
        except (TimeoutError,URLError):
            jobs[identifier]['status']='failed';jobs[identifier]['failure']='source_unavailable'
        except Exception:
            jobs[identifier]['status']='failed'
        finally:
            (directory/'input.json').unlink(missing_ok=True);(directory/'tc.csv.gz').unlink(missing_ok=True)
    threading.Thread(target=work,daemon=True).start()
    return jsonify(id=identifier,key=key),202
@app.route('/preview/plans',methods=['POST','OPTIONS'])
def create_mm_preview():
    """Opt-in B feed; same original worker, no arbitrary forecast URLs/fallback."""
    return create(preview=True)
@app.route('/plans/<identifier>',methods=['GET','OPTIONS'])
def status(identifier):
    if request.method=='OPTIONS':return ('',204)
    job=jobs.get(identifier)
    if not job or not secrets.compare_digest(job['key'],request.headers.get('X-Plan-Key','')):return jsonify(error='Beregningen findes ikke længere. Beregn igen.'),404
    if time.time()-job['created']>TTL:return jsonify(error='Beregningen er udløbet. Beregn igen.'),410
    if job['status']=='failed':
        errors={'timeout':'Beregningen fik timeout. Dit hold er bevaret; prøv igen.',
                'source_unavailable':'Officielle kilder kunne ikke verificeres. Dit hold er bevaret; prøv igen senere.'}
        return jsonify(status='failed',error=errors.get(job.get('failure'),'Beregningen bestod ikke kontrollerne. Kontrollér hold, tidspunkt og forecast, og prøv igen.')),422
    if job['status']=='completed':
        try:
            result=json.loads((job['directory']/'result.json').read_text())
            if not isinstance(result,dict):raise ValueError('Invalid private result')
        except (OSError,ValueError,TypeError):
            return jsonify(status='failed',error='Det private resultat kunne ikke valideres. Beregn igen.'),422
        return jsonify(status='completed',plan=result)
    return jsonify(status='running')
