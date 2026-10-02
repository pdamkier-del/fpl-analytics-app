#!/usr/bin/env python3
"""Match frozen CL inventories by explicit aliases, club pair and per-club score.

Never use an H2H URL, club order or GW alone as fixture identity. Reconstructed
kickoffs are retrospective metadata, not contemporaneous schedule snapshots.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo
import pandas as pd
from build_reproducible_role_benchmark import ROOT,write_json,sha


def normalize(name):
    name=re.sub(r'\([A-Z]{3}\)','',name).strip()
    name=unicodedata.normalize('NFKD',name.replace('ø','o').replace('Ø','O'))
    name=''.join(c for c in name if not unicodedata.combining(c))
    words=re.findall(r'[a-z0-9]+',name.lower())
    words=[w for w in words if w not in ('fc','cf','fk','sk','kv')]
    key=''.join(words)
    aliases={'clubatleticodemadrid':'atleticomadrid','bayer04leverkusen':'bayerleverkusen',
      'sportingclubedeportugal':'sportingcp','sportlisboaebenfica':'benfica',
      'internazionalemilano':'inter','paphos':'pafos','pafos':'pafos',
      'qarabagagdam':'qarabag',
      'kairat':'kairatalmaty','asmonaco':'monaco','sscnapoli':'napoli',
      'paeolympiakossfp':'olympiacos','slaviapraha':'slaviaprague',
      'psv':'psveindhoven','olympiquedemarseille':'marseille',
      'royaleunionsaintgilloise':'unionstgilloise','unionsaintgilloise':'unionstgilloise',
      'afcajax':'ajax','ajax':'ajax','atalantabc':'atalanta'}
    return aliases.get(key,key)


def parse_inventory(text):
    rows=[];date=None;year=2025;clock=None;stage=None
    for line_no,line in enumerate(text.splitlines(),1):
        stripped=line.strip()
        if stripped.startswith('▪'):stage=stripped.lstrip('▪ ').strip();continue
        m=re.fullmatch(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) (\d{1,2})(?: (\d{4}))?',stripped)
        if m:
            if m[4]:year=int(m[4])
            date=datetime.strptime(f'{m[2]} {m[3]} {year}','%b %d %Y').date();clock=None;continue
        if ' v ' not in line:continue
        if date is None:raise ValueError('Fixture without date')
        m=re.match(r'\s*(?:(\d{2}:\d{2})\s+)?(.+?)\s+v\s+(.+?)\s{2,}(.+?)\s*$',line)
        if not m:raise ValueError('Unparsed fixture at line '+str(line_no))
        if m[1]:clock=m[1]
        if clock is None:raise ValueError('Fixture without clock')
        result=re.sub(r'^\d+-\d+ pen\.\s*','',m[4])
        score=re.match(r'(\d+)-(\d+)',result)
        if not score:raise ValueError('Unparsed result')
        local=datetime.combine(date,datetime.strptime(clock,'%H:%M').time()).replace(tzinfo=ZoneInfo('Europe/Berlin'))
        rows.append({'inventory_line':line_no,'home':normalize(m[2]),'away':normalize(m[3]),
          'home_name':m[2].strip(),'away_name':m[3].strip(),'home_score':int(score[1]),'away_score':int(score[2]),
          'stage':stage,'clock_as_written':clock,'kickoff_candidate':local.astimezone(timezone.utc).isoformat()})
    return pd.DataFrame(rows)


def main():
    raw=ROOT/'data_v1_1/raw/independent-cup-inventory/cl-2025-26.txt'
    inventory=parse_inventory(raw.read_text());assert len(inventory)==189
    source=pd.concat([pd.read_csv(p) for p in sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*/matches.csv'))],ignore_index=True)
    source=source[source.tournament=='champions-league']
    records=[];used=set();quarantine=[]
    pair_counts=inventory.apply(lambda r:tuple(sorted((r.home,r.away))),axis=1).value_counts().to_dict()
    for r in source.itertuples():
        left,right=r.match_id.removeprefix('25-26-champions-league-').split('-vs-')
        a,b=normalize(left),normalize(right);hits=[]
        for s in inventory.itertuples():
            direct=(s.home==a and s.away==b and s.home_score==r.home_score and s.away_score==r.away_score)
            reverse=(s.home==b and s.away==a and s.home_score==r.away_score and s.away_score==r.home_score)
            if direct or reverse:hits.append((s,reverse))
        row={'match_id':r.match_id,'source_home':a,'source_away':b,'source_home_score':r.home_score,'source_away_score':r.away_score,
          'source_kickoff':r.kickoff_time,'candidate_count':len(hits),'source_url':r.match_url}
        pair_count=pair_counts.get(tuple(sorted((a,b))),0)
        row['independent_matches_for_club_pair']=pair_count
        # Even an apparently valid score/time cannot certify player stats once
        # source IDs omit dates and the club pair occurs in multiple fixtures.
        if pair_count>1:
            quarantine.append({'match_id':r.match_id,'reason':'repeated CL club pair with date-free source key; fixture/player-stat version cannot be certified','independent_pair_fixture_count':pair_count})
        if len(hits)==1:
            s,reverse=hits[0];used.add(s.inventory_line)
            supplied=pd.to_datetime(r.kickoff_time,utc=True,errors='coerce')
            candidate=pd.to_datetime(s.kickoff_candidate,utc=True)
            row.update({'inventory_line':s.inventory_line,'independent_home':s.home,'independent_away':s.away,
              'stage':s.stage,'reversed_source_home_away':reverse,'kickoff_candidate':s.kickoff_candidate,
              'existing_kickoff_matches_candidate':None if pd.isna(supplied) else bool(supplied==candidate)})
        records.append(row)
    audit=pd.DataFrame(records);anchored=audit[audit.source_kickoff.notna() & (audit.candidate_count==1)]
    mismatches=anchored[anchored.existing_kickoff_matches_candidate==False]
    missing=audit[audit.source_kickoff.isna() & (audit.candidate_count==1)]
    out=ROOT/'analysis/results/independent-cl-audit';out.mkdir(parents=True,exist_ok=True)
    inventory.to_csv(out/'independent_inventory.csv',index=False);audit.to_csv(out/'source_fixture_matches.csv',index=False)
    pd.DataFrame(quarantine).to_csv(out/'workload_quarantine.csv',index=False)
    pl={'arsenal','chelsea','liverpool','manchestercity','newcastleunited','tottenhamhotspur'}
    independent_pl=inventory[inventory.home.isin(pl)|inventory.away.isin(pl)]
    gaps=independent_pl[~independent_pl.inventory_line.isin(used)]
    gaps.to_csv(out/'missing_from_original_source.csv',index=False)
    # Timezone was not declared by the TXT source. Treat the Berlin interpretation
    # as a hypothesis and require all available source timestamp anchors to agree.
    gate=len(anchored)>=40 and len(mismatches)==0
    overrides=missing[['match_id','kickoff_candidate','inventory_line','stage']].rename(columns={'kickoff_candidate':'kickoff_time'}) if gate else pd.DataFrame(columns=['match_id','kickoff_time','inventory_line','stage'])
    overrides.to_csv(out/'accepted_kickoff_overrides.csv',index=False)
    summary={'inventory_matches':len(inventory),'independent_pl_cl_matches':len(independent_pl),'original_source_cl_matches':len(source),
      'unique_pair_score_matches':int((audit.candidate_count==1).sum()),'unmatched_or_ambiguous':int((audit.candidate_count!=1).sum()),
      'timestamp_anchors':len(anchored),'timestamp_anchor_mismatches':len(mismatches),'recovery_gate_passed':gate,
      'missing_kickoffs_recoverable':len(missing),'accepted_overrides':len(overrides),'missing_cl_fixtures_in_original_source':len(gaps),
      'quarantined_source_fixture_keys':len(quarantine),
      'clock_rule':'Europe/Berlin interpreted from calendar clock; DST applied; empirical timestamp anchors required',
      'availability':'Retrospective reconstruction only; does not establish schedule publication or player-minute correctness',
      'matching':'Explicit aliases + unordered club pair + per-club final score; require exactly one match; no GW/URL-only matching'}
    write_json(out/'summary.json',summary)
    write_json(out/'manifest.json',{'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [raw,*sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*/matches.csv'))]],
      'code':[{'path':str(Path(__file__).relative_to(ROOT)),'sha256':sha(__file__)}],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json']})
    print(summary)


if __name__=='__main__':main()
