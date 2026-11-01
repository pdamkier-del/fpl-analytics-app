"""Offline/free-source trial. No imports from active MM, PM, TS or app.

Reuse the existing expert-XI and official-availability collectors. Provider
predictions are attributed opinions, never official confirmation or calibrated p.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
import argparse, hashlib, json, re, unicodedata
import requests
from snapshot_predicted_lineups import canonical, parse as parse_pundit
from collect_dashboard_news import build as official_news

URLS={'fpl':'https://fantasy.premierleague.com/api/bootstrap-static/',
      'fixtures':'https://fantasy.premierleague.com/api/fixtures/',
      'rotowire':'https://www.rotowire.com/soccer/lineups.php',
      'sportsmole':'https://www.sportsmole.co.uk/football/preview/',
      'pundit':'https://www.fantasyfootballpundit.com/fantasy-premier-league-team-news/'}


def clock(s):
    t=datetime.fromisoformat(s.replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('Timezone required')
    return t.astimezone(timezone.utc)


def identity(s):
    return ' '.join(re.sub(r'[^a-z0-9 ]',' ',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).split())


class Node:
    def __init__(self,tag='',attrs=None):self.tag=tag;self.attrs=dict(attrs or []);self.children=[]
    def has(self,cls):return cls in self.attrs.get('class','').split()
    def find(self,cls):return [n for n in self.walk()if n.has(cls)]
    def walk(self):
        for c in self.children:
            if isinstance(c,Node):yield c;yield from c.walk()
    def text(self):return ' '.join(' '.join(c.text()if isinstance(c,Node)else c for c in self.children).split())


class Tree(HTMLParser):
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self,text):super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(text)
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in self.VOID:self.stack.append(n)
    def handle_startendtag(self,tag,attrs):
        self.stack[-1].children.append(Node(tag,attrs))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):self.stack[-1].children.append(data)


def team_index(bootstrap):
    teams={}
    for t in bootstrap['teams']:
        for s in [t['name'],t['short_name']]:teams.setdefault(canonical(s),set()).add(t['id'])
    return teams


def player_match(name,team,bootstrap):
    # Exact normalized full/web name within the verified current club only.
    # No initials/surname/fuzzy guess, no propagation of provider club conflicts.
    hits=[]
    for p in bootstrap['elements']:
        if p['team']==team and identity(name)in {identity(p['first_name']+' '+p['second_name']),identity(p['web_name'])}:hits.append(p)
    return hits[0]if len(hits)==1 else None


def parse_rotowire(text,bootstrap,fixtures,observed_at):
    at=clock(observed_at);teams=team_index(bootstrap);root=Tree(text).root;rows=[];rejected=[]
    for card in root.find('lineup'):
        if not card.has('is-soccer'):continue
        names=card.find('lineup__mteam');times=card.find('lineup__time')
        if len(names)!=2 or len(times)!=1:rejected.append({'reason':'malformed_fixture'});continue
        ids=[teams.get(canonical(n.text()),set())for n in names]
        if any(len(v)!=1 for v in ids):rejected.append({'reason':'unmapped_teams','teams':[n.text()for n in names]});continue
        home,away=[next(iter(v))for v in ids]
        candidates=[]
        # RotoWire explicitly labels ET; handle EDT/EST through America/New_York.
        for year in [at.year-1,at.year,at.year+1]:
            try:ko=datetime.strptime(str(year)+' '+times[0].text(),'%Y %B %d %I:%M %p ET').replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
            except ValueError:continue
            candidates.extend(f for f in fixtures if f['team_h']==home and f['team_a']==away and f.get('kickoff_time')and clock(f['kickoff_time'])==ko)
        if len(candidates)!=1:rejected.append({'reason':'unmatched_fixture_clock','home':home,'away':away});continue
        f=candidates[0]
        if clock(f['kickoff_time'])<=at or f.get('started')or card.has('has-started'):
            rejected.append({'fixture_id':f['id'],'reason':'already_started'});continue
        lists=card.find('lineup__list')
        if len(lists)!=2:rejected.append({'fixture_id':f['id'],'reason':'malformed_sides'});continue
        for team,side in zip([home,away],['is-home','is-visit']):
            side_lists=[n for n in lists if n.has(side)]
            if len(side_lists)!=1:rejected.append({'fixture_id':f['id'],'reason':'ambiguous_side'});continue
            ul=side_lists[0];status=ul.find('lineup__status');label=status[0].text()if len(status)==1 else ''
            kind={'Confirmed Lineup':'provider_reported_confirmed','Expected Lineup':'editorial_prediction','Predicted Lineup':'editorial_prediction','Unknown Lineup':'not_posted'}.get(label,'unrecognized')
            if kind=='unrecognized':rejected.append({'fixture_id':f['id'],'reason':'unknown_status','label':label});continue
            selection=[];injuries=[];after_injuries=False
            for li in ul.children:
                if not isinstance(li,Node):continue
                if li.has('lineup__title')and li.text()=='Injuries':after_injuries=True
                if not li.has('lineup__player'):continue
                anchors=[n for n in li.walk()if n.tag=='a'and n.attrs.get('href','').startswith('/soccer/player/')]
                if len(anchors)!=1:continue
                a=anchors[0];name=a.attrs.get('title')or a.text();p=player_match(name,team,bootstrap)
                item={'source_name':name,'player_id':p['id']if p else None,'identity':'exact_current_club'if p else 'unresolved','source_player_url':urljoin(URLS['rotowire'],a.attrs['href'])}
                if after_injuries:
                    flags=li.find('lineup__inj');item['source_status']=flags[0].text()if len(flags)==1 else None
                    item['official_fpl_status']=p.get('status')if p else None
                    item['official_fpl_news']=p.get('news')if p else None
                    item['official_confirmation']=False;injuries.append(item)
                else:selection.append(item)
            valid=len(selection)==11 and all(p['player_id']is not None for p in selection)and len({p['player_id']for p in selection})==11
            eligible=kind=='editorial_prediction'and valid
            rows.append(dict(fixture_id=f['id'],gw=f.get('event'),team_id=team,kickoff=f['kickoff_time'],source_url=URLS['rotowire'],source_kind=kind,source_published_at=None,observed_at=observed_at,source_label=label,players=selection,reported_absences=injuries,complete_mapped_xi=valid,eligible_editorial_xi=eligible,official_confirmation=False,model_input_enabled=False))
    return {'rows':rows,'rejected':rejected}


def discover_sportsmole(text):
    # Discovery only. A URL/title cannot prove kickoff, publication time or XI.
    found={}
    for n in Tree(text).root.walk():
        if n.tag!='a':continue
        url=urljoin(URLS['sportsmole'],n.attrs.get('href',''));u=urlparse(url)
        if u.netloc!='www.sportsmole.co.uk'or not re.search(r'/football/.+/preview/.+_\d+\.html$',u.path):continue
        title=n.text()
        if title:found[url]=dict(url=url,title=title[:240],fixture_verified=False,model_input_enabled=False)
    return list(found.values())



def parse_sportsmole_article(text,receipt):
    """Preserve attributed preview metadata; never guess a PL fixture from text."""
    at=clock(receipt['observed_at']);root=Tree(text).root
    published=re.findall(r'"datePublished"\s*:\s*"([^"]+)"',text)
    modified=re.findall(r'"dateModified"\s*:\s*"([^"]+)"',text)
    published=sorted(set(published));modified=sorted(set(modified))
    if len(published)!=1 or any(clock(t)>at for t in published+modified):raise ValueError('Invalid article publication clock')
    headings=[n.text()for n in root.walk()if n.tag=='h1']
    if len(headings)!=1:raise ValueError('Ambiguous article headline')
    paragraphs=[n for n in root.walk()if n.tag=='p'];lineups=[]
    for i,n in enumerate(paragraphs[:-1]):
        if n.text().endswith('possible starting lineup:'):
            names=[x.strip()for x in re.split('[;,]',paragraphs[i+1].text())if x.strip()]
            lineups.append(dict(source_team=n.text().split(' possible starting lineup:')[0],source_player_names=names,eleven_names=len(names)==11,players_identity_verified=False))
    return dict(source_url=receipt['url'],observed_at=receipt['observed_at'],source_published_at=published[0],source_modified_at=modified[0]if len(modified)==1 else None,headline=headings[0],source_kind='editorial_preview',competition_url_hint='league-cup'if '/league-cup/'in receipt['url']else None,possible_lineups=lineups,fixture_verified=False,official_confirmation=False,model_input_enabled=False)


def build(archive):
    archive=Path(archive);receipts=json.loads((archive/'receipts.json').read_text());bykey={x['key']:x for x in receipts}
    for k in URLS:
        r=bykey[k]
        if r['url']!=URLS[k]or r['status']!=200:raise ValueError('Missing trusted source: '+k)
        if hashlib.sha256((archive/(k+'.raw')).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Source checksum mismatch: '+k)
        clock(r['observed_at'])
    b=json.loads((archive/'fpl.raw').read_bytes());f=json.loads((archive/'fixtures.raw').read_bytes())
    official=official_news(b,bykey['fpl']['observed_at']);gw=official['next_gw']
    rot=parse_rotowire((archive/'rotowire.raw').read_text(),b,f,bykey['rotowire']['observed_at'])
    pundit=parse_pundit((archive/'pundit.raw').read_text(),{'official_next_gw':gw,'teams':b['teams']},observed_at=bykey['pundit']['observed_at'])
    # Existing Pundit parser is reused as a GW freshness diagnostic only: it
    # lacks exact fixture/player ID validation required by this trial's contract.
    discovery=discover_sportsmole((archive/'sportsmole.raw').read_text())
    rows=[r for r in rot['rows']if r['gw']==gw]
    expected={f['id']for f in f if f.get('event')==gw};covered={r['fixture_id']for r in rows}
    article=None
    article_receipt=archive/'article-receipt.json'
    if article_receipt.exists():
        ar=json.loads(article_receipt.read_text());raw=(archive/'sportsmole-article.raw').read_bytes()
        if ar['url']not in {x['url']for x in discovery}or ar['status']!=200 or hashlib.sha256(raw).hexdigest()!=ar['sha256']:raise ValueError('Unverified discovered article')
        article=parse_sportsmole_article(raw.decode(),ar);receipts.append(ar)
    if len({(r['fixture_id'],r['team_id'])for r in rot['rows']})!=len(rot['rows']):raise ValueError('Duplicate team fixture evidence')
    return dict(sportsmole_article=article,schema='free-match-intel-trial-v1',sources=receipts,next_gw=gw,deadline=official['deadline'],rotowire=rot,pundit_freshness=pundit,sportsmole_discovery=discovery,coverage={'next_gw_fixtures':len(expected),'rotowire_next_gw_fixtures':len(covered),'missing_fixture_ids':sorted(expected-covered),'next_gw_team_rows':len(rows),'eligible_editorial_xis':sum(r['eligible_editorial_xi']for r in rows),'not_posted_team_rows':sum(r['source_kind']=='not_posted'for r in rows),'pundit_current_gw_lineups':len(pundit['lineups']),'sportsmole_discovery_links':len(discovery)},official_availability=official,active_model_changed=False,production_changed=False,limits=['Live capture is knowledge from observation time, not a historical publication timestamp','Provider-reported confirmed XIs are not independently official-confirmed','No inferred rest, injury cause, cross-source independence or calibrated start probability','Sports Mole discovery is not complete coverage or verified fixture evidence','Pundit reuse checks GW only; not eligible model input','No app integration, automatic schedule or forecast change'])


def capture(archive,article_url=None):
    archive=Path(archive)
    if archive.exists():raise ValueError('Use a new append-only capture directory')
    archive.mkdir(parents=True);receipts=[]
    for key,url in URLS.items():
        r=requests.get(url,timeout=35,headers={'User-Agent':'Mozilla/5.0 FPLAnalytics free source trial'});at=datetime.now(timezone.utc).isoformat();r.raise_for_status()
        (archive/(key+'.raw')).write_bytes(r.content);receipts.append(dict(key=key,url=url,final_url=r.url,status=r.status_code,observed_at=at,sha256=hashlib.sha256(r.content).hexdigest()))
    (archive/'receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    if article_url:
        discovered=discover_sportsmole((archive/'sportsmole.raw').read_text())
        if article_url not in {x['url']for x in discovered}:raise ValueError('Article must be in captured discovery index')
        r=requests.get(article_url,timeout=35,headers={'User-Agent':'Mozilla/5.0 FPLAnalytics free source trial'});r.raise_for_status()
        (archive/'sportsmole-article.raw').write_bytes(r.content)
        (archive/'article-receipt.json').write_text(json.dumps(dict(key='sportsmole_article',url=article_url,final_url=r.url,status=r.status_code,observed_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(r.content).hexdigest()),indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--capture',action='store_true');p.add_argument('--article-url');a=p.parse_args()
    if a.capture:capture(a.archive,a.article_url)
    report=build(a.archive);a.out.mkdir(parents=True,exist_ok=True);(a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['coverage'],indent=2))
if __name__=='__main__':main()
