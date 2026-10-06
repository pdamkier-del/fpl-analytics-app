"""Deterministic player identity resolver for historical UUID to FPL element IDs.

The historical model uses stable player UUIDs while the FPL API uses season-local
integer element IDs. Exact display-name equality is too brittle, so this module
resolves in strict confidence tiers and never silently guesses an ambiguous match.

Unresolved identities are intentionally returned as unresolved. Callers must use
an explicit fallback forecast rather than converting them to zero xP.
"""
from __future__ import annotations
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from collections import defaultdict

_SPECIAL_TRANSLATION = str.maketrans({
    "ı":"i","İ":"I","ø":"o","Ø":"O","đ":"d","Đ":"D","ł":"l","Ł":"L",
    "ß":"ss","æ":"ae","Æ":"AE","œ":"oe","Œ":"OE",
})

def normalize_name(value: object) -> str:
    s=str(value or "").translate(_SPECIAL_TRANSLATION)
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().casefold()
    return "".join(ch for ch in s if ch.isalnum())

def name_tokens(value: object) -> tuple[str,...]:
    s=str(value or "").translate(_SPECIAL_TRANSLATION)
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().casefold()
    return tuple(x for x in re.findall(r"[a-z0-9]+",s) if x)

@dataclass(frozen=True)
class IdentityMatch:
    player_uuid: str
    fpl_id: int | None
    method: str
    score: float
    margin: float

def _raw_aliases(row) -> list[str]:
    vals=[
        getattr(row,"web_name",""),
        getattr(row,"known_name",""),
        getattr(row,"first_name",""),
        getattr(row,"second_name",""),
        f"{getattr(row,'first_name','')} {getattr(row,'second_name','')}",
    ]
    out=[]
    for v in vals:
        v=str(v).strip()
        if v and v.lower()!="nan" and v not in out:
            out.append(v)
    return out

def resolve_uuid_to_fpl_ids(features, raw_players) -> tuple[dict[str,int], list[IdentityMatch]]:
    """Resolve unique historical player UUIDs to FPL IDs conservatively."""
    feat=features[["player_uuid","player"]].drop_duplicates().copy()
    raw=raw_players.drop_duplicates("id").copy()

    exact=defaultdict(set)
    token_aliases={}
    norm_aliases={}
    for r in raw.itertuples():
        pid=int(r.id)
        norms=[]; toks=[]
        for a in _raw_aliases(r):
            n=normalize_name(a)
            if n:
                exact[n].add(pid); norms.append(n)
            t=frozenset(name_tokens(a))
            if t:toks.append(t)
        norm_aliases[pid]=norms
        token_aliases[pid]=toks

    mapping={}
    matches=[]
    unresolved=[]
    for r in feat.itertuples():
        uid=str(r.player_uuid); n=normalize_name(r.player)
        ids=exact.get(n,set())
        if len(ids)==1:
            pid=next(iter(ids))
            mapping[uid]=pid
            matches.append(IdentityMatch(uid,pid,"exact_normalized",1.0,1.0))
        else:
            unresolved.append((uid,str(r.player)))

    still=[]
    for uid,name in unresolved:
        ft=frozenset(name_tokens(name))
        candidates=[]
        if ft:
            for pid,tsets in token_aliases.items():
                best=0.0; method=None
                for rt in tsets:
                    if ft==rt and len(ft)>=2:
                        score=1.0; meth="equal_token_set"
                    elif len(ft)>=2 and (ft.issubset(rt) or rt.issubset(ft)) and len(ft & rt)>=2:
                        score=0.96 + 0.02*len(ft & rt)/max(len(ft),len(rt))
                        meth="unique_token_subset"
                    else:
                        continue
                    if score>best: best=score; method=meth
                if best>0:candidates.append((best,pid,method))
        candidates.sort(reverse=True)
        if candidates:
            top=candidates[0]
            second=candidates[1][0] if len(candidates)>1 else 0.0
            tied=[x for x in candidates if abs(x[0]-top[0])<1e-12]
            if len(tied)==1 and top[0]>=0.96:
                mapping[uid]=top[1]
                matches.append(IdentityMatch(uid,top[1],top[2],top[0],top[0]-second))
                continue
        still.append((uid,name))

    # Tier 3b: unique surname plus compatible first-name prefix. This handles
    # stable nickname/full-name variants such as Max/Maximilian Kilman and
    # Trey/Treymaurice Nyoni without accepting surname-only guesses.
    prefix_still=[]
    for uid,name in still:
        ft=name_tokens(name)
        candidates=[]
        if len(ft)>=2:
            ff,fs=ft[0],ft[-1]
            for pid,tsets in token_aliases.items():
                ok=False
                for rt in tsets:
                    rtt=tuple(rt)
                    # sets lose ordering, so derive ordered tokens from raw aliases.
                for alias in _raw_aliases(raw[raw.id.astype(int).eq(pid)].iloc[0]):
                    at=name_tokens(alias)
                    if len(at)<2: continue
                    af,asur=at[0],at[-1]
                    if fs==asur and min(len(ff),len(af))>=3 and (ff.startswith(af) or af.startswith(ff)):
                        ok=True; break
                if ok:candidates.append(pid)
        candidates=sorted(set(candidates))
        if len(candidates)==1:
            pid=candidates[0]
            mapping[uid]=pid
            matches.append(IdentityMatch(uid,pid,"surname_first_prefix",0.95,0.95))
        else:
            prefix_still.append((uid,name))
    still=prefix_still

    for uid,name in still:
        fn=normalize_name(name)
        scored=[]
        for pid,norms in norm_aliases.items():
            if norms:
                scored.append((max(SequenceMatcher(None,fn,rn).ratio() for rn in norms),pid))
        scored.sort(reverse=True)
        best=scored[0] if scored else (0.0,None)
        second=scored[1][0] if len(scored)>1 else 0.0
        margin=best[0]-second
        accept=(best[0]>=0.88 and margin>=0.04) or (best[0]>=0.84 and margin>=0.12)
        if accept and best[1] is not None:
            mapping[uid]=int(best[1])
            matches.append(IdentityMatch(uid,int(best[1]),"conservative_fuzzy",float(best[0]),float(margin)))
        else:
            matches.append(IdentityMatch(uid,None,"unresolved",float(best[0]),float(margin)))
    return mapping,matches
