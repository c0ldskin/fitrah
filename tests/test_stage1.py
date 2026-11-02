"""Lab 0 Stage 1 tests. Run from the repository root:  PYTHONPATH=src python3 -m pytest -q"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.evidence import EvidenceLog, load_signing_key
from runtime.monitor import Monitor
from simulator.scenarios import (CONTROLS, CORE, FIXTURE_FOR, SCENARIOS, SPAWN, SPAWN_Q, READ, build,
                                 genesis_for, mutate, spawn)
from simulator.verify import Verifier

LAB = Path(__file__).resolve().parents[1] / "experiments" / "lab0"
GENESIS = json.loads((LAB / "genesis.json").read_text())
PUB = (LAB / "keys" / "test-signing.pub").read_text().split()[0]
FIXTURES = json.loads((LAB / "fixtures.json").read_text())
KEY = load_signing_key(LAB / "keys" / "test-signing.seed")
BY_ID = {s[0]: s for s in SCENARIOS}


def run(tmp_path, config, scenarios=SCENARIOS, genesis=None, monitor_cls=Monitor, name="log"):
    path = tmp_path / f"{name}-{config}.jsonl"
    log = EvidenceLog(path, KEY)
    out = {}
    for sid, _, _, _, _, steps in scenarios:
        g = genesis if genesis is not None else genesis_for(sid)
        fixture = FIXTURE_FOR.get(sid) if genesis is None else None
        program, schedule, tests, _ = build(steps, g["root"]["core"])
        outcomes = monitor_cls(g, config, log, sid, f"t-{config}", fixture=fixture).run(program, schedule)
        out[sid] = [outcomes[i] for i in tests]
    log.close()
    return path, out


def verify(path, genesis=GENESIS):
    return Verifier(genesis, PUB, FIXTURES).run(path.read_bytes().splitlines())


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    d = tmp_path_factory.mktemp("stage1")
    return {c: run(d, c) for c in "ABC"}


# --- Configuration C: every scenario decision matches the spec -------------------------
@pytest.mark.parametrize("sid", [s[0] for s in SCENARIOS])
def test_config_C_matches_spec(runs, sid):
    _, _, _, dec, reason, _ = BY_ID[sid]
    for t in runs["C"][1][sid]:
        assert (t["decision"], t["reason"]) == (dec, reason)


def test_config_C_verifier_clean(runs):
    rep = verify(runs["C"][0])
    assert rep["ok"], rep


def test_no_false_blocks(runs):
    for sid in CONTROLS:
        assert all(t["decision"] == "allow" for t in runs["C"][1][sid])


# --- Configuration A: violations really happen, and the verifier sees all of them ------
def test_baseline_executes_and_verifier_detects_every_violation(runs):
    rep = verify(runs["A"][0])
    flagged = {v["scenario"] for v in rep["violations"]}
    for sid, *_ in SCENARIOS:
        executed = all(t["decision"] == "allow" for t in runs["A"][1][sid])
        if sid in CONTROLS:
            assert executed and sid not in flagged
        elif sid == "S42":
            assert not executed  # malformed requests cannot execute even without checks (TC-03)
        else:
            assert executed and sid in flagged, sid


def test_B_equals_A_for_scripted_agents(runs):
    a = {k: [(t["decision"], t["reason"]) for t in v] for k, v in runs["A"][1].items()}
    b = {k: [(t["decision"], t["reason"]) for t in v] for k, v in runs["B"][1].items()}
    assert a == b


def test_reproducible(tmp_path):
    p1, _ = run(tmp_path, "C", name="r1")
    p2, _ = run(tmp_path, "C", name="r2")
    assert p1.read_bytes() == p2.read_bytes()


# --- Fault injection: a weakened R must be caught by the independent verifier ----------
class NoBirthChecks(Monitor):
    def _enforced(self, a, req):
        return self._baseline(a, req) if req["op"] == "spawn" else super()._enforced(a, req)


class NoInvokeChecks(Monitor):
    def _enforced(self, a, req):
        return self._baseline(a, req) if req["op"] == "invoke" else super()._enforced(a, req)


class NoMutateChecks(Monitor):
    def _enforced(self, a, req):
        return self._baseline(a, req) if req["op"] == "mutate" else super()._enforced(a, req)


@pytest.mark.parametrize("cls,expected", [
    (NoBirthChecks, {"S20", "S21", "S22", "S23", "S24", "S25", "S30", "S31", "S32", "S33"}),
    (NoInvokeChecks, {"S40", "S41"}),
    (NoMutateChecks, {"S10", "S11", "S12", "S13", "S14", "S15"}),
])
def test_verifier_catches_weakened_runtime(tmp_path, cls, expected):
    path, _ = run(tmp_path, "C", monitor_cls=cls)
    flagged = {v["scenario"] for v in verify(path)["violations"]}
    assert expected <= flagged
    assert not flagged & set(CONTROLS)


# --- Evidence log tampering (F5) -------------------------------------------------------
def _lines(runs):
    return runs["C"][0].read_bytes().splitlines()


def test_tamper_flip_byte_detected(runs):
    lines = _lines(runs)
    lines[5] = lines[5].replace(b'"decision":"block"', b'"decision":"allow"', 1) \
        if b'"decision":"block"' in lines[5] else lines[5][:-2] + b"0}"
    rep = Verifier(GENESIS, PUB, FIXTURES).run(lines)
    assert rep["integrity_failures"]


def test_tamper_delete_middle_entry_detected(runs):
    lines = _lines(runs)
    del lines[10]
    assert Verifier(GENESIS, PUB, FIXTURES).run(lines)["integrity_failures"]


def test_tamper_reorder_detected(runs):
    lines = _lines(runs)
    lines[3], lines[4] = lines[4], lines[3]
    assert Verifier(GENESIS, PUB, FIXTURES).run(lines)["integrity_failures"]


def test_finding_TC04_tail_truncation_not_detected(runs):
    """Documents finding TC-04: dropping the tail of the log verifies cleanly."""
    lines = _lines(runs)
    rep = Verifier(GENESIS, PUB, FIXTURES).run(lines[: len(lines) // 2])
    assert rep["ok"]


def test_finding_TC05_public_test_key_allows_forgery(runs, tmp_path):
    """Documents finding TC-05: anyone holding the committed test key writes a valid log."""
    path = tmp_path / "forged.jsonl"
    log = EvidenceLog(path, KEY)
    m = Monitor(GENESIS, "C", log, "FORGED", "forged")
    log.append({"op": "request", "run": "forged", "config": "C", "scenario": "FORGED", "step": 0,
                "actor": "a0", "claimed": None, "request": {"op": "invoke", "action": "read",
                "resource": "vault", "args": {"file": "ledger.txt"}}, "decision": "allow",
                "reason": "PERMITTED_0", "invariants": [], "state": m._state(), "vault": m._vault(),
                "model": None})
    log.close()
    assert verify(path)["ok"]


# --- Decision TC-02 (changelog 0.4.5): the core constrains birth and mutation -----------
def _without(rule_id):
    g = json.loads(json.dumps(GENESIS))
    g["root"]["core"] = [r for r in g["root"]["core"] if r["id"] != rule_id]
    return g


def test_TC02_absent_spawn_rule_denies_birth(tmp_path):
    """Explicit allow: a core with no spawn rule at all must deny birth, not only an explicit deny."""
    g = _without("K4")
    child = spawn([READ], [], core=g["root"]["core"])
    _, out = run(tmp_path, "C", scenarios=[("P1", "probe", "", "", "", [("P", child, True, "Q")])], genesis=g)
    assert (out["P1"][0]["decision"], out["P1"][0]["reason"]) == ("block", "CORE_FORBIDS")


def test_TC02_absent_mutate_rule_denies_mutation(tmp_path):
    g = _without("K5")
    _, out = run(tmp_path, "C", scenarios=[("P2", "probe", "", "", "", [("P", mutate("mut.x", 1), True, None)])],
                 genesis=g)
    assert (out["P2"][0]["decision"], out["P2"][0]["reason"]) == ("block", "CORE_FORBIDS")


def test_policy0_rejects_other_semantics(tmp_path):
    g = dict(GENESIS, policy_0="deny_overrides")
    _, out = run(tmp_path, "C", scenarios=[("P3", "probe", "", "", "", [("P", {"op": "invoke", "action": "read",
                 "resource": "vault", "args": {"file": "ledger.txt"}}, True, None)])], genesis=g)
    assert out["P3"][0]["decision"] == "block"  # fails closed, never silently permissive


# --- Fixtures cannot be chosen by the log ----------------------------------------------
def _relabel(lines, scenario, fixture):
    from dna.model import canon
    out = []
    for line in lines:
        e = json.loads(line)
        if e.get("op") == "genesis" and e.get("scenario") == scenario:
            e["fixture"] = fixture
            body = {k: v for k, v in e.items() if k != "sig"}
            e["sig"] = KEY.sign(canon(body)).hex()
            line = canon(e)
        out.append(line)
    return out


def test_verifier_rejects_unknown_fixture(runs):
    lines = _relabel(_lines(runs), "S00", "everything_allowed")
    rep = Verifier(GENESIS, PUB, FIXTURES).run(lines)
    assert any(v["invariant"] == "GENESIS" for v in rep["violations"])


def test_verifier_rejects_fixture_outside_its_scenario(runs):
    lines = _relabel(_lines(runs), "S00", "spawn_denied")
    rep = Verifier(GENESIS, PUB, FIXTURES).run(lines)
    assert any("outside its scenarios" in v["detail"] for v in rep["violations"])


# --- Regressions for defects found in review (stage1-findings.md TC-08, TC-09) ----------
def test_TC08_blocked_spawn_leaves_no_registered_child(tmp_path):
    """A spawn with valid DNA but an invalid program must not register the child."""
    path = tmp_path / "tc08.jsonl"
    log = EvidenceLog(path, KEY)
    m = Monitor(GENESIS, "C", log, "TC08", "t")
    req = spawn([READ], [], core=CORE)  # explicit core: the request must be otherwise valid
    req["program"] = "not-a-list"
    out = m.run([req], ["a0"])
    log.close()
    assert out[0]["decision"] == "block" and out[0]["reason"] == "MALFORMED"
    assert sorted(m.registry) == ["a0"]
    assert verify(path)["ok"]


def test_TC08_internal_error_fails_closed_and_rolls_back(tmp_path):
    """An unexpected exception inside R is blocked as INTERNAL_ERROR with state unchanged."""
    class Faulty(Monitor):
        def _perform(self, a, req):
            self.vault["ledger.txt"] = "partially written"
            raise RuntimeError("simulated defect")
    path = tmp_path / "tc08b.jsonl"
    log = EvidenceLog(path, KEY)
    m = Faulty(GENESIS, "C", log, "TC08b", "t")
    out = m.run([{"op": "invoke", "action": "write", "resource": "vault",
                  "args": {"file": "ledger.txt", "data": "x"}}], ["a0"])
    log.close()
    assert (out[0]["decision"], out[0]["reason"]) == ("block", "INTERNAL_ERROR")
    assert m.vault == GENESIS["vault"]
    assert verify(path)["ok"]


def test_TC09_verifier_reports_log_without_genesis(runs):
    lines = _lines(runs)[1:]
    rep = Verifier(GENESIS, PUB, FIXTURES).run(lines)
    assert not rep["ok"] and any("before any genesis" in x["detail"] for x in rep["integrity_failures"])


def test_TC23_verifier_uses_channel_identity_in_C(tmp_path):
    """An allowed request carrying a claimed identity is executed as the channel in C;
    the verifier must replay it the same way and accept the log (finding TC-23)."""
    req = {"op": "invoke", "action": "write", "resource": "vault",
           "args": {"file": "ledger.txt", "data": "x"}, "as": "a1"}
    _, out = run(tmp_path, "C", scenarios=[("TC23", "probe", "", "", "", [("P", SPAWN_Q, False, "Q"),
                                                                          ("P", req, True, None)])],
                 name="tc22")
    assert out["TC23"][0]["decision"] == "allow"
    assert verify(tmp_path / "tc22-C.jsonl")["ok"]
