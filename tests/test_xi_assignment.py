import pytest

from fpl_v1_1_model.xi_assignment import formation_slots,optimize_xi,optimize_best_formation


def player(pid,roles,base=.5,perf=.5):
    return {
        'player_uuid':pid,
        'base_p_start':base,
        'performance':perf,
        'q':{r:q for r,(q,h) in roles.items()},
        'H':{r:h for r,(q,h) in roles.items()},
    }


def test_formation_has_eleven_slots():
    slots=formation_slots('4-2-3-1')
    assert len(slots)==11
    assert slots[0].role=='GK'
    assert sum(s.role=='ST' for s in slots)==1


def test_multirole_player_can_only_fill_one_slot():
    players=[
        player('gk',{'GK':(1,.9)},.95),
        player('rbcb',{'RB':(.9,.9),'RCB':(.9,.85)},.9),
        player('rb2',{'RB':(.8,.75)},.75),
        player('rcb2',{'RCB':(.8,.7)},.7),
        player('lcb',{'LCB':(1,.9)},.9),
        player('lb',{'LB':(1,.9)},.9),
        player('rdm',{'RDM':(1,.9)},.9),
        player('ldm',{'LDM':(1,.9)},.9),
        player('ram',{'RAM':(1,.9)},.9),
        player('cam',{'CAM':(1,.9)},.9),
        player('lam',{'LAM':(1,.9)},.9),
        player('st',{'ST':(1,.9)},.9),
    ]
    xi=optimize_xi(players,'4-2-3-1')
    ids=[x.player_uuid for x in xi]
    assert len(ids)==11
    assert len(set(ids))==11
    assert ids.count('rbcb')==1


def test_assignment_uses_global_optimum_not_greedy():
    # p1 is slightly better at RB but massively better at RCB.  A greedy RB
    # choice would waste p1; global assignment must put p2 at RB and p1 at RCB.
    players=[
        player('gk',{'GK':(1,.9)},.99),
        player('p1',{'RB':(.95,.95),'RCB':(.99,.99)},.95),
        player('p2',{'RB':(.90,.90),'RCB':(.05,.05)},.9),
        player('lcb',{'LCB':(1,.9)},.9),
        player('lb',{'LB':(1,.9)},.9),
        player('rdm',{'RDM':(1,.9)},.9),
        player('ldm',{'LDM':(1,.9)},.9),
        player('ram',{'RAM':(1,.9)},.9),
        player('cam',{'CAM':(1,.9)},.9),
        player('lam',{'LAM':(1,.9)},.9),
        player('st',{'ST':(1,.9)},.9),
    ]
    xi=optimize_xi(players,'4-2-3-1')
    byrole={x.role:x.player_uuid for x in xi}
    assert byrole['RB']=='p2'
    assert byrole['RCB']=='p1'


def test_performance_can_break_close_role_hierarchy_tie():
    base=[
        player('gk',{'GK':(1,.9)},.99),
        player('rbA',{'RB':(1,.8)},.8,.3),
        player('rbB',{'RB':(1,.79)},.8,.9),
        player('rcb',{'RCB':(1,.9)},.9),
        player('lcb',{'LCB':(1,.9)},.9),
        player('lb',{'LB':(1,.9)},.9),
        player('rdm',{'RDM':(1,.9)},.9),
        player('ldm',{'LDM':(1,.9)},.9),
        player('ram',{'RAM':(1,.9)},.9),
        player('cam',{'CAM':(1,.9)},.9),
        player('lam',{'LAM':(1,.9)},.9),
        player('st',{'ST':(1,.9)},.9),
    ]
    xi=optimize_xi(base,'4-2-3-1',performance_weight=1.0)
    assert {x.role:x.player_uuid for x in xi}['RB']=='rbB'


def test_best_formation_returns_legal_unique_xi():
    players=[
        player('gk',{'GK':(1,.9)},.99),
        player('rb',{'RB':(1,.9),'RWB':(.6,.6)},.9),
        player('rcb',{'RCB':(1,.9)},.9),
        player('lcb',{'LCB':(1,.9)},.9),
        player('lb',{'LB':(1,.9),'LWB':(.6,.6)},.9),
        player('rdm',{'RDM':(1,.9),'RCM':(.4,.4)},.9),
        player('ldm',{'LDM':(1,.9),'LCM':(.4,.4)},.9),
        player('ram',{'RAM':(1,.9),'RW':(.5,.5)},.9),
        player('cam',{'CAM':(1,.9),'CM':(.3,.3)},.9),
        player('lam',{'LAM':(1,.9),'LW':(.5,.5)},.9),
        player('st',{'ST':(1,.9)},.9),
        player('extra',{'CM':(1,.6),'ST':(.2,.2)},.5),
    ]
    out=optimize_best_formation(players,formations=['4-2-3-1','4-3-3'])
    assert out['formation'] in {'4-2-3-1','4-3-3'}
    assert len(out['xi'])==11
    assert len({x.player_uuid for x in out['xi']})==11
