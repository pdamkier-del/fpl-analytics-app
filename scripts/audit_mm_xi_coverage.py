#!/usr/bin/env python3
"""Archived 2025/26 cross-competition XI turnover. Exploratory MM-only evidence.

Lineup changes are observations, not proof that fixture importance caused rotation.
Unknown dates or team identity are excluded; no post-cutoff data used for predictions.
"""
import csv, json, re, collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data_v1_1/raw/all-competitions-2025-26'
OUT=ROOT/'analysis/results/mm-match-importance-20261016'
def competition(match):
    s=match.lower()
    for label,terms in [('Champions League',['champions-league']),('Europa League',['europa-league']),('Conference League',['conference-league']),('FA Cup',['fa-cup']),('League Cup',['efl-cup','carabao-cup','league-cup'])]:
        if any(t in s for t in terms):return label
    if any(t in s for t in ['premier-league','premier_league']):return 'Premier League'
    return 'other / unknown'
def main():
    games=collections.defaultdict(lambda: {'players':set(),'sources':set(),'starting_rows':0})
    missing=0
    for path in sorted(BASE.glob('GW*/lineups.csv')):
        with path.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                if str(row.get('is_starting','')).lower() not in ('true','1'):continue
                team=row.get('team_code','').strip();match=row.get('match_id','').strip()
                player=(row.get('player_id') or '').strip()
                if not player:player='name:'+re.sub(r'\s+',' ',(row.get('player_name') or '').casefold().strip())
                if not team or not match or player=='name:':
                    missing+=1;continue
                key=(team,match);games[key]['players'].add(player);games[key]['sources'].add(str(path.relative_to(ROOT)));games[key]['starting_rows']+=1
    bycomp=collections.defaultdict(lambda: {'matches':0,'valid_xi':0,'invalid_xi':0,'distinct_teams':set(),'matched_player_count':0})
    rows=[]
    for (team,match),v in sorted(games.items()):
        comp=competition(match);n=len(v['players']);stat=bycomp[comp];stat['matches']+=1;stat['distinct_teams'].add(team);stat['matched_player_count']+=n
        stat['valid_xi' if n==11 else 'invalid_xi']+=1
        rows.append(dict(team_code=team,match_id=match,competition=comp,unique_starters=n,raw_starting_rows=v['starting_rows'],source_files=';'.join(sorted(v['sources'])),complete_xi=n==11,players=sorted(v['players'])))
    result={'source':'Archived pre-existing lineup files, NOT the entire league competition schedule',
            'raw_starting_rows_without_identity':missing,
            'match_team_records':len(rows),
            'competition_coverage':{k:{**{z:v[z] for z in ('matches','valid_xi','invalid_xi','matched_player_count')},'teams':len(v['distinct_teams'])} for k,v in sorted(bycomp.items())},
            'limitations':['match_id contains no verified chronological kickoff timestamp','same-name player identities may collide without provider ID','lineup-only snapshots contain no substitution timestamps/minutes','cannot infer consecutive-match turnover without trusted match date and calendar','no causal importance test, no new MM forecast or MAE'],
            'complete_xi_records':sum(v['complete_xi'] for v in rows)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'lineup_coverage.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    with (OUT/'lineup_match_teams.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['team_code','match_id','competition','unique_starters','raw_starting_rows','complete_xi','source_files']);w.writeheader();w.writerows({k:v for k,v in r.items() if k!='players'} for r in rows)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
