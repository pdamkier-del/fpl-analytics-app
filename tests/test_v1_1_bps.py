from fpl_v1_1_model.bps import BPSComponents,bps_2026_27,allocate_bonus_points


def test_2026_27_penalty_save_combined_bps():
    # 7 penalty-save base + 2 any save + 1 inside-box + 1 big-chance = 11,
    # plus 3 for playing 1-60 in this isolated example.
    c=BPSComponents(minutes=1,position='GK',penalty_saves=1,saves_total=1,saves_inside_box=1,big_chance_saves=1)
    assert bps_2026_27(c)==14


def test_2026_27_cbi_every_three_and_no_being_tackled_field():
    c=BPSComponents(minutes=0,position='DEF',clearances_blocks_interceptions=8)
    assert bps_2026_27(c)==2


def test_bonus_tie_first():
    x=allocate_bonus_points({'a':35,'b':35,'c':34,'d':33})
    assert x=={'a':3,'b':3,'c':1,'d':0}


def test_bonus_tie_second():
    x=allocate_bonus_points({'a':36,'b':35,'c':35,'d':34})
    assert x=={'a':3,'b':2,'c':2,'d':0}


def test_bonus_tie_third_and_many_players():
    x=allocate_bonus_points({'a':36,'b':35,'c':34,'d':34,'e':34})
    assert x=={'a':3,'b':2,'c':1,'d':1,'e':1}
