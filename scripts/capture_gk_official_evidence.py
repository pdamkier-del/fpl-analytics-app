#!/usr/bin/env python3
"""Archive direct official squad evidence; no individual non-FPL forecasts."""
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
import hashlib,json,re,unicodedata,urllib.request
ROOT=Path(__file__).resolve().parents[1]
URLS={'chelsea_squad':'https://www.chelseafc.com/en/teams/mens-profiles',
      'chelsea_injury':'https://www.chelseafc.com/en/news/article/injury-update-emiliano-martinez',
      'fpl_bootstrap':'https://fantasy.premierleague.com/api/bootstrap-static/'}
def canonical(s):return re.sub('[^a-z]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
class Squad(HTMLParser):
    def __init__(self):super().__init__();self.players=[]
    def handle_starttag(self,tag,attrs):
        def walk(x):
            if isinstance(x,dict):
                if x.get('playerPosition')=='Goalkeeper':self.players.append(x)
                for v in x.values():walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
        for _,v in attrs:
            if v and 'playerFirstName' in v:
                try:walk(json.loads(v))
                except ValueError:pass

def capture(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);sources={};raw={}
    for key,url in URLS.items():
        data=urllib.request.urlopen(url,timeout=40).read();at=datetime.now(timezone.utc).isoformat()
        path=out/(key+('.json'if key=='fpl_bootstrap'else'.html'));path.write_bytes(data)
        sources[key]=dict(url=url,observed_at=at,sha256=hashlib.sha256(data).hexdigest());raw[key]=data
    bootstrap=json.loads(raw['fpl_bootstrap']);team=next(t for t in bootstrap['teams']if t['name']=='Chelsea')
    official=[p for p in bootstrap['elements']if p['team']==team['id']and p['element_type']==1]
    parser=Squad();parser.feed(raw['chelsea_squad'].decode())
    men={canonical(p['playerFirstName']+p['playerLastName']):p for p in parser.players if 'mensteam'in p.get('teams',[])}
    if not any('penders'in n for n in men):raise ValueError('Chelsea squad parser lacks Penders')
    names={canonical(p.get('first_name','')+p.get('second_name',''))for p in official}
    # Full names differ in middle names; confirmed FPL surnames are also checked.
    missing=[p for n,p in men.items()if n not in names and not any(canonical(q['web_name'])in n for q in official)]
    evidence=dict(observed_at=max(x['observed_at']for x in sources.values()),sources=sources,team_id=team['id'],
        first_team_goalkeepers=[dict(name=(p['playerFirstName']+' '+p['playerLastName']).strip(),url='https://www.chelseafc.com'+p['playerProfileLink']['url'])for p in men.values()],
        unlisted_competitors=[(p['playerFirstName']+' '+p['playerLastName']).strip()for p in missing],
        fpl_goalkeepers=[{k:p.get(k)for k in ['id','web_name','status','news','news_added','chance_of_playing_next_round']}for p in official])
    (out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');return evidence
if __name__=='__main__':print(json.dumps(capture(ROOT/'work/gk-official-evidence'),indent=2))
