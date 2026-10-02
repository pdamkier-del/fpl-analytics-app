"""Regression checks for the isolated AM -> explicit CAM correction."""
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

import pandas as pd
from fpl_v1_1_model.pstart_v2 import (
    MinutesFeatures, PlayerRoleInput, constrained_start_probabilities,
)

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


roles = load_script('v1_1_ingest_fpl_core_detailed_roles')
hierarchy = load_script('v1_1_build_role_hierarchy')


def lineup(formation):
    layers = roles.parse_formation(formation)
    rows = [{'player_id': 'gk', 'position': 'G', 'x': 0, 'y': 50}]
    for depth, size in enumerate(layers):
        for side in range(size):
            rows.append({'player_id': f'{depth}_{side}',
                         'position': 'D' if depth == 0 else ('F' if depth == len(layers)-1 else 'M'),
                         'x': 20 + depth * 20, 'y': (side + 1) * 100 / (size + 1)})
    return pd.DataFrame(rows)


def test_central_tens_are_cam_and_sides_are_preserved():
    for formation in ('4-2-3-1', '4-4-1-1', '3-4-1-2', '4-3-1-2'):
        assigned = roles.assign_starter_roles(lineup(formation), formation)
        assert len(assigned) == 10
        assert list(assigned.values()).count('CAM') == 1
        assert 'AM' not in assigned.values()
    assigned = roles.assign_starter_roles(lineup('4-2-3-1'), '4-2-3-1')
    assert assigned['0_0'] == 'RB' and assigned['0_3'] == 'LB'
    assert assigned['2_0'] == 'RAM' and assigned['2_2'] == 'LAM'


def test_half_spaces_and_deep_single_pivot_are_not_forced_to_cam():
    assigned = roles.assign_starter_roles(lineup('3-4-2-1'), '3-4-2-1')
    assert assigned['2_0'] == 'RAM' and assigned['2_1'] == 'LAM'
    assert 'CAM' not in assigned.values()
    assigned = roles.assign_starter_roles(lineup('4-1-4-1'), '4-1-4-1')
    assert assigned['1_0'] == 'DM'


def test_taxonomy_preserves_cam_and_legacy_central_aliases():
    minimum = {'GK','RB','RWB','RCB','CB','LCB','LB','LWB','RDM','DM','LDM',
               'RCM','CM','LCM','CAM','RW','LW','ST'}
    assert minimum <= set(hierarchy.ROLES)
    for alias in ('CAM', 'AM', 'AMC'):
        assert hierarchy.normalize_role(alias) == 'CAM'
    for role in ('CM', 'ST', 'RW', 'LW', 'RAM', 'LAM'):
        assert hierarchy.normalize_role(role) == role


def test_starting_goalkeeper_is_preserved_alongside_ten_outfield_roles():
    starters = lineup('4-2-3-1')
    outfield = roles.assign_starter_roles(starters, '4-2-3-1')
    full = roles.add_goalkeeper_roles(starters, outfield)
    assert len(full) == 11 and full['gk'] == 'GK'
    assert {k:v for k,v in full.items() if k != 'gk'} == outfield


def test_rename_alone_preserves_constrained_probabilities():
    mf = MinutesFeatures(.8, .7, .8, .1)
    original = [PlayerRoleInput(pid, role, q, h, mf)
                for pid, q, h in [('a',.7,.9), ('b',.5,.6), ('c',.3,.4)]
                for role in ('AM','RW')]
    corrected = [PlayerRoleInput(x.player_id, 'CAM' if x.role == 'AM' else x.role,
                                x.role_share, x.hierarchy, x.minutes, x.is_goalkeeper)
                 for x in original]
    old, _ = constrained_start_probabilities(original, importance=.8, role_capacity={'AM':1,'RW':1})
    new, _ = constrained_start_probabilities(corrected, importance=.8, role_capacity={'CAM':1,'RW':1})
    for pid in old:
        assert abs(old[pid] - new[pid]) < 1e-10


def test_cam_q_h_and_capacity_survive_hierarchy_pipeline():
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / 'roles.sqlite3'
        out = Path(temp) / 'features'
        subprocess.run([sys.executable, str(ROOT/'scripts/v1_1_init_multicomp_pstart_v2.py'),
                        '--db',str(db)], check=True, capture_output=True)
        con = sqlite3.connect(db)
        for number, role in [(1,'AM'), (2,'RW'), (3,'CAM')]:
            mid = f'm{number}'
            ko = f'2025-08-{number*7:02d}T12:00:00+00:00'
            con.execute('INSERT INTO club_matches_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (mid,'2025-26',ko,'PL',None,None,'Home','Away','2025-26:1',
                         '2025-26:2','test',None,ko))
            con.execute('INSERT INTO player_match_roles_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (mid,'p','Player','2025-26:1',1,90,1,role,70,50,'test',ko))
        con.commit(); con.close()
        subprocess.run([sys.executable,str(ROOT/'scripts/v1_1_build_role_hierarchy.py'),
                        '--db',str(db),'--out-dir',str(out)],check=True,capture_output=True)
        state = pd.read_csv(out/'player_role_state.csv')
        latest = state[state.source_match_id == 'm3']
        cam = latest[latest.role == 'CAM'].iloc[0]
        rw = latest[latest.role == 'RW'].iloc[0]
        assert 0 < cam.q_role < 1 and 0 < rw.q_role < 1
        assert cam.hierarchy_role > 0 and rw.hierarchy_role > 0
        assert abs(latest.q_role.sum()-1) < 1e-9
        assert 'AM' not in state.role.values
        # The first snapshot contains only the first match's observed evidence.
        first = state[(state.source_match_id == 'm1') & (state.role == 'CAM')].iloc[0]
        assert first.role_evidence == 1
