#!/usr/bin/env python3
"""Fetch source-attributed expert XI coordinates, without mislabelling as MM predictions.

Lineup source: Fantasy Football Pundit, public weekly team-news page.
The prediction is external (not locked FPL MM P(start)); its team positioning is
copied as source coordinates, not reverse-engineered from player FPL position.

On failure, writes a valid empty dataset. Never ship a stale or invented XI.
"""
from __future__ import annotations
import argparse,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE="https://www.fantasyfootballpundit.com/fantasy-premier-league-team-news/"
OFFICIAL=ROOT/"data_v1_1/derived/fpl_schedule_knowledge/live/latest.json"
OUT=ROOT/"app/expert-lineups.js"
PITCH_RE=re.compile(
  r'<div class="[^"]*Formation-module[^"]*__pitch"[^>]*'
  r'aria-label="([^"]+)"[^>]*>.*?<ul class="[^"]*__players">(.*?)</ul>',
  re.S | re.I)
PLAYER_RE=re.compile(
  r'<li class="[^"]*__player"[^>]*style="[^"]*--x:\s*([0-9.]+)%;'
  r'\s*--y:\s*([0-9.]+)%;?[^"]*"[^>]*>(.*?)</li>',re.S|re.I)
NAME_RE=re.compile(r'<span class="[^"]*__name"[^>]*>(.*?)</span>',re.S|re.I)
TIME_RE=re.compile(r'<time\b[^>]*dateTime="([^"]+)"',re.I)
GW_RE=re.compile(r'__fixtureGw">\s*GW\s*(?:<!--\s*-->)?\s*([0-9]+)',re.I)
ALIASES={
 "spurs":"tottenham hotspur","tottenham":"tottenham hotspur",
 "man city":"manchester city","man united":"manchester united",
 "man utd":"manchester united","brighton":"brighton and hove albion",
 "wolves":"wolverhampton wanderers","newcastle":"newcastle united",
 "west ham":"west ham united","nottingham forest":"nottingham forest",
 "forest":"nottingham forest","nottm forest":"nottingham forest","leeds":"leeds united",
 "leicester":"leicester city","ipswich":"ipswich town",
 "hull":"hull city","coventry":"coventry city",
 "crystal palace":"crystal palace",
 "bournemouth":"bournemouth","afc bournemouth":"bournemouth",
 "aston villa":"aston villa"
}
def normal(value):
    v=html.unescape(value or '').lower().strip().replace('&','and')
    v=re.sub(r'[^a-z0-9 ]','',v)
    v=' '.join(v.split())
    return v[4:] if v.startswith('the ') else v
def canonical(value): return ALIASES.get(normal(value),normal(value))
def parse(html_text,official,*,observed_at=None):
    team_names={canonical(t.get('name')):t for t in official.get('teams',[])}
    team_names.update({canonical(t.get('short_name')):t for t in official.get('teams',[])})
    expected=int(official.get('official_next_gw') or 0)
    rows=[]; invalid=[]
    for m in PITCH_RE.finditer(html_text):
        title=html.unescape(m.group(1))
        if ' predicted lineup:' not in title:continue
        name=title.split(' predicted lineup:',1)[0]
        team=team_names.get(canonical(name))
        if not team:
            invalid.append('unmapped team '+name);continue
        lookback=html_text[max(0,m.start()-1600):m.start()]
        gw_match=list(GW_RE.finditer(lookback))
        gw=int(gw_match[-1].group(1)) if gw_match else 0
        time_match=list(TIME_RE.finditer(lookback))
        updated=html.unescape(time_match[-1].group(1)) if time_match else None
        if gw!=expected:
            invalid.append(name+' stale GW '+str(gw));continue
        players=[]
        for p in PLAYER_RE.finditer(m.group(2)):
            n=NAME_RE.search(p.group(3))
            if not n:continue
            text=html.unescape(re.sub(r'<[^>]+>','',n.group(1))).strip()
            x,y=float(p.group(1)),float(p.group(2))
            if not text or not (5<=x<=95 and 5<=y<=95):continue
            players.append({'name':text,'x':round(x,2),'y':round(y,2)})
        if len(players)!=11 or len({normal(p['name']) for p in players})!=11:
            invalid.append(name+' incomplete or duplicated XI '+str(len(players)));continue
        rows.append({'team_id':int(team['id']),'club':team['short_name'],
                     'team_name':team['name'],'gw':gw,'updated':updated,
                     'players':players,'source':'Fantasy Football Pundit'})
    return {'source_url':SOURCE,'source_kind':'independent_expert_predicted_xi',
            'observed_at_utc':observed_at,
            'official_next_gw':expected,'lineups':rows,'rejected':invalid,
            'warnings':['Eksperternes forventede start-XI er ikke beregnet af MM.',
                        'Koordinaterne er fra den eksterne kilde. Vis aldrig disse som vores P(start)/xMins.',
                        'Skiftende opstillinger kan afvige fra den faktiske XI.']}
def capture(*,official_path=OFFICIAL,out_path=OUT,fetch=None):
    official=json.loads(Path(official_path).read_text('utf8'))
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    try:
        if fetch is None:
            req=urllib.request.Request(SOURCE,headers={'User-Agent':'Mozilla/5.0 (FPL Analytics personal-use forecast)','Accept':'text/html'})
            with urllib.request.urlopen(req,timeout=25) as r:page=r.read(1800000).decode('utf8','replace')
        else:page=fetch(SOURCE)
        report=parse(page,official,observed_at=now)
    except (OSError,ValueError,TimeoutError) as exc:
        report={'source_url':SOURCE,'source_kind':'independent_expert_predicted_xi',
                'observed_at_utc':now,'official_next_gw':official.get('official_next_gw'),
                'lineups':[],'rejected':[type(exc).__name__+': '+str(exc)[:180]],
                'warnings':['Kunne ikke hente den aktuelle eksterne forventede start-XI.']}
    path=Path(out_path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('window.FPL_EXPERT_LINEUPS='+json.dumps(report,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf8')
    print('EXPERT_PREDICTED_XI',json.dumps({'gw':report['official_next_gw'],'valid_teams':len(report['lineups']),
          'rejected':report['rejected'][:8]},ensure_ascii=False),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--official',default=str(OFFICIAL))
    p.add_argument('--out',default=str(OUT))
    args=p.parse_args()
    capture(official_path=args.official,out_path=args.out)
