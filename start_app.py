from __future__ import annotations
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import json, os, threading, webbrowser, socket

ROOT=Path(__file__).resolve().parent
APP=ROOT/'app'
USER=ROOT/'user'
USER.mkdir(exist_ok=True)
os.chdir(APP)

import sys
sys.path.insert(0,str(ROOT/'model'))
import engine
import decision_optimizer

DEFAULT_SQUAD_IDS=[496,572,8,173,204,229,469,15,40,154,290,399,165,346,411]

def load_squad():
    f=USER/'squad.json'
    if f.exists():
        try:
            data=json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            data={}
    else:
        data={}
    if not data.get('player_ids'):
        data['player_ids']=DEFAULT_SQUAD_IDS[:]
        try:
            f.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception:
            pass
    return data

def load_base_data():
    return json.loads((ROOT/'model/base_data.json').read_text(encoding='utf-8'))

class Handler(SimpleHTTPRequestHandler):
    def _json(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/api/health': return self._json({'ok':True,'app':'FPL Desktop Web App'})
        if p=='/api/model/config': return self._json(engine.active_config())
        if p=='/api/update/status':
            f=USER/'update_status.json'
            return self._json(json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'ok':True,'app_version':(ROOT/'VERSION.txt').read_text(encoding='utf-8').strip() if (ROOT/'VERSION.txt').exists() else 'unknown','data_version':(ROOT/'DATA_VERSION.txt').read_text(encoding='utf-8').strip() if (ROOT/'DATA_VERSION.txt').exists() else 'unknown'})
        if p=='/api/user/squad':
            return self._json(load_squad())
        if p=='/api/model/versions': return self._json(engine.list_versions())
        if p=='/api/model/status':
            d=engine.active_config(); base=json.loads((ROOT/'model/base_data.json').read_text(encoding='utf-8'))
            return self._json({'active_version':d.get('version'),'engine_mode':d.get('engine_mode'),'source_model_version':base.get('meta',{}).get('model_version'),'forecast_players':len(base.get('forecasts',[])),'actual_rows':len(base.get('actuals',[])),'fixtures':len(base.get('fixtures',[]))})
        if p=='/': self.path='/overview.html'
        return super().do_GET()
    def do_POST(self):
        p=urlparse(self.path).path
        try:
            length=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(length) or b'{}')
            if p=='/api/model/config': return self._json(engine.save_version(payload),201)
            if p=='/api/model/activate': return self._json(engine.activate(payload.get('version','')))
            if p=='/api/model/run': return self._json(engine.run_model())
            if p=='/api/optimizer/plan':
                squad=load_squad(); data=load_base_data()
                return self._json(decision_optimizer.optimize_plan(data,squad,payload))
            if p=='/api/optimizer/manual':
                squad=load_squad(); data=load_base_data()
                return self._json(decision_optimizer.manual_transfer(data,squad,payload))
            if p=='/api/user/squad':
                current=load_squad()
                merged=dict(current); merged.update(payload)
                ids=[int(x) for x in merged.get('player_ids',[])][:15]
                merged['player_ids']=ids
                (USER/'squad.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
                return self._json(merged,201)
            return self._json({'error':'not found'},404)
        except Exception as e:
            return self._json({'error':str(e)},400)
    def log_message(self,fmt,*args):
        print('[FPL]',fmt%args)

def free_port(preferred=8765):
    for port in range(preferred,preferred+20):
        with socket.socket() as s:
            try: s.bind(('127.0.0.1',port)); return port
            except OSError: pass
    raise RuntimeError('No free local port found')

if __name__=='__main__':
    port=free_port(); url=f'http://127.0.0.1:{port}/overview.html'
    print('\nFPL Desktop Web App')
    print('Open:',url)
    print('Keep this window open while you use the app. Press Ctrl+C to stop.\n')
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    threading.Timer(0.8,lambda:webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
