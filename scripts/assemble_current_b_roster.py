"""Strict bridge from official fixture roster to verified B upstream features.

This adapter does not generate missing player roles or injury information.
"""
import pandas as pd
from mm_candidate import validate_frame
from research_individual_mm_refinement import NUM

KEY = ['season', 'fixture_uuid', 'player_uuid']

def assemble(skeleton, identity, features, provenance):
    if skeleton.get('scope') != 'official_identity_fixture_skeleton_not_B_features':
        raise ValueError('Official skeleton required')
    if provenance.get('upstream_variant') != 'role_chance_return_duration':
        raise ValueError('Authentic B input required')
    if provenance.get('features') != NUM or not provenance.get('source_manifest_sha256'):
        raise ValueError('Invalid feature provenance')
    roster = pd.DataFrame(skeleton['rows'])
    if roster.empty or roster.duplicated(['fixture_uuid','fpl_element']).any():
        raise ValueError('Invalid roster')
    identity = identity[['fpl_element','player_uuid']]
    if identity.isna().any().any() or identity.fpl_element.duplicated().any() or identity.player_uuid.duplicated().any():
        raise ValueError('Non-bijective player IDs')
    official = roster.merge(identity, on='fpl_element', how='left', validate='many_to_one')
    if official.player_uuid.isna().any():
        raise ValueError('Missing player UUID')
    if features.duplicated(KEY).any():
        raise ValueError('Duplicate feature rows')
    if set(map(tuple, official[KEY].to_numpy())) != set(map(tuple, features[KEY].to_numpy())):
        raise ValueError('Feature/official roster mismatch')
    result = official.merge(features, on=KEY, validate='one_to_one', suffixes=('_official',''))
    for field in ['team_id','gw','pos','cutoff']:
        a, b = result[field+'_official'], result[field]
        if field == 'cutoff':
            ok = pd.to_datetime(a, utc=True).eq(pd.to_datetime(b, utc=True))
        else:
            ok = a.eq(b)
        if not ok.all():
            raise ValueError('Conflict in '+field)
    return validate_frame(result)
