import pandas as pd
from fpl_xpts.identity import normalize_name,resolve_uuid_to_fpl_ids

def test_special_diacritics_normalize():
    assert normalize_name("Ferdi Kadıoğlu")==normalize_name("Ferdi Kadioglu")
    assert normalize_name("Filip Jørgensen")==normalize_name("Filip Jörgensen")

def test_middle_name_subset_resolves():
    f=pd.DataFrame([{"player_uuid":"u1","player":"Marcos Senesi"}])
    r=pd.DataFrame([{"id":72,"web_name":"Senesi","known_name":"","first_name":"Marcos","second_name":"Senesi Barón"}])
    m,detail=resolve_uuid_to_fpl_ids(f,r)
    assert m["u1"]==72
    assert detail[0].method in {"unique_token_subset","exact_normalized"}

def test_reordered_tokens_resolve():
    f=pd.DataFrame([{"player_uuid":"u1","player":"Wataru Endo"}])
    r=pd.DataFrame([{"id":392,"web_name":"Endo","known_name":"","first_name":"Endo","second_name":"Wataru"}])
    m,_=resolve_uuid_to_fpl_ids(f,r)
    assert m["u1"]==392

def test_ambiguous_surname_does_not_guess():
    f=pd.DataFrame([{"player_uuid":"u1","player":"Gonzalez"}])
    r=pd.DataFrame([
      {"id":1,"web_name":"Gonzalez","known_name":"","first_name":"Nico","second_name":"Gonzalez"},
      {"id":2,"web_name":"Gonzalez","known_name":"","first_name":"Enso","second_name":"Gonzalez Medina"},
    ])
    m,d=resolve_uuid_to_fpl_ids(f,r)
    assert "u1" not in m
    assert d[0].method=="unresolved"


def test_first_name_prefix_with_same_surname_resolves():
    f=pd.DataFrame([
      {"player_uuid":"u1","player":"Max Kilman"},
      {"player_uuid":"u2","player":"Treymaurice Nyoni"},
    ])
    r=pd.DataFrame([
      {"id":605,"web_name":"Kilman","known_name":"","first_name":"Maximilian","second_name":"Kilman"},
      {"id":396,"web_name":"Trey Nyoni","known_name":"","first_name":"Trey","second_name":"Nyoni"},
    ])
    m,d=resolve_uuid_to_fpl_ids(f,r)
    assert m["u1"]==605
    assert m["u2"]==396
