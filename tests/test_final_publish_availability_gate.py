"""No live final-model promotion without the user-approved hard-availability MM policy."""
import hashlib,json
from pathlib import Path
import pytest
import publish_final_model as pub


def prepare(tmp_path,monkeypatch):
    monkeypatch.setattr(pub,"ROOT",tmp_path)
    path=tmp_path/"work"/"live-final-model"/"policy.json"
    path.parent.mkdir(parents=True)
    pol={"availability_policy":"live-hard-eligibility-v1",
         "source_model_version":"fpl-model-2026-10-09-assembled",
         "origin_gw":6,"frozen_mm_unchanged":True,
         "full_final_chain_live_certified":False,
         "published_mm_sha256":"a"*64,
         "raw_input_sha256":"b"*64,
         "official_team_news_sha256":"c"*64,
         "source_news":{"official_news_gw":6,"players_with_verified_news":667}}
    def save():
        path.write_text(json.dumps(pol))
        return {"availability_policy_path":str(path.relative_to(tmp_path)),
                "availability_policy_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    m=save()
    return pol,save,m,{"mm":{"sha256":"a"*64}}


def check(m,parts):
    return pub.verify_approved_live_availability(m,parts,"fpl-model-2026-10-09-assembled",6)


def test_hard_out_policy_required_to_certify_final_model(tmp_path,monkeypatch):
    pol,save,m,parts=prepare(tmp_path,monkeypatch)
    assert check(m,parts)["policy"]=="live-hard-eligibility-v1"
    with pytest.raises(RuntimeError,match="Missing approved"):
        check({},parts)


@pytest.mark.parametrize("change,value,expected",[
  ("availability_policy","live-hard-eligibility-v2","approved"),
  ("origin_gw",7,"scoped"),
  ("frozen_mm_unchanged",False,"preserve"),
  ("full_final_chain_live_certified",True,"must not"),
  ("published_mm_sha256","d"*64,"differs"),
  ("source_model_version","OTHER","another frozen"),
  ("source_news",{"official_news_gw":7,"players_with_verified_news":667},"coverage"),
])
def test_reject_wrong_contract_details(tmp_path,monkeypatch,change,value,expected):
    pol,save,m,parts=prepare(tmp_path,monkeypatch)
    pol[change]=value
    m=save()
    with pytest.raises(RuntimeError,match=expected):
        check(m,parts)


def test_tampered_policy_is_rejected(tmp_path,monkeypatch):
    pol,save,m,parts=prepare(tmp_path,monkeypatch)
    pol["origin_gw"]=7
    save()
    with pytest.raises(RuntimeError,match="checksum"):
        check(m,parts)


def test_other_mm_digest_is_rejected(tmp_path,monkeypatch):
    pol,save,m,parts=prepare(tmp_path,monkeypatch)
    with pytest.raises(RuntimeError,match="differs"):
        check(m,{"mm":{"sha256":"d"*64}})
