#!/usr/bin/env python3
"""Resumable original FotMob ledger. Exact joins; MM mathematics untouched."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip, hashlib, io, json, re, sys, time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from fpl_v1_1_model.external_rating_ingest import norm,extract_fotmob,map_rows,provider_competition_matches
from fpl_v1_1_model.rating_history import validate_rating_ledger
from fpl_v1_1_model.match_importance import canonical_competition
from run_mm_unified_official_roles import base_identity,read_all,SOURCE,CLASSIFIED

PIN='1c9191ab6b0c191378ea27f257fdab2bae63caba'
COMPETITIONS={47:'prem',42:'champions-league',73:'europa-league',10216:'conference-league',10615:'conference-league',132:'fa-cup',133:'efl-cup'}
BASE='https://www.fotmob.com/api/data'

class Cache:
    def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
    def get(self,url):
        path=self.path/(hashlib.sha256(url.encode()).hexdigest()+'.json.gz')
        if path.exists():
            with gzip.open(path,'rt') as f:return json.load(f)['payload']
        last=None
        for attempt in range(3):
            try:
                with urlopen(Request(url,headers={'User-Agent':'MM-research-rating-ledger/1.0'}),timeout=45) as f:
                    body=f.read()
                payload=json.loads(body)
                record={'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(body).hexdigest(),'payload':payload}
                temp=path.with_suffix('.tmp')
                with gzip.open(temp,'wt') as f:json.dump(record,f)
                temp.replace(path)
                time.sleep(.4)
                return payload
            except Exception as exc:
                last=exc
                if getattr(exc,'code',None) in (401,403,404):break
                time.sleep(1+attempt)
        raise RuntimeError(str(last))
    def manifest(self):
        rows=[]
        for p in sorted(self.path.glob('*.json.gz')):
            with gzip.open(p,'rt') as f:r=json.load(f)
            rows.append({k:r[k] for k in ['url','retrieved_at','sha256']})
        return rows


def read_source(path,destination):
    target=destination/'identity_source'/path
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        url=f'https://raw.githubusercontent.com/olbauday/FPL-Core-Insights/{PIN}/{quote(path)}'
        with urlopen(url,timeout=60) as f:target.write_bytes(f.read())
    return pd.read_csv(target)


def build_anchors(out):
    classified=pd.read_csv(CLASSIFIED)
    lines,team_map=base_identity(read_all('lineups'),classified)
    fid=defaultdict(set)
    for r in lines.dropna(subset=['player_id','player_uuid']).itertuples():fid[int(r.player_id)].add(str(r.player_uuid))
    opta=defaultdict(set)
    players=read_source('data/2025-2026/players.csv',out)
    for r in players.itertuples():opta[str(int(r.player_code))].update(fid.get(int(r.player_id),set()))
    # Strictly exact within-team full-name anchors for roster-only players.
    roster=pd.read_csv(SOURCE,usecols=['team_id','player_uuid','player']).drop_duplicates()
    roster_alias=defaultdict(set)
    for r in roster.itertuples():roster_alias[(int(r.team_id),norm(r.player))].add(str(r.player_uuid))
    for r in players.itertuples():
        team=team_map.get(int(r.team_code))
        opta[str(int(r.player_code))].update(roster_alias.get((team,norm(str(r.first_name)+' '+str(r.second_name))),set()))
    roles={(str(r.match_id),str(r.player_uuid)):str(r.final_role) for r in classified.itertuples()}
    names=defaultdict(set)
    for r in classified.itertuples():names[(str(r.match_id),int(r.team_id),norm(r.player))].add(str(r.player_uuid))
    for r in lines.dropna(subset=['player_uuid','team_code']).itertuples():
        names[(str(r.match_id),team_map.get(int(r.team_code)),norm(r.player_name))].add(str(r.player_uuid))
    registry=defaultdict(set);known=defaultdict(set)
    quarantine_path=ROOT/'analysis/results/independent-europe-audit/workload_quarantine.csv'
    quarantine=set(pd.read_csv(quarantine_path).match_id.astype(str)) if quarantine_path.exists() else set()
    def add(mid,comp,ko,code,season='2025/2026',event=None):
        if pd.isna(ko) or pd.isna(code) or str(mid) in quarantine:return
        date=pd.to_datetime(ko,utc=True).date().isoformat()
        registry[(season,canonical_competition(comp),date,int(code))].add(str(mid))
        if event:known[('fotmob',str(event))].add(str(mid))
    for r in read_all('matches').itertuples():
        ko=pd.to_datetime(r.kickoff_time,utc=True,errors='coerce')
        event=re.search(r'#(\d+)',str(r.match_url));event=event.group(1) if event else None
        for code in [r.home_team,r.away_team]:
            if pd.notna(code) and int(code) in team_map:add(r.match_id,r.tournament,ko,code,event=event)
    inverse={v:k for k,v in team_map.items()}
    for path in ['analysis/results/workload-recovered-v4/team_match_coverage.csv','analysis/results/historical-cup-recovery-v1/restored_team_games.csv']:
        f=ROOT/path
        if not f.exists():continue
        for r in pd.read_csv(f).itertuples():
            add(r.match_id,r.competition,r.kickoff,inverse.get(int(r.team_id)))
    fa=ROOT/'analysis/results/fa-match-importance-20261006-v1/fa_player_minutes_uuid.csv'
    if fa.exists():
        for r in pd.read_csv(fa).itertuples():
            add(r.match_id,r.competition,r.kickoff,r.team_code,event=int(r.source_event_id))
            names[(str(r.match_id),int(r.team_id),norm(r.player_name))].add(str(r.player_uuid))
    return team_map,opta,registry,known,names,roles,classified


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='data_v1_1/derived/mm_v2_ratings')
    ap.add_argument('--cache',default='.cache/mm-external-ratings');ap.add_argument('--as-of',default=datetime.now(timezone.utc).isoformat())
    a=ap.parse_args();out=ROOT/a.out;out.mkdir(parents=True,exist_ok=True);cache=Cache(ROOT/a.cache)
    asof=pd.to_datetime(a.as_of,utc=True)
    team_map,opta,registry,known,names,roles,classified=build_anchors(out)
    errors=[];events=[];lookups={};source_clubs={}
    for season,folder in [('2025/2026','2025-2026'),('2026/2027','2026-2027')]:
        try:teams=read_source(f'data/{folder}/teams.csv',out)
        except Exception as exc:errors.append({'season':season,'stage':'club_inventory','error':str(exc)});continue
        clubnames=defaultdict(set);clubs={}
        for r in teams.itertuples():
            code=int(r.code);clubs[code]={'team_code':code,'team_id':team_map.get(code),'team_name':str(r.name)}
            for name in [r.name,getattr(r,'fotmob_name','')]:
                if pd.notna(name) and str(name).strip():clubnames[norm(name)].add(code)
        source_clubs[season]=clubs;lookup={}
        inventories=[]
        for league,comp in COMPETITIONS.items():
            url=f'{BASE}/leagues?id={league}&season={quote(season,safe="")}'
            try:
                data=cache.get(url);matches=(data.get('fixtures') or {}).get('allMatches') or []
                for event in matches:
                    for side in ['home','away']:
                        team=event.get(side) or {};candidates=clubnames.get(norm(team.get('name')),set())
                        if len(candidates)==1:lookup[str(team['id'])]=clubs[next(iter(candidates))]
                inventories.extend((league,comp,e) for e in matches)
            except Exception as exc:errors.append({'season':season,'competition':comp,'stage':'inventory','url':url,'error':str(exc)})
        # Extend only from existing source match IDs; never create UUIDs/IDs.
        if season=='2026/2027':
            for gw in range(1,10):
                try:
                    matches=read_source(f'data/{folder}/By Gameweek/GW{gw}/matches.csv',out)
                    for r in matches.itertuples():
                        ko=pd.to_datetime(r.kickoff_time,utc=True,errors='coerce')
                        if pd.isna(ko) or ko>asof:continue
                        event=re.search(r'#(\d+)',str(r.match_url));event=event.group(1) if event else None
                        for code in [r.home_team,r.away_team]:
                            if pd.isna(code) or int(code) not in clubs:continue
                            registry[(season,canonical_competition(r.tournament),ko.date().isoformat(),int(code))].add(str(r.match_id))
                            if event:known[('fotmob',event)].add(str(r.match_id))
                except Exception as exc:errors.append({'season':season,'stage':'source_match_registry','gw':gw,'error':str(exc)})
        lookups[season]=lookup
        seen=set()
        for league,comp,e in inventories:
            key=str(e['id']);status=e.get('status') or {};ko=pd.to_datetime(status.get('utcTime'),utc=True,errors='coerce')
            if key in seen or pd.isna(ko) or ko>asof or not status.get('finished') or status.get('cancelled') or status.get('awarded'):continue
            if not any(str((e.get(side) or {}).get('id')) in lookup for side in ['home','away']):continue
            seen.add(key);events.append({'season':season,'competition':comp,'league_id':league,'event':e})
        print(f'{season}: {len(seen)} completed PL-club fixtures',flush=True)
    def collect(item):
        e=item['event'];url=f'{BASE}/matchDetails?matchId={e["id"]}'
        try:
            detail=cache.get(url)
            if not provider_competition_matches(detail,item['league_id']):
                g=detail.get('general') or {}
                raise ValueError(f'Inventory/detail competition mismatch: expected={item["league_id"]}, leagueId={g.get("leagueId")}, parentLeagueId={g.get("parentLeagueId")}, name={g.get("leagueName")}')
            return extract_fotmob(detail,e,item['season'],item['competition'],lookups[item['season']]),None
        except Exception as exc:return [],{'season':item['season'],'competition':item['competition'],'stage':'match','match_id':str(e['id']),'error':str(exc)}
    raw=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending={pool.submit(collect,item):item for item in events}
        for n,future in enumerate(as_completed(pending),1):
            rows,error=future.result();raw.extend(rows)
            if error:errors.append(error)
            if n%50==0:print(f'{n}/{len(events)} fixtures; {len(raw)} original ratings',flush=True)
    raw=pd.DataFrame(raw)
    if raw.empty:raise RuntimeError('No original ratings collected; refusing an empty benchmark')
    raw=raw.drop_duplicates(['provider','season','provider_match_id','provider_player_id']).sort_values(['provider','season','provider_match_id','provider_player_id']).reset_index(drop=True)
    mapped,audit=map_rows(raw,registry,known,{},opta,names,roles)
    if mapped.empty:raise RuntimeError('No mapped original ratings')
    validate_rating_ledger(mapped)
    duplicate=int(mapped.duplicated(['provider','player_uuid','match_id']).sum())
    if duplicate:raise ValueError(f'{duplicate} duplicate provider/player/match mappings; refuse ledger')
    # Verify target fixture identity aliases against all feature cutoffs.
    source=pd.read_csv(SOURCE,usecols=['fixture_uuid','player_uuid','cutoff']).drop_duplicates()
    aliases=classified[['match_id','fixture_uuid']].drop_duplicates()
    join=mapped.merge(aliases,on='match_id').merge(source,on=['fixture_uuid','player_uuid'])
    leakage=int((pd.to_datetime(join.available_at,utc=True)<=pd.to_datetime(join.cutoff,utc=True)).sum())
    postmatch=int((pd.to_datetime(mapped.available_at,utc=True)<=pd.to_datetime(mapped.kickoff,utc=True)+pd.Timedelta(hours=3)).sum())
    if leakage or postmatch:raise ValueError('Target-match or postmatch timing audit failed')
    def grouped(cols):
        return audit.groupby(cols+['mapping_status'],dropna=False).size().unstack(fill_value=0).reset_index().to_dict('records')
    identity={'total_rating_rows':len(raw),'mapped':len(mapped),'unresolved':int((audit.mapping_status=='unresolved').sum()),'ambiguous':int((audit.mapping_status=='ambiguous').sum()),'invalid_rating':int((audit.mapping_status=='invalid_rating').sum()),'mapping_rules':audit.groupby(['mapping_rule','mapping_status']).size().reset_index(name='rows').to_dict('records'),'no_fuzzy_matching':True,'source_pin':PIN}
    fixture_rows=[]
    for item in events:
        for side in ['home','away']:
            club=lookups[item['season']].get(str(item['event'][side]['id']))
            if club:fixture_rows.append({'season':item['season'],'competition':item['competition'],'team_name':club['team_name'],'provider_match_id':str(item['event']['id'])})
    fixture_scope=pd.DataFrame(fixture_rows).drop_duplicates()
    fixture_coverage=[]
    for season,comp in fixture_scope[['season','competition']].drop_duplicates().itertuples(index=False,name=None):
        scope=fixture_scope[(fixture_scope.season==season)&(fixture_scope.competition==comp)]
        r=raw[(raw.season==season)&(raw.competition==comp)]
        m=mapped[(mapped.season==season)&(mapped.competition==comp)]
        fixture_coverage.append({'season':season,'competition':comp,'completed_inventory_matches':int(scope.provider_match_id.nunique()),'matches_with_original_ratings':int(r.provider_match_id.nunique()),'matches_with_mapped_ratings':int(m.provider_match_id.nunique()),'inventory_team_games':len(scope),'rated_team_games':len(r[['provider_match_id','team_name']].drop_duplicates()),'mapped_team_games':len(m[['provider_match_id','team_name']].drop_duplicates())})
    team_fixture_coverage=[]
    for (season,team),scope in fixture_scope.groupby(['season','team_name']):
        r=raw[(raw.season==season)&(raw.team_name==team)];m=mapped[(mapped.season==season)&(mapped.team_name==team)]
        team_fixture_coverage.append({'season':season,'team_name':team,'completed_inventory_team_games':len(scope),'rated_team_games':int(r.provider_match_id.nunique()),'mapped_team_games':int(m.provider_match_id.nunique())})
    coverage={'as_of':asof.isoformat(),'providers':['fotmob'],'sofascore':'www.sofascore.com official API probe HTTP403; no fabricated provider rows','by_competition':grouped(['season','competition']),'fixture_coverage_by_competition':fixture_coverage,'fixture_coverage_by_team':team_fixture_coverage,'by_team':grouped(['season','team_name']),'duplicate_provider_player_match':duplicate,'ratings_outside_0_10':int((~mapped.rating.between(0,10)).sum()),'target_match_leakage':leakage,'postmatch_proxy_violations':postmatch,'target_rows_checked':len(join),'available_at_policy':'kickoff + 6 hours for provider-confirmed finished matches; conservative proxy, not original publication time; historical revisions cannot be certified','completed_inventory_matches':len(events),'matched_rating_events':int(raw.groupby(['season','provider_match_id']).ngroups),'errors':errors,'promotion_allowed':False}
    for filename,frame in [('player_match_ratings.csv.gz',mapped),('rating_identity_rows.csv.gz',audit),('raw_provider_ratings.csv.gz',raw)]:frame.to_csv(out/filename,index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame([{'season':i['season'],'competition':i['competition'],'provider_match_id':i['event']['id'],'kickoff':i['event']['status']['utcTime'],'home_name':i['event']['home']['name'],'away_name':i['event']['away']['name']} for i in events]).to_csv(out/'fixture_inventory.csv',index=False)
    # Freeze exact mapping inputs for offline rebuild (no network dependency).
    mappings={'registry':[{'key':list(k),'values':sorted(v)} for k,v in registry.items()],'known_matches':[{'key':list(k),'values':sorted(v)} for k,v in known.items()],'opta_ids':[{'key':k,'values':sorted(v)} for k,v in opta.items()],'names':[{'key':list(k),'values':sorted(v)} for k,v in names.items()],'roles':[{'key':list(k),'value':v} for k,v in roles.items()]}
    with gzip.open(out/'exact_mapping_inputs.json.gz','wt') as f:json.dump(mappings,f)
    for filename,data in [('identity_audit.json',identity),('coverage_audit.json',coverage),('http_source_manifest.json',cache.manifest())]:
        (out/filename).write_text(json.dumps(data,indent=2,default=str)+'\n')
    manifest=[{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.rglob('*')) if p.is_file()]
    (out/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(identity,indent=2),flush=True)

if __name__=='__main__':main()
