from fpl_xpts.simple_chip_thresholds import choose_simple_chip

def test_late_expiry_no_caution():
    assert choose_simple_chip(19,1,1.0,-10.0,100,100).choice=="fh"
    assert choose_simple_chip(38,2,-10.0,1.0,100,100).choice=="wc"

def test_early_preserves_chips():
    assert choose_simple_chip(1,3,10,20,10,20).choice=="normal"

def test_only_held_chip_can_be_selected():
    assert choose_simple_chip(6,1,50,100,10,10).choice=="fh"
    assert choose_simple_chip(6,2,50,100,10,10).choice=="wc"

def test_prefer_higher_adjusted_surplus():
    assert choose_simple_chip(6,3,15,16,10,20).choice=="fh"

def test_two_half_reset():
    x=choose_simple_chip(20,3,5,0,10,20)
    assert x.choice=="normal"

def test_invalid_gameweek():
    import pytest
    with pytest.raises(ValueError):
        choose_simple_chip(39,3,1,1,10,20)
