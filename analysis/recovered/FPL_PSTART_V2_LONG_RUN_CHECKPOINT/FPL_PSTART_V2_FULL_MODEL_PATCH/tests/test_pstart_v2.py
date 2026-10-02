from fpl_v1_1_model.pstart_v2 import *

def test_dynamic_comp_value_rises_when_competitions_disappear():
    b={'PL':1.0,'CL':1.2,'FA':0.6,'LC':0.4}
    a=dynamic_competition_value('LC',['PL','CL','FA','LC'],b)
    c=dynamic_competition_value('LC',['PL','LC'],b)
    assert c>a

def test_importance_increases_with_round_and_opponent():
    b={'PL':1.0,'LC':0.4}
    lo=match_importance(competition='LC',active_competitions=['PL','LC'],round_strength=.1,opponent_strength=.1,base_values=b)
    hi=match_importance(competition='LC',active_competitions=['PL','LC'],round_strength=.9,opponent_strength=.9,base_values=b)
    assert hi>lo

def test_hierarchy_absence_does_not_count_as_bench_loss():
    h=HierarchyState(9,1); before=h.value
    h.update(started=False,minutes=0,importance=.9,in_matchday_squad=False,half_life=10)
    # only gentle neutral decay of evidence strength; ratio unchanged
    assert abs(h.value-before)<1e-12

def test_exact_team_mass_with_unique_roles():
    mf=MinutesFeatures(.8,.75,.8,.1)
    inp=[]
    # 2 roles, two slots each; enough players
    for n in range(6):
        for role,q in [('A',.6),('B',.4)]:
            inp.append(PlayerRoleInput(str(n),role,q,.6+0.02*n,mf))
    p,a=constrained_start_probabilities(inp,importance=.8,role_capacity={'A':2,'B':2})
    assert abs(sum(p.values())-4)<1e-6
    assert max(p.values())<=1+1e-8
