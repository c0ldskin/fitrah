"""Tests for the Stage 1B harness itself. Run:  PYTHONPATH=src python3 -m pytest -q

These check that the instruments are sound, so a Stage 1B result means what it
says: the defect-free copy of R is identical to R, generation is deterministic,
the reference model agrees with correct R, every injected defect is findable,
shrinking preserves a violation, and the in-process path matches the process path.
"""
from __future__ import annotations

import json

import pytest

from stage1b.defects import DEFECTS, DefectiveMonitor
from stage1b.direct import DirectMonitor
from stage1b.exhaustive import bounded_genesis, search
from stage1b.experiments import (FIXTURES, cross_check_process_path, fixture_genesis, lineage_history)
from stage1b.gen import CORES, generate, has_violation, replay, shrink

SEEDS = range(40)


def _trace(result):
    return [(s.get("decision"), s.get("reason"), s.get("state")) for s in result["steps"]]


def test_generation_is_deterministic():
    assert generate(123, 40) == generate(123, 40)
    assert generate(123, 40) != generate(124, 40)


@pytest.mark.parametrize("seed", list(SEEDS)[:20])
def test_defect_free_copy_is_identical_to_R(seed, tmp_path):
    h = generate(seed, 50)
    a = replay(h, log_path=tmp_path / "a.jsonl", run_id="eq")
    b = replay(h, monitor_cls=DefectiveMonitor, defect=None, log_path=tmp_path / "b.jsonl", run_id="eq")
    assert _trace(a) == _trace(b)
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


@pytest.mark.parametrize("genesis", [None, "spawn_denied", "mutate_denied"])
def test_correct_R_has_no_violations_and_verifier_accepts(genesis, tmp_path):
    g = fixture_genesis(genesis) if genesis else None
    for seed in SEEDS:
        r = replay(generate(seed, 50, g), genesis=g, log_path=tmp_path / "c.jsonl")
        assert not has_violation(r), seed
        assert r["verifier"]["ok"], (seed, r["verifier"]["violations"][:2])
        assert all("TC-22" in c for s in r["steps"] for c in s.get("conformance", [])), seed


def test_deep_lineage_clean_in_C(tmp_path):
    h, meta = lineage_history(30)
    r = replay(h, log_path=tmp_path / "l.jsonl")
    assert not has_violation(r) and r["verifier"]["ok"]
    assert sum(r["steps"][i]["decision"] == "allow" for i in meta["valid_birth_steps"]) == 30


@pytest.mark.parametrize("defect", list(DEFECTS))
def test_every_defect_has_a_bounded_counterexample(defect):
    g = None
    if defect == "D05":
        g = bounded_genesis(FIXTURES["spawn_denied"]["core"])
    if defect == "D07":
        g = bounded_genesis(FIXTURES["mutate_denied"]["core"])
    r = search(monitor_cls=DefectiveMonitor, defect=defect, stop_at_first=True, genesis=g, time_limit=60)
    assert r["counterexample"] is not None and len(r["counterexample"]["path"]) <= 3


def test_shrink_keeps_a_violation():
    h = next(generate(s, 50) for s in range(200)
             if has_violation(replay(generate(s, 50), monitor_cls=DefectiveMonitor, defect="D02")))
    pred = lambda hh: has_violation(replay(hh, monitor_cls=DefectiveMonitor, defect="D02"))  # noqa: E731
    small = shrink(h, pred)
    assert pred(small) and len(small) < len(h)


def test_TC22_duplicate_rule_core_is_blocked_by_R():
    """Documents finding TC-22: as a set the core equals the parent's, but R compares lists."""
    m = DirectMonitor(json.loads(json.dumps(__import__("stage1b.gen", fromlist=["GENESIS"]).GENESIS)),
                      "C", __import__("stage1b.gen", fromlist=["_Recorder"])._Recorder(None), "t", "t")
    got = m.submit("a0", {"op": "spawn", "child": {"core": CORES["duplicate_K1"], "C": ["read:vault"],
                                                   "Dg": []}, "program": []})
    assert (got["decision"], got["reason"]) == ("block", "CORE_MISMATCH")


def test_process_path_matches_in_process_path():
    r = cross_check_process_path(n=5, length=30)
    assert r["histories_compared"] == 5 and r["mismatched"] == 0


# --- TC-24: verifier completeness gaps found by Stage 1B (regressions) ------------------
def _flags_at(result, step_index):
    seq = result["steps"][step_index]["seq"]
    return [v for v in result["verifier"]["violations"] if v["seq"] == seq]


def _req(**kw):
    return json.dumps(kw, sort_keys=True)


def test_TC24_dead_agent_mutation_is_flagged(tmp_path):
    h = [["a0", _req(op="kill")], ["a0", _req(op="mutate", field="mut.s", value=1)]]
    r = replay(h, config="A", log_path=tmp_path / "d.jsonl")
    assert any("dead agent" in v["detail"] for v in _flags_at(r, 1))


def test_TC24_noop_protected_write_is_flagged(tmp_path):
    same_C = sorted(__import__("stage1b.gen", fromlist=["GENESIS"]).GENESIS["root"]["C"])
    h = [["a0", _req(op="mutate", field="C", value=same_C)]]
    r = replay(h, config="A", log_path=tmp_path / "n.jsonl")
    assert any("write to C" in v["detail"] for v in _flags_at(r, 0))


def test_TC24_claimed_identity_effect_is_flagged_in_A(tmp_path):
    spawn = _req(op="spawn", child={"core": CORES["canonical"], "C": ["read:vault"], "Dg": []}, program=[])
    write = _req(op="invoke", action="write", resource="vault", args={"file": "ledger.txt", "data": "x"}, **{"as": "a1"})
    r = replay([["a0", spawn], ["a0", write]], config="A", log_path=tmp_path / "i.jsonl")
    assert any(v["invariant"] == "IDENTITY" for v in _flags_at(r, 1))


def test_TC24_authority_judged_by_lawful_view(tmp_path):
    """After an (accepted, flagged) widening of Dg, a later spawn using the widened authority is
    itself flagged, rather than judged against the corrupted Dg."""
    widen = _req(op="mutate", field="Dg", value=["admin:vault", "read:vault", "spawn:R"])
    spawn = _req(op="spawn", child={"core": CORES["canonical"], "C": ["admin:vault"], "Dg": []}, program=[])
    r = replay([["a0", widen], ["a0", spawn]], config="A", log_path=tmp_path / "w.jsonl")
    assert any(v["invariant"] == "F2" for v in _flags_at(r, 1))
