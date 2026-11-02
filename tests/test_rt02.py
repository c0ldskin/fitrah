"""RT-02: bounded requests. Run from the repository root:  PYTHONPATH=src python3 -m pytest -q

Each test runs a normal root agent P and substitutes one scripted test double
for a single agent. R must terminate the misbehaving agent within the bound,
fail closed, keep RT-01 (no partial state), write evidence, and keep serving
the other agents.
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import pytest

from runtime.evidence import EvidenceLog, load_signing_key
from runtime.monitor import Monitor
from simulator.scenarios import CORE, READ, SPAWN_Q, build, spawn
from simulator.verify import Verifier

LAB = Path(__file__).resolve().parents[1] / "experiments" / "lab0"
GENESIS = json.loads((LAB / "genesis.json").read_text())
FIXTURES = json.loads((LAB / "fixtures.json").read_text())
PUB = (LAB / "keys" / "test-signing.pub").read_text().split()[0]
KEY = load_signing_key(LAB / "keys" / "test-signing.seed")
DOUBLE = Path(__file__).resolve().parent / "doubles" / "misbehaving_agent.py"
BOUND_MS = 300


def genesis(bound=BOUND_MS):
    g = copy.deepcopy(GENESIS)
    g["rt02_request_timeout_ms"] = bound
    return g


class WithDouble(Monitor):
    """Agent `target` runs the test double in `mode`; everyone else is a normal scripted agent."""
    target, mode = "a1", "stall"

    def _argv_for(self, agent_id):
        if agent_id == self.target:
            return [sys.executable, "-I", str(DOUBLE), self.mode]
        return super()._argv_for(agent_id)


def run(tmp_path, steps, mode, target="a1", bound=BOUND_MS):
    g = genesis(bound)
    cls = type("M", (WithDouble,), {"mode": mode, "target": target})
    path = tmp_path / f"rt02-{mode}-{target}.jsonl"
    log = EvidenceLog(path, KEY)
    m = cls(g, "C", log, "RT02", "rt02")
    program, schedule, _, _ = build(steps)
    t0 = time.monotonic()
    out = m.run(program, schedule)
    elapsed = time.monotonic() - t0
    log.close()
    rep = Verifier(g, PUB, FIXTURES).run(path.read_bytes().splitlines())
    entries = [json.loads(x) for x in path.read_bytes().splitlines()]
    return m, out, rep, entries, elapsed


READ_REQ = {"op": "invoke", "action": "read", "resource": "vault", "args": {"file": "ledger.txt"}}
# P spawns Q (a1, the double); Q is prompted; then P must still be served
STEPS = [("P", SPAWN_Q, False, "Q"), ("Q", READ_REQ, True, None), ("P", READ_REQ, True, None)]


@pytest.mark.parametrize("mode,kind", [("stall", "TIMEOUT"), ("partial", "TIMEOUT"),
                                       ("flood", "OVERSIZE"), ("exit", "EOF")])
def test_misbehaving_child_is_terminated_and_others_proceed(tmp_path, mode, kind):
    m, out, rep, entries, elapsed = run(tmp_path, STEPS, mode)
    assert out[0]["decision"] == "allow"                                   # birth of Q
    assert (out[1]["decision"], out[1]["reason"]) == ("block", f"CHANNEL_{kind}")
    assert (out[2]["decision"], out[2]["reason"]) == ("allow", "PERMITTED_0")  # R not stalled
    assert m.registry["a1"]["status"] == "dead"                            # fail closed
    assert m.vault == GENESIS["vault"]                                     # RT-01: no partial effect
    failures = [e for e in entries if e["op"] == "channel_failure"]
    assert len(failures) == 1 and failures[0]["actor"] == "a1" and failures[0]["phase"] == "request"
    assert rep["ok"], rep                                                  # evidence replays
    assert elapsed < 5                                                     # bounded, not the double's 30 s


def test_later_steps_of_terminated_agent_are_skipped(tmp_path):
    steps = STEPS + [("Q", READ_REQ, True, None)]
    _, out, rep, _, _ = run(tmp_path, steps, "stall")
    assert (out[3]["decision"], out[3]["reason"]) == ("skipped", "ACTOR_TERMINATED")
    assert rep["ok"]


def test_deaf_root_with_large_program_fails_at_launch(tmp_path):
    """A full pipe must not block R's write: the bound applies to sends as well as reads."""
    big = [dict(READ_REQ, args={"file": "ledger.txt", "data": "x" * 1024}) for _ in range(2048)]  # > 2 MiB
    g = genesis()
    cls = type("M", (WithDouble,), {"mode": "deaf", "target": "a0"})
    path = tmp_path / "deaf.jsonl"
    log = EvidenceLog(path, KEY)
    m = cls(g, "C", log, "RT02", "rt02")
    t0 = time.monotonic()
    out = m.run(big, ["a0"])
    elapsed = time.monotonic() - t0
    log.close()
    entries = [json.loads(x) for x in path.read_bytes().splitlines()]
    assert out[0]["reason"] == "ACTOR_TERMINATED"
    assert [e["phase"] for e in entries if e["op"] == "channel_failure"] == ["launch"]
    assert m.registry["a0"]["status"] == "dead"
    assert Verifier(g, PUB, FIXTURES).run(path.read_bytes().splitlines())["ok"]
    assert elapsed < 5


def test_child_launch_failure_rolls_back_birth(tmp_path):
    """RT-01 with RT-02: if the child cannot receive its program in time, no child is registered."""
    child = spawn([READ], [], core=CORE)
    # ~200 KiB: larger than a pipe buffer (64 KiB on Linux) but under R's 1 MiB request-line bound,
    # because the child's program travels inside the parent's spawn request
    child["program"] = [dict(READ_REQ, args={"file": "ledger.txt", "data": "x" * 1024}) for _ in range(200)]
    g = genesis()
    cls = type("M", (WithDouble,), {"mode": "deaf", "target": "a1"})
    path = tmp_path / "launch.jsonl"
    log = EvidenceLog(path, KEY)
    m = cls(g, "C", log, "RT02", "rt02")
    out = m.run([child, READ_REQ], ["a0", "a0"])
    log.close()
    assert (out[0]["decision"], out[0]["reason"]) == ("block", "CHILD_LAUNCH_FAILED")
    assert sorted(m.registry) == ["a0"] and "a1" not in m.procs
    assert (out[1]["decision"], out[1]["reason"]) == ("allow", "PERMITTED_0")
    assert Verifier(g, PUB, FIXTURES).run(path.read_bytes().splitlines())["ok"]


def test_no_agent_process_survives_a_run(tmp_path):
    procs = []

    class Track(WithDouble):
        mode, target = "stall", "a1"

        def _launch(self, agent_id, program):
            super()._launch(agent_id, program)
            procs.append(self.procs[agent_id].proc)

    g = genesis()
    path = tmp_path / "track.jsonl"
    log = EvidenceLog(path, KEY)
    program, schedule, _, _ = build(STEPS)
    Track(g, "C", log, "RT02", "rt02").run(program, schedule)
    log.close()
    assert procs and all(p.poll() is not None for p in procs)


def test_verifier_rejects_forged_channel_failure(tmp_path):
    """A channel_failure entry recorded against another bound, or not failing closed, is flagged."""
    from dna.model import canon
    _, _, _, entries, _ = run(tmp_path, STEPS, "stall")
    lines, prev = [], "0" * 64
    from dna.model import sha256_hex
    for e in entries:
        e = {k: v for k, v in e.items() if k not in ("sig", "prev")}
        if e["op"] == "channel_failure":
            e["bound_ms"] = 999999
        e["prev"] = prev
        body = dict(e)
        e["sig"] = KEY.sign(canon(body)).hex()
        line = canon(e)
        prev = sha256_hex(line)
        lines.append(line)
    rep = Verifier(genesis(), PUB, FIXTURES).run(lines)
    assert any(v["invariant"] == "RT-02" for v in rep["violations"])


def test_bound_in_log_must_match_genesis(tmp_path):
    _, _, _, _, _ = run(tmp_path, STEPS[:1], "stall")
    path = tmp_path / "rt02-stall-a1.jsonl"
    rep = Verifier(genesis(bound=BOUND_MS + 1), PUB, FIXTURES).run(path.read_bytes().splitlines())
    assert any("RT-02 bound" in v["detail"] for v in rep["violations"])


def test_agent_runs_in_its_own_process_group(tmp_path):
    """Termination targets the agent's process group, never R's own group."""
    import os
    groups = []

    class Track(WithDouble):
        mode, target = "stall", "a1"

        def _launch(self, agent_id, program):
            super()._launch(agent_id, program)
            p = self.procs[agent_id].proc
            groups.append((p.pid, os.getpgid(p.pid)))

    g = genesis()
    log = EvidenceLog(tmp_path / "pg.jsonl", KEY)
    program, schedule, _, _ = build(STEPS)
    Track(g, "C", log, "RT02", "rt02").run(program, schedule)
    log.close()
    assert groups and all(pid == pgid != os.getpgrp() for pid, pgid in groups)


# --- TC-19 (decision 0.4.9): dedicated response-phase regression -------------------------
class PaddedResponse(WithDouble):
    """Test-only R variant: pads its response beyond any pipe capacity (Linux max 1 MiB),
    so a response write to an agent that has stopped reading must block."""
    mode, target = "talk_deaf", "a0"
    PAD = 2 * 1024 * 1024

    def handle(self, channel, raw):
        return dict(super().handle(channel, raw), pad="x" * self.PAD)


def test_TC19_response_phase_timeout(tmp_path):
    g = genesis()
    path = tmp_path / "tc19.jsonl"
    log = EvidenceLog(path, KEY)
    m = PaddedResponse(g, "C", log, "TC19", "tc19")
    t0 = time.monotonic()
    out = m.run([], ["a0", "a0"])
    elapsed = time.monotonic() - t0
    log.close()
    entries = [json.loads(x) for x in path.read_bytes().splitlines()]
    requests = [e for e in entries if e["op"] == "request"]
    failures = [e for e in entries if e["op"] == "channel_failure"]
    # the request itself was authorised and committed before delivery failed (RT-01: no rollback
    # of a committed, logged decision; the failure is in delivery only)
    assert (out[0]["decision"], out[0]["reason"]) == ("allow", "PERMITTED_0")
    assert len(requests) == 1 and requests[0]["decision"] == "allow"
    assert m.vault["ledger.txt"].endswith("a0:tc19\n")
    # the response phase failed within the bound and failed closed
    assert [(f["phase"], f["kind"]) for f in failures] == [("response", "TIMEOUT")]
    assert m.registry["a0"]["status"] == "dead"
    assert out[1]["reason"] == "ACTOR_TERMINATED"
    assert elapsed < 5
    # the evidence replays: the committed write, then the R-initiated termination
    assert Verifier(g, PUB, FIXTURES).run(path.read_bytes().splitlines())["ok"]


def test_TC19_response_phase_leaves_no_survivor(tmp_path):
    procs = []

    class Track(PaddedResponse):
        def _launch(self, agent_id, program):
            super()._launch(agent_id, program)
            procs.append(self.procs[agent_id].proc)

    log = EvidenceLog(tmp_path / "tc19b.jsonl", KEY)
    Track(genesis(), "C", log, "TC19", "tc19").run([], ["a0"])
    log.close()
    assert procs and all(p.poll() is not None for p in procs)
