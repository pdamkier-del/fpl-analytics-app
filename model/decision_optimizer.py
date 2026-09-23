from __future__ import annotations

from pathlib import Path
from typing import Any
import json

FORMATIONS = ((3, 5, 2), (3, 4, 3), (4, 5, 1), (4, 4, 2), (4, 3, 3), (5, 4, 1), (5, 3, 2), (5, 2, 3))
POSITIONS = ("GK", "DEF", "MID", "FWD")
BAD_INCOMING_STATUSES = {"injured", "suspended", "unavailable"}
_LINEUP_CACHE: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _gw_xpts(player: dict[str, Any], gi: int) -> float:
    gws = player.get("gws") or []
    if gi < 0 or gi >= len(gws):
        return 0.0
    return _num(gws[gi].get("xpts"))


def _sum_xpts(player: dict[str, Any], horizon: int, start_gi: int = 0) -> float:
    return sum(_gw_xpts(player, gi) for gi in range(start_gi, start_gi + horizon))


def _player_brief(player: dict[str, Any], gi: int | None = None) -> dict[str, Any]:
    out = {
        "id": int(player.get("id")),
        "player": player.get("player"),
        "full_name": player.get("full_name"),
        "club": player.get("club"),
        "pos": player.get("pos"),
        "price": _num(player.get("price")),
        "status": player.get("status") or "Available",
        "chance": player.get("chance"),
    }
    if gi is not None:
        gws = player.get("gws") or []
        gw = gws[gi] if 0 <= gi < len(gws) else {}
        out.update({
            "gw": gw.get("gw"),
            "fixture": gw.get("fixture"),
            "xpts": _num(gw.get("xpts")),
            "xmins": _num(gw.get("xmins")),
            "pstart": _num(gw.get("pstart")),
        })
    return out


def _club_ok(squad: tuple[dict[str, Any], ...]) -> bool:
    counts: dict[str, int] = {}
    for p in squad:
        club = str(p.get("club") or "")
        counts[club] = counts.get(club, 0) + 1
        if counts[club] > 3:
            return False
    return True


def _squad_key(squad: tuple[dict[str, Any], ...]) -> tuple[int, ...]:
    return tuple(sorted(int(p.get("id")) for p in squad))


def best_lineup(squad: tuple[dict[str, Any], ...], gi: int) -> dict[str, Any]:
    cache_key=(_squad_key(squad),gi)
    cached=_LINEUP_CACHE.get(cache_key)
    if cached is not None:
        return cached
    by = {pos: [] for pos in POSITIONS}
    for p in squad:
        pos = p.get("pos")
        if pos in by:
            by[pos].append(p)
    for pos in POSITIONS:
        by[pos].sort(key=lambda p: _gw_xpts(p, gi), reverse=True)

    best: dict[str, Any] | None = None
    for d, m, f in FORMATIONS:
        if len(by["GK"]) < 1 or len(by["DEF"]) < d or len(by["MID"]) < m or len(by["FWD"]) < f:
            continue
        xi = tuple([by["GK"][0], *by["DEF"][:d], *by["MID"][:m], *by["FWD"][:f]])
        base = sum(_gw_xpts(p, gi) for p in xi)
        captain = max(xi, key=lambda p: _gw_xpts(p, gi))
        total = base + _gw_xpts(captain, gi)
        if best is None or total > best["total"]:
            xi_ids = {int(p["id"]) for p in xi}
            bench_gk = next((p for p in by["GK"] if int(p["id"]) not in xi_ids), None)
            bench_out = sorted(
                [p for p in squad if int(p["id"]) not in xi_ids and p.get("pos") != "GK"],
                key=lambda p: _gw_xpts(p, gi),
                reverse=True,
            )
            bench = tuple([p for p in [bench_gk, *bench_out] if p is not None])
            best = {
                "formation": f"{d}-{m}-{f}",
                "xi": xi,
                "captain": captain,
                "bench": bench,
                "base": base,
                "total": total,
            }
    if best is None:
        raise ValueError("Squad cannot produce a legal FPL starting XI")
    _LINEUP_CACHE[cache_key]=best
    return best


def _objective(squad: tuple[dict[str, Any], ...], horizon: int, start_gi: int = 0) -> float:
    return sum(best_lineup(squad, start_gi + gi)["total"] for gi in range(horizon))


def _validate_squad(players_by_id: dict[int, dict[str, Any]], ids: list[int]) -> tuple[dict[str, Any], ...]:
    squad = tuple(players_by_id[i] for i in ids if i in players_by_id)
    if len(squad) != 15:
        raise ValueError(f"Optimizer needs a complete 15-player squad; {len(squad)} players were resolved")
    counts = {pos: sum(1 for p in squad if p.get("pos") == pos) for pos in POSITIONS}
    if counts != {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}:
        raise ValueError(f"Squad has invalid position counts: {counts}")
    if not _club_ok(squad):
        raise ValueError("Squad exceeds the 3-players-per-club rule")
    return squad


def _candidate_pools(players: list[dict[str, Any]], horizon: int) -> dict[str, tuple[dict[str, Any], ...]]:
    pools: dict[str, tuple[dict[str, Any], ...]] = {}
    for pos in POSITIONS:
        arr = [
            p for p in players
            if p.get("pos") == pos
            and p.get("price") is not None
            and str(p.get("status") or "Available").lower() not in BAD_INCOMING_STATUSES
        ]
        keep: dict[int, dict[str, Any]] = {}
        def add(items):
            for p in items:
                keep[int(p["id"])] = p
        add(sorted(arr, key=lambda p: _sum_xpts(p, horizon), reverse=True)[:8])
        add(sorted(arr, key=lambda p: _sum_xpts(p, horizon) / max(_num(p.get("price")), 0.1), reverse=True)[:14])
        add(sorted(arr, key=lambda p: _num(p.get("price")))[:7])
        for gi in range(horizon):
            add(sorted(arr, key=lambda p: _gw_xpts(p, gi), reverse=True)[:4])
        pools[pos] = tuple(keep.values())
    return pools


def _one_move_actions(squad: tuple[dict[str, Any], ...], bank: float, pools: dict[str, tuple[dict[str, Any], ...]]):
    ids = {int(p["id"]) for p in squad}
    actions = []
    for idx, outgoing in enumerate(squad):
        for incoming in pools.get(str(outgoing.get("pos")), ()): 
            iid = int(incoming["id"])
            if iid in ids:
                continue
            new_bank = bank + _num(outgoing.get("price")) - _num(incoming.get("price"))
            if new_bank < -1e-9:
                continue
            new_squad = list(squad)
            new_squad[idx] = incoming
            new_squad_t = tuple(new_squad)
            if not _club_ok(new_squad_t):
                continue
            actions.append((new_squad_t, new_bank, (outgoing, incoming)))
    return actions


def _prune_actions(actions: list[dict[str, Any]], gi: int, limit: int) -> list[dict[str, Any]]:
    if not actions:
        return []
    by_score = sorted(actions, key=lambda a: (best_lineup(a["squad"], gi)["total"] - a["hit"], a["bank"]), reverse=True)[:limit]
    by_cash = sorted(actions, key=lambda a: (a["bank"], best_lineup(a["squad"], gi)["total"] - a["hit"]), reverse=True)[: max(8, limit // 4)]
    merged: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}
    for a in [*by_score, *by_cash]:
        key = (_squad_key(a["squad"]), len(a["moves"]))
        old = merged.get(key)
        if old is None or a["hit"] < old["hit"] or (a["hit"] == old["hit"] and a["bank"] > old["bank"]):
            merged[key] = a
    return list(merged.values())


def _action_options(state: dict[str, Any], gi: int, max_transfers: int, pools, hit_cost: float):
    options = [{
        "squad": state["squad"], "bank": state["bank"], "moves": tuple(), "hit": 0.0,
        "ft_next": min(5, state["ft"] + 1),
    }]
    if max_transfers <= 0:
        return options
    one = []
    for sq, bank, move in _one_move_actions(state["squad"], state["bank"], pools):
        one.append({
            "squad": sq, "bank": bank, "moves": (move,),
            "hit": max(0, 1 - state["ft"]) * hit_cost,
            "ft_next": min(5, max(0, state["ft"] - 1) + 1),
        })
    one = _prune_actions(one, gi, 28)
    options.extend(one)

    if max_transfers >= 2:
        two = []
        seeds = _prune_actions(one, gi, 7)
        for seed in seeds:
            for sq, bank, move in _one_move_actions(seed["squad"], seed["bank"], pools):
                bought_ids = {int(m[1]["id"]) for m in seed["moves"]}
                if int(move[0]["id"]) in bought_ids:
                    continue
                moves = (*seed["moves"], move)
                two.append({
                    "squad": sq, "bank": bank, "moves": moves,
                    "hit": max(0, 2 - state["ft"]) * hit_cost,
                    "ft_next": min(5, max(0, state["ft"] - 2) + 1),
                })
        two = _prune_actions(two, gi, 16)
        options.extend(two)

    if max_transfers >= 3 and gi == 0:
        three = []
        seeds = _prune_actions([o for o in options if len(o["moves"]) == 2], gi, 4)
        for seed in seeds:
            for sq, bank, move in _one_move_actions(seed["squad"], seed["bank"], pools):
                bought_ids = {int(m[1]["id"]) for m in seed["moves"]}
                if int(move[0]["id"]) in bought_ids:
                    continue
                moves = (*seed["moves"], move)
                three.append({
                    "squad": sq, "bank": bank, "moves": moves,
                    "hit": max(0, 3 - state["ft"]) * hit_cost,
                    "ft_next": min(5, max(0, state["ft"] - 3) + 1),
                })
        options.extend(_prune_actions(three, gi, 8))

    dedup: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}
    for action in options:
        key = (_squad_key(action["squad"]), len(action["moves"]))
        old = dedup.get(key)
        if old is None or action["hit"] < old["hit"] or (action["hit"] == old["hit"] and action["bank"] > old["bank"]):
            dedup[key] = action
    return list(dedup.values())


def _move_signature(actions: tuple[dict[str, Any], ...]) -> tuple:
    parts = []
    for a in actions:
        for outgoing, incoming in a["moves"]:
            parts.append((a["gw"], int(outgoing["id"]), int(incoming["id"])))
    return tuple(parts)


def _serialize_lineup(line: dict[str, Any], gi: int) -> dict[str, Any]:
    return {
        "formation": line["formation"],
        "base_xpts": line["base"],
        "total_xpts": line["total"],
        "captain": _player_brief(line["captain"], gi),
        "xi": [_player_brief(p, gi) for p in line["xi"]],
        "bench": [_player_brief(p, gi) for p in line["bench"]],
    }


def _serialize_plan(state: dict[str, Any], baseline: float, buffer_points: float) -> dict[str, Any]:
    actions_out = []
    transfer_count = 0
    for a in state["actions"]:
        transfer_count += len(a["moves"])
        actions_out.append({
            "gw": a["gw"],
            "moves": [{"out": _player_brief(o), "in": _player_brief(i)} for o, i in a["moves"]],
            "ft_before": a["ft_before"],
            "ft_after": a["ft_after"],
            "hit": a["hit"],
            "bank": a["bank"],
            "lineup": _serialize_lineup(a["line"], a["gi"]),
        })
    raw_after_hits = state["raw_score"] - state["hits"]
    decision_score = raw_after_hits - buffer_points * transfer_count
    return {
        "raw_xpts": state["raw_score"],
        "score_after_hits": raw_after_hits,
        "decision_score": decision_score,
        "baseline_score": baseline,
        "net_gain": raw_after_hits - baseline,
        "decision_gain": decision_score - baseline,
        "hits": state["hits"],
        "uncertainty_buffer_total": buffer_points * transfer_count,
        "transfer_count": transfer_count,
        "bank_end": state["bank"],
        "ft_end": state["ft"],
        "actions": actions_out,
    }

def optimize_plan(data: dict[str, Any], squad_cfg: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    _LINEUP_CACHE.clear()
    players = list(data.get("forecasts") or [])
    by_id = {int(p["id"]): p for p in players}
    original = _validate_squad(by_id, [int(x) for x in squad_cfg.get("player_ids") or []])
    horizon = int(request.get("horizon", 6))
    if horizon not in (1, 3, 6):
        raise ValueError("horizon must be 1, 3 or 6")
    mode = str(request.get("mode") or "rolling")
    max_transfers_now = max(0, min(3, int(request.get("max_transfers", 2))))
    max_transfers_future = max(0, min(2, int(request.get("max_transfers_future", 1))))
    bank = max(0.0, _num(request.get("bank", squad_cfg.get("bank", 0.0))))
    ft = max(0, min(5, int(request.get("free_transfers", squad_cfg.get("free_transfers", 1) or 1))))
    hit_cost = _num(request.get("hit_cost", 4.0), 4.0)
    buffer_points = max(0.0, _num(request.get("uncertainty_buffer", 2.0), 2.0))
    allow_hits = bool(request.get("allow_hits", True))
    top_n = max(1, min(5, int(request.get("top_n", 3))))
    baseline = _objective(original, horizon)
    pools = _candidate_pools(players, horizon)
    next_gw = int((data.get("meta") or {}).get("next_gw") or 0)

    states = [{"squad": original, "bank": bank, "ft": ft, "raw_score": 0.0, "hits": 0.0, "transfer_count": 0, "actions": tuple()}]
    for gi in range(horizon):
        candidates: dict[tuple[tuple[int, ...], int, int], dict[str, Any]] = {}
        for st in states:
            if mode == "now":
                allowed = max_transfers_now if gi == 0 else 0
            else:
                allowed = max_transfers_now if gi == 0 else max_transfers_future
            for action in _action_options(st, gi, allowed, pools, hit_cost):
                if not allow_hits and action["hit"] > 0:
                    continue
                line = best_lineup(action["squad"], gi)
                action_doc = {
                    "gi": gi, "gw": next_gw + gi, "moves": action["moves"], "hit": action["hit"],
                    "ft_before": st["ft"], "ft_after": action["ft_next"], "line": line, "bank": action["bank"],
                }
                ns = {
                    "squad": action["squad"], "bank": action["bank"], "ft": action["ft_next"],
                    "raw_score": st["raw_score"] + line["total"],
                    "hits": st["hits"] + action["hit"],
                    "transfer_count": st["transfer_count"] + len(action["moves"]),
                    "actions": (*st["actions"], action_doc),
                }
                ns["decision_score_so_far"] = ns["raw_score"] - ns["hits"] - buffer_points * ns["transfer_count"]
                key = (_squad_key(ns["squad"]), ns["ft"], int(round(ns["bank"] * 10)))
                old = candidates.get(key)
                if old is None or ns["decision_score_so_far"] > old["decision_score_so_far"]:
                    candidates[key] = ns
        arr = list(candidates.values())
        remaining = horizon - gi - 1
        for state in arr:
            future = _objective(state["squad"], remaining, gi + 1) if remaining else 0.0
            state["heuristic"] = state["decision_score_so_far"] + future + 0.08 * state["bank"] + 0.08 * state["ft"]
        arr.sort(key=lambda state: state["heuristic"], reverse=True)
        cash = sorted(arr, key=lambda state: (state["bank"], state["heuristic"]), reverse=True)[:10]
        ft_rich = sorted(arr, key=lambda state: (state["ft"], state["heuristic"]), reverse=True)[:8]
        merged: dict[tuple[tuple[int, ...], int, int], dict[str, Any]] = {}
        for state in [*arr[:48], *cash, *ft_rich]:
            key = (_squad_key(state["squad"]), state["ft"], int(round(state["bank"] * 10)))
            merged[key] = state
        states = list(merged.values())

    def final_decision_score(state):
        return state["raw_score"] - state["hits"] - buffer_points * state["transfer_count"]

    states.sort(key=lambda state: (final_decision_score(state), -state["hits"], state["bank"]), reverse=True)
    distinct, seen = [], set()
    for state in states:
        sig = _move_signature(state["actions"])
        if sig in seen:
            continue
        seen.add(sig)
        distinct.append(state)
        if len(distinct) >= top_n:
            break
    if not distinct:
        raise ValueError("Optimizer could not produce a plan")

    return {
        "meta": {
            "mode": mode, "horizon": horizon, "max_transfers_now": max_transfers_now,
            "max_transfers_future": max_transfers_future, "bank_start": bank, "free_transfers_start": ft,
            "hit_cost": hit_cost, "uncertainty_buffer_per_transfer": buffer_points, "allow_hits": allow_hits,
            "search_method": "beam_search_with_cash_and_ft_preservation", "global_optimum_guaranteed": False,
        },
        "current": {"squad": [_player_brief(p) for p in original], "baseline_score": baseline},
        "plans": [_serialize_plan(state, baseline, buffer_points) for state in distinct],
    }

def manual_transfer(data: dict[str, Any], squad_cfg: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    _LINEUP_CACHE.clear()
    players = list(data.get("forecasts") or [])
    by_id = {int(p["id"]): p for p in players}
    original = _validate_squad(by_id, [int(x) for x in squad_cfg.get("player_ids") or []])
    out_id, in_id = int(request.get("out_id")), int(request.get("in_id"))
    if out_id not in by_id or in_id not in by_id:
        raise ValueError("Unknown player")
    outgoing, incoming = by_id[out_id], by_id[in_id]
    if outgoing not in original:
        raise ValueError("OUT player is not in My Team")
    if outgoing.get("pos") != incoming.get("pos"):
        raise ValueError("Manual one-for-one transfer must keep the same position")
    if incoming in original:
        raise ValueError("IN player is already in My Team")
    bank = max(0.0, _num(request.get("bank", squad_cfg.get("bank", 0.0))))
    ft = max(0, min(5, int(request.get("free_transfers", squad_cfg.get("free_transfers", 1) or 1))))
    hit_cost = _num(request.get("hit_cost", 4.0), 4.0)
    new_bank = bank + _num(outgoing.get("price")) - _num(incoming.get("price"))
    if new_bank < -1e-9:
        raise ValueError("Transfer is not affordable with current-price budget")
    new_squad = list(original)
    new_squad[new_squad.index(outgoing)] = incoming
    new_squad_t = tuple(new_squad)
    if not _club_ok(new_squad_t):
        raise ValueError("Transfer would exceed 3 players from one club")
    hit = max(0, 1 - ft) * hit_cost
    comparisons = []
    for horizon in (1, 3, 6):
        before, after = _objective(original, horizon), _objective(new_squad_t, horizon)
        comparisons.append({"horizon": horizon, "before": before, "after": after, "raw_gain": after-before,
                            "hit": hit, "net_gain": after-before-hit})
    return {"out": _player_brief(outgoing), "in": _player_brief(incoming), "bank_before": bank,
            "bank_after": new_bank, "free_transfers": ft, "hit": hit, "comparisons": comparisons}


def load_data(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
