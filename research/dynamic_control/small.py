"""Finite scenario-tree transfer problems with exact expected-point references."""
from dataclasses import dataclass, replace
from functools import cache
from itertools import combinations
import json
from math import log, sqrt
from pathlib import Path
import random
import statistics
from time import perf_counter


@dataclass(frozen=True)
class State:
    owned: tuple[tuple[int, int], ...]
    bank: int
    ft: int


@dataclass(frozen=True)
class Node:
    price: tuple[int, ...]
    points: tuple[float, ...]
    children: tuple[tuple[float, int], ...] = ()


@dataclass(frozen=True)
class Case:
    name: str
    nodes: tuple[Node, ...]
    initial: State
    starters: int = 1


def actions(case, node_id, state):
    """Enumerate fixed-size squads and budgets, with UK FPL sale accounting."""
    node = case.nodes[node_id]
    owned = dict(state.owned)
    for squad in combinations(range(len(node.price)), len(owned)):
        outgoing = owned.keys() - set(squad)
        incoming = set(squad) - owned.keys()
        sale = sum(min(node.price[i], owned[i] + max(0, node.price[i] - owned[i]) // 2)
                   for i in outgoing)
        bank = state.bank + sale - sum(node.price[i] for i in incoming)
        if bank < 0:
            continue
        count = len(incoming)
        after = State(tuple((i, owned.get(i, node.price[i])) for i in squad),
                      bank, min(5, max(0, state.ft - count) + 1))
        points = sum(sorted((node.points[i] for i in squad), reverse=True)[:case.starters])
        yield squad, after, points - 4 * max(0, count - state.ft)


def exact_solver(case):
    @cache
    def value(node, state):
        return max(q(node, after, reward) for _, after, reward in actions(case, node, state))

    def q(node, after, reward):
        return reward + sum(p * value(child, after) for p, child in case.nodes[node].children)

    return value, q


def exact_action(case, node, state, q):
    return max(actions(case, node, state), key=lambda a: q(node, a[1], a[2]))


def committed_value(case, state, q):
    """Value when the next squad must be chosen before seeing the branch."""
    children = case.nodes[0].children
    if not children:
        return max(a[2] for a in actions(case, 0, state))
    totals = []
    for _, after, reward in actions(case, 0, state):
        options = [
            {squad: p * q(child, next_state, points)
             for squad, next_state, points in actions(case, child, after)}
            for p, child in children
        ]
        common = set(options[0]).intersection(*options[1:])
        totals.append(reward + max(sum(option[squad] for option in options) for squad in common))
    return max(totals)


def beam_action(case, node, state, depth, width, rho=1.0, terminal=False):
    # Certainty-equivalent path uses the most likely next node. The first
    # decision is common across branches. Later real observations trigger replan.
    beam = [(0.0, state, None)]
    first_node = node
    for step in range(depth):
        children = case.nodes[node].children
        last = step + 1 == depth
        expanded = {}
        for score, current, first in beam:
            for action in actions(case, node, current):
                _, after, reward = action
                count = len(set(action[0]) - dict(current.owned).keys())
                hit = 4 * max(0, count - current.ft)
                total = score + rho ** step * (reward + hit) - hit
                incumbent = expanded.get(after)
                if incumbent is None or total > incumbent[0]:
                    expanded[after] = (total, after, first or action)

        def rank(item):
            score, after, _ = item
            if terminal and last:
                # One-step Bellman continuation, integrating observable shocks.
                score += rho ** (step + 1) * sum(
                    p * max(a[2] for a in actions(case, child, after)) for p, child in children
                )
            return score

        beam = sorted(expanded.values(), key=rank, reverse=True)[:width]
        if not children or last:
            break
        node = max(children)[1]
    assert beam[0][2] in list(actions(case, first_node, state))
    return beam[0][2]


def mcts_action(case, state, simulations, seed):
    rng = random.Random(seed)
    visits = {}
    means = {}

    def simulate(node, current):
        options = list(actions(case, node, current))
        keys = [(node, current, a[0]) for a in options]
        n = sum(visits.get(k, 0) for k in keys)
        index = max(range(len(keys)), key=lambda j: (
            means[keys[j]] + 8 * sqrt(log(max(n, 1)) / visits[keys[j]])
            if keys[j] in visits else float("inf")
        ))
        key = keys[index]
        _, after, total = options[index]
        children = case.nodes[node].children
        if children:
            probabilities, ids = zip(*children)
            child = rng.choices(ids, weights=probabilities)[0]
            total += simulate(child, after)
        count = visits[key] = visits.get(key, 0) + 1
        average = means.get(key, 0.0)
        means[key] = average + (total - average) / count
        return total

    for _ in range(simulations):
        simulate(0, state)
    return max(actions(case, 0, state), key=lambda a: (
        visits.get((0, state, a[0]), 0), means.get((0, state, a[0]), -float("inf"))
    ))


def load_cases(path):
    for raw in json.loads(path.read_text()):
        nodes = tuple(Node(tuple(n["price"]), tuple(n["points"]),
                           tuple(tuple(c) for c in n.get("children", []))) for n in raw["nodes"])
        seed = raw["initial"]
        state = State(tuple(tuple(x) for x in seed["owned"]), seed["bank"], seed["ft"])
        yield Case(raw["name"], nodes, state, raw.get("starters", 1))


def experiment(cases):
    results = []
    for case in cases:
        started = perf_counter()
        value, q = exact_solver(case)
        optimal = exact_action(case, 0, case.initial, q)
        reference = value(0, case.initial)
        exact_seconds = perf_counter() - started
        recourse_value = reference - committed_value(case, case.initial, q)
        hold = tuple(i for i, _ in case.initial.owned)
        hold_action = next(a for a in actions(case, 0, case.initial) if a[0] == hold)
        candidates = {
            "exact": (reference, optimal[0], exact_seconds, 0.0),
        }
        methods = {
            "greedy": lambda: beam_action(case, 0, case.initial, 1, 1),
            "rho060": lambda: beam_action(case, 0, case.initial, 6, 8, .6),
            "mpc2": lambda: beam_action(case, 0, case.initial, 2, 8),
            "beam1": lambda: beam_action(case, 0, case.initial, 6, 1),
            "beam8": lambda: beam_action(case, 0, case.initial, 6, 8),
            "terminal": lambda: beam_action(case, 0, case.initial, 1, 8, terminal=True),
        }
        for name, policy in methods.items():
            started = perf_counter()
            squad, after, reward = policy()
            elapsed = perf_counter() - started
            candidates[name] = (q(0, after, reward), squad, elapsed, 0.0)
        started = perf_counter()
        mc = [mcts_action(case, case.initial, 512, seed) for seed in range(12)]
        elapsed = perf_counter() - started
        values = [q(0, after, reward) for _, after, reward in mc]
        candidates["mcts512"] = (statistics.mean(values), [x[0] for x in mc],
                                  elapsed / len(mc), statistics.stdev(values))
        for method, (value_after, squad, seconds, sd) in candidates.items():
            results.append(dict(case=case.name, method=method, squad=squad, value=value_after,
                                gap=reference - value_after, seconds=seconds, seed_sd=sd,
                                recourse_value=recourse_value,
                                roll_gap=reference - q(0, hold_action[1], hold_action[2]),
                                ft_value=value(0, replace(case.initial, ft=case.initial.ft + 1)) - reference,
                                bank_tick_value=value(0, replace(case.initial, bank=case.initial.bank + 1)) - reference))
    return results


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    print(json.dumps(experiment(load_cases(folder / "cases.json")), indent=2))
