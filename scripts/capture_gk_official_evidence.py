#!/usr/bin/env python3
"""Archive direct official squad evidence; no individual non-FPL forecasts."""
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
import hashlib,json,re,unicodedata,urllib.request
from time import time_ns
ROOT=Path(__file__).resolve().parents[1]
URLS={'chelsea_squad':'https://www.chelseafc.com/en/teams/mens-profiles',
      'chelsea_injury':'https://www.chelseafc.com/en/news/article/injury-update-emiliano-martinez',
      'chelsea_everton_lineup':'https://www.chelseafc.com/en/news/article/confirmed-chelsea-line-up-vs-everton-171026',
      'chelsea_everton_report':'https://www.chelseafc.com/en/news/article/match-report-everton-0-2-chelsea',
      'chelsea_coach_update':'https://www.chelseafc.com/en/news/article/alonso-issues-emiliano-martinez-update',
      'chelsea_penders_profile':'https://www.chelseafc.com/en/teams/profile/mike-penders',
      'chelsea_sharman_lowe_profile':'https://www.chelseafc.com/en/teams/profile/teddy-sharman-lowe',
      'chelsea_slonina_profile':'https://www.chelseafc.com/en/teams/profile/gabriel-slonina',
      'fpl_bootstrap':'https://fantasy.premierleague.com/api/bootstrap-static/'}
def canonical(s):return re.sub('[^a-z]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
class Article(HTMLParser):
    def __init__(self):super().__init__();self.published_at=None;self.text=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        def walk(x):
            if isinstance(x,dict):
                if 'content_publish_date'in x:self.published_at=x['content_publish_date']
                for v in x.values():walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
        for _,v in attrs:
            if v and 'content_publish_date'in v:
                try:walk(json.loads(v))
                except ValueError:pass
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.text.append(data.strip())

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

def fetch_squad(url, *, attempts=3, opener=None):
    """Reject the club's occasional staff-only payload; retry uncached, never infer absence."""
    opener=opener or urllib.request.urlopen
    rejected=[]
    for attempt in range(attempts):
        requested=url if attempt==0 else url+('&'if '?'in url else '?')+'evidence_capture='+str(time_ns())
        request=urllib.request.Request(requested,headers={'Cache-Control':'no-cache'})
        with opener(request,timeout=40)as response:data=response.read()
        parser=Squad();parser.feed(data.decode())
        if any('mensteam'in p.get('teams',[])for p in parser.players):
            return data,dict(requested_url=requested,retrieval_attempt=attempt+1,
                rejected_responses=rejected,
                squad_scope='Parsed first-team goalkeeper registrations; registration is not match availability.')
        rejected.append(dict(requested_url=requested,sha256=hashlib.sha256(data).hexdigest(),
            observed_at=datetime.now(timezone.utc).isoformat(),reason='No parsed first-team goalkeeper registrations'))
    raise ValueError('Official squad returned no first-team goalkeeper registrations after validated retries; availability is unknown')

def capture(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);sources={};raw={}
    for key,url in URLS.items():
        extra={}
        if key=='chelsea_squad':data,extra=fetch_squad(url)
        else:data=urllib.request.urlopen(url,timeout=40).read()
        at=datetime.now(timezone.utc).isoformat()
        path=out/(key+('.json'if key=='fpl_bootstrap'else'.html'));path.write_bytes(data)
        sources[key]=dict(url=url,observed_at=at,sha256=hashlib.sha256(data).hexdigest(),**extra);raw[key]=data
        if key!='fpl_bootstrap':
            article=Article();article.feed(data.decode());sources[key]['published_at']=article.published_at
    bootstrap=json.loads(raw['fpl_bootstrap']);team=next(t for t in bootstrap['teams']if t['name']=='Chelsea')
    official=[p for p in bootstrap['elements']if p['team']==team['id']and p['element_type']==1]
    parser=Squad();parser.feed(raw['chelsea_squad'].decode())
    men={canonical(p['playerFirstName']+p['playerLastName']):p for p in parser.players if 'mensteam'in p.get('teams',[])}
    if not men:raise ValueError('Official squad contains no parsed first-team goalkeepers')
    names={canonical(p.get('first_name','')+p.get('second_name',''))for p in official}
    # Full names differ in middle names; confirmed FPL surnames are also checked.
    missing=[p for n,p in men.items()if n not in names and not any(canonical(q['web_name'])in n for q in official)]
    evidence=dict(observed_at=max(x['observed_at']for x in sources.values()),sources=sources,team_id=team['id'],
        first_team_goalkeepers=[dict(name=(p['playerFirstName']+' '+p['playerLastName']).strip(),url='https://www.chelseafc.com'+p['playerProfileLink']['url'])for p in men.values()],
        unlisted_competitors=[(p['playerFirstName']+' '+p['playerLastName']).strip()for p in missing],
        fpl_goalkeepers=[{k:p.get(k)for k in ['id','web_name','status','news','news_added','chance_of_playing_next_round']}for p in official])
    evidence['fpl_goalkeepers_missing_from_club_registration_page']=[p['web_name']for p in official
        if not any(canonical(p['web_name'])in n or canonical(p.get('first_name','')+p.get('second_name',''))==n for n in men)]
    evidence['registration_absence_interpretation']='Missing from the parsed club page is not evidence of injury, loan or next-match unavailability.'
    evidence['loan_goalkeepers']=[dict(name=(p['playerFirstName']+' '+p['playerLastName']).strip(),teams=p.get('teams',[]))for p in {canonical(p['playerFirstName']+p['playerLastName']):p for p in parser.players if 'onLoan'in p.get('teams',[])}.values()]
    evidence['hierarchy_review']={
        'review_date':'2026-10-18',
        'scope':'Official evidence review; qualitative hierarchy is not a calibrated start forecast.',
        'martinez':'Fractured jaw, successful surgery; FPL chance 0 for next round. No official return date.',
        'penders':'Sole goalkeeper substitute vs Everton on 17 October; replaced Martinez. Two cup starts supported by club profile and coach comments. Alonso: full trust with him.',
        'sharman_lowe':'First-team registration; absent from 17 October match squad. Profile records return from loan in January 2026. No current injury or next-match availability confirmed.',
        'slonina':'First-team registration; absent from 17 October match squad. Profile records earlier bench appearances, not current selection. No current injury or next-match availability confirmed.',
        'interpretation':'Penders is the best-supported immediate deputy. Registration alone does not establish next-match availability or a 40.29% collective start chance.',
        'model_limitation':'Published v1 pool probability is residual original MM mass, not an estimate calibrated to these individual competitors. Do not interpret it as their verified combined start probability.'}
    (out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');return evidence
if __name__=='__main__':print(json.dumps(capture(ROOT/'work/gk-official-evidence'),indent=2))
