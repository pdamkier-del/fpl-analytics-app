#!/usr/bin/env python3
"""Extend CL quarantine with organizer EL/Conference fixture identity evidence.

The frozen organizer facts are retrospective audit inputs, not as-of schedule
features. Date-free repeated club pairs cannot certify their player payloads.
No kickoff or historical player statistic is recovered by this audit.
"""
import json
from pathlib import Path
import pandas as pd
from audit_independent_cl_fixtures import normalize as cl_normalize
from build_reproducible_role_benchmark import ROOT,write_json,sha


def normalize(name):
    value=cl_normalize(str(name))
    return {'fcmidtjylland':'midtjylland','fcporto':'porto','fcutrecht':'utrecht',
      'malmoff':'malmo','zrinjskimostar':'zrinjski','kups':'kupskuopio',
      'shakhtar':'shakhtardonetsk'}.get(value,value)


def compare(source, inventory):
    """Stable, unordered club-pair/per-club-score match; no guessed aliases."""
    inventory=inventory.copy()
    for side in ('home','away'):inventory[side]=inventory[side].map(normalize)
    records=[];quarantine=[];matched=set()
    for r in source.sort_values('match_id').itertuples():
        a,b=r.match_id.removeprefix('25-26-'+r.tournament+'-').split('-vs-')
        a,b=normalize(a),normalize(b)
        pairs=inventory[(inventory.competition==r.tournament)&
          (((inventory.home==a)&(inventory.away==b))|((inventory.home==b)&(inventory.away==a)))]
        hits=pairs[((pairs.home==a)&(pairs.home_score==r.home_score)&(pairs.away_score==r.away_score))|
          ((pairs.home==b)&(pairs.home_score==r.away_score)&(pairs.away_score==r.home_score))]
        known=pd.to_datetime(r.kickoff_time,utc=True,errors='coerce')
        row={'match_id':r.match_id,'competition':r.tournament,'gameweek':r.gameweek,
          'source_home':a,'source_away':b,'source_home_score':r.home_score,'source_away_score':r.away_score,
          'source_kickoff':r.kickoff_time,'finished':str(r.finished).lower()=='true',
          'independent_pair_fixture_count':len(pairs),'candidate_count':len(hits),
          'existing_kickoff_date_matches_candidate':None}
        if len(hits)==1:
            hit=hits.iloc[0];matched.add(int(hit.name))
            row.update({'independent_date':hit.date,'independent_home':hit.home,'independent_away':hit.away,
              'stage':hit.stage,'source_url':hit.source_url,'source_line':int(hit.source_line),
              'existing_kickoff_date_matches_candidate':None if pd.isna(known) else str(known.date())==hit.date})
        if row['finished']:
            reason=None
            if len(pairs)>1:
                reason='repeated Europe club pair with date-free source key; player-stat version uncertified'
            elif len(hits)!=1:
                reason='source club pair and score do not uniquely match organizer inventory'
            elif row['existing_kickoff_date_matches_candidate'] is False:
                reason='supplied kickoff date disagrees with organizer fixture score'
            if reason:quarantine.append({'match_id':r.match_id,'reason':reason,'independent_pair_fixture_count':len(pairs)})
        records.append(row)
    return pd.DataFrame(records),pd.DataFrame(quarantine),matched


def main():
    raw=ROOT/'data_v1_1/raw/independent-cup-inventory'
    path=raw/'uefa-el-conference-2025-26.csv'
    inventory=pd.read_csv(path)
    source_manifest=json.loads((raw/'UEFA_SOURCE_MANIFEST.json').read_text())
    assert sha(path)==source_manifest['sha256']
    assert inventory.groupby('competition').size().to_dict()=={'conference-league':153,'europa-league':189}
    assert not inventory.duplicated(['competition','date','home','away']).any()
    paths=sorted((ROOT/'data_v1_1/raw/all-competitions-2025-26').glob('GW*/matches.csv'))
    source=pd.concat([pd.read_csv(p) for p in paths],ignore_index=True)
    source=source[source.tournament.isin(['europa-league','conference-league'])]
    assert not source.match_id.duplicated().any()
    audit,quarantine,matched=compare(source,inventory)
    cl=ROOT/'analysis/results/independent-cl-audit/workload_quarantine.csv'
    combined=pd.concat([pd.read_csv(cl),quarantine],ignore_index=True).sort_values('match_id')
    assert not combined.match_id.duplicated().any()
    pl={'Aston Villa','Nottingham Forest','Crystal Palace'}
    pl_inventory=inventory[inventory.home.isin(pl)|inventory.away.isin(pl)]
    unmatched=pl_inventory[~pl_inventory.index.isin(matched)]
    out=ROOT/'analysis/results/independent-europe-audit';out.mkdir(parents=True,exist_ok=True)
    audit.to_csv(out/'source_fixture_matches.csv',index=False)
    combined.to_csv(out/'workload_quarantine.csv',index=False)
    unmatched.to_csv(out/'unmatched_reference_fixtures.csv',index=False)
    conflicts=audit[audit.existing_kickoff_date_matches_candidate==False]
    summary={'organizer_fixtures':len(inventory),'organizer_pl_fixtures_by_competition':pl_inventory.groupby('competition').size().astype(int).to_dict(),
      'source_keys_by_competition':source.groupby('tournament').size().astype(int).to_dict(),
      'additional_quarantined_source_keys':len(quarantine),'combined_quarantined_source_keys':len(combined),
      'date_score_conflicts':len(conflicts),'conflicting_source_keys':conflicts.match_id.tolist(),
      'uniquely_matched_source_keys':int((audit.candidate_count==1).sum()),
      'unmatched_reference_fixtures':len(unmatched),'kickoff_overrides':0,
      'qualifying_coverage':'Organizer inventory excludes qualifying; Palace qualifiers remain an explicit gap',
      'source_quality_certified':False,
      'availability':'Retrospective identity audit; does not establish player-stat publication or actual kickoff clock'}
    write_json(out/'summary.json',summary)
    inputs=[path,raw/'UEFA_SOURCE_MANIFEST.json',cl,*paths]
    write_json(out/'manifest.json',{'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
      'code':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [Path(__file__),ROOT/'scripts/audit_independent_cl_fixtures.py']],
      'outputs':[{'path':p.name,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.name!='manifest.json']})
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
