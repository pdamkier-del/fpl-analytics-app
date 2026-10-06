#!/usr/bin/env python3
"""Remove only unmapped previous-season fallback facts; leave model inputs intact.

Used to finalise a captured provider inventory. Refuses any wrong-season mapped
rating, since that would require a fresh experiment. New collection already
applies the same July-to-June guard before requesting match details.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from fpl_v1_1_model.external_rating_ingest import in_season

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dir',default='data_v1_1/derived/mm_v2_ratings');a=ap.parse_args();d=ROOT/a.dir
    ledger=d/'player_match_ratings.csv.gz';before=hashlib.sha256(ledger.read_bytes()).hexdigest()
    mapped=pd.read_csv(ledger)
    if not all(in_season(r.kickoff,r.season) for r in mapped.itertuples()):raise ValueError('Wrong-season mapped rating: fresh experiment required')
    raw=pd.read_csv(d/'raw_provider_ratings.csv.gz',dtype={'provider_player_id':str,'provider_match_id':str,'provider_opta_id':str})
    audit=pd.read_csv(d/'rating_identity_rows.csv.gz',dtype={'provider_player_id':str,'provider_match_id':str,'provider_opta_id':str})
    bad=~audit.apply(lambda r:in_season(r.kickoff,r.season),axis=1)
    if (audit.loc[bad,'mapping_status']=='mapped').any():raise ValueError('Wrong-season model input')
    rejected_rows=audit.loc[bad].copy()
    if bad.any():audit.loc[bad].to_csv(d/'rejected_previous_season_rows.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    audit=audit.loc[~bad].reset_index(drop=True);raw=raw[raw.apply(lambda r:in_season(r.kickoff,r.season),axis=1)].reset_index(drop=True)
    for name,frame in [('raw_provider_ratings.csv.gz',raw),('rating_identity_rows.csv.gz',audit)]:frame.to_csv(d/name,index=False,compression={'method':'gzip','mtime':0})
    inv=pd.read_csv(d/'fixture_inventory.csv',dtype={'provider_match_id':str})
    bad_inv=~inv.apply(lambda r:in_season(r.kickoff,r.season),axis=1)
    rejected=inv.loc[bad_inv].copy();inv=inv.loc[~bad_inv].reset_index(drop=True)
    inv.to_csv(d/'fixture_inventory.csv',index=False)
    identity=json.loads((d/'identity_audit.json').read_text());coverage=json.loads((d/'coverage_audit.json').read_text())
    identity.update(total_rating_rows=len(raw),mapped=len(mapped),unresolved=int((audit.mapping_status=='unresolved').sum()),ambiguous=int((audit.mapping_status=='ambiguous').sum()),invalid_rating=int((audit.mapping_status=='invalid_rating').sum()),mapping_rules=audit.groupby(['mapping_rule','mapping_status']).size().reset_index(name='rows').to_dict('records'))
    def grouped(cols):return audit.groupby(cols+['mapping_status'],dropna=False).size().unstack(fill_value=0).reset_index().to_dict('records')
    coverage.update(by_competition=grouped(['season','competition']),by_team=grouped(['season','team_name']),completed_inventory_matches=len(inv),matched_rating_events=int(raw.groupby(['season','provider_match_id']).ngroups),latest_rated_kickoff_by_season=raw.groupby('season').kickoff.max().to_dict(),rejected_out_of_season_inventory=rejected.to_dict('records'))
    # Fixture denominators are reduced only by excluded historical fallback rows.
    for r in coverage['fixture_coverage_by_competition']:
        q=inv[(inv.season==r['season'])&(inv.competition==r['competition'])]
        rr=raw[(raw.season==r['season'])&(raw.competition==r['competition'])];mm=mapped[(mapped.season==r['season'])&(mapped.competition==r['competition'])]
        r.update(completed_inventory_matches=len(q),matches_with_original_ratings=int(rr.provider_match_id.nunique()),matches_with_mapped_ratings=int(mm.provider_match_id.nunique()),inventory_team_games=r['inventory_team_games']-len(rejected_rows[(rejected_rows.season==r['season'])&(rejected_rows.competition==r['competition'])][['provider_match_id','team_name']].drop_duplicates()),rated_team_games=len(rr[['provider_match_id','team_name']].drop_duplicates()),mapped_team_games=len(mm[['provider_match_id','team_name']].drop_duplicates()))
    for r in coverage['fixture_coverage_by_team']:
        rr=raw[(raw.season==r['season'])&(raw.team_name==r['team_name'])];mm=mapped[(mapped.season==r['season'])&(mapped.team_name==r['team_name'])]
        r.update(completed_inventory_team_games=r['completed_inventory_team_games']-int(rejected_rows[(rejected_rows.season==r['season'])&(rejected_rows.team_name==r['team_name'])].provider_match_id.nunique()),rated_team_games=int(rr.provider_match_id.nunique()),mapped_team_games=int(mm.provider_match_id.nunique()))
    after=hashlib.sha256(ledger.read_bytes()).hexdigest()
    if before!=after:raise ValueError('Mapped ledger changed; refuse inherited benchmark')
    coverage['season_scope_audit']={'removed_unmapped_provider_rows':int(bad.sum()),'rejected_previous_season_fixtures':len(rejected),'model_input_sha256_before':before,'model_input_sha256_after':after,'model_inputs_identical':True,'fresh_benchmark_required':False,'policy':'July 1 <= kickoff < next July 1; excludes provider inventory fallback from future-season coverage'}
    for name,data in [('identity_audit.json',identity),('coverage_audit.json',coverage)]: (d/name).write_text(json.dumps(data,indent=2,default=str)+'\n')
    manifest=[{'path':str(p.relative_to(d)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(d.rglob('*')) if p.is_file() and p.name!='data_manifest.json']
    (d/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(coverage['season_scope_audit'],indent=2))
if __name__=='__main__':main()
