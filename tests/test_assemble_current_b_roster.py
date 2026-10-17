import pandas as pd
import pytest
from assemble_current_b_roster import assemble
from research_individual_mm_refinement import NUM

def test_current_B_bridge_rejects_missing_producer():
    skeleton={'scope':'official_identity_fixture_skeleton_not_B_features',
              'rows':[dict(season='2026-27',fixture_uuid='f',fpl_element=1,
                           team_id=1,pos='MID',gw=7,cutoff='2026-10-17T09:00:00Z')]}
    ids=pd.DataFrame([dict(fpl_element=1,player_uuid='p1')])
    features=pd.DataFrame([dict(season='2026-27',fixture_uuid='f',player_uuid='p1')])
    with pytest.raises(ValueError,match='Authentic B input'):
        assemble(skeleton,ids,features,dict(upstream_variant='legacy'))

def test_current_B_bridge_rejects_wrong_uuid():
    skeleton={'scope':'official_identity_fixture_skeleton_not_B_features',
              'rows':[dict(season='2026-27',fixture_uuid='f',fpl_element=1,
                           team_id=1,pos='MID',gw=7,cutoff='2026-10-17T09:00:00Z')]}
    ids=pd.DataFrame([dict(fpl_element=1,player_uuid='p1')])
    features=pd.DataFrame([dict(season='2026-27',fixture_uuid='f',player_uuid='p2')])
    with pytest.raises(ValueError,match='roster mismatch'):
        assemble(skeleton,ids,features,dict(upstream_variant='role_chance_return_duration',
            features=NUM,source_manifest_sha256='documented'))
