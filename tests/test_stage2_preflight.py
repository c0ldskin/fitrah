"""Stage 2 preflight logic (read-only). Run:  PYTHONPATH=src python3 -m pytest -q

These tests exercise the decision logic only. They create temporary files under
pytest's tmp_path, never change users, groups or system settings, and never
contact the network (the probe's connect is injected).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from stage2 import agent_probe, preflight
from stage2.preflight import Identity, agent_may, protected_path, run_checks, verdict

AGENT = Identity("fitrah-agent", 2002, (2002,), "/nonexistent-agent-home")
RUNTIME = Identity("fitrah-runtime", 2001, (2001,), "/nonexistent-runtime-home")
ROOT_ID = Identity("root", 0, (0,), "/root")


def st(mode, uid=2001, gid=2001):
    return os.stat_result((mode, 0, 0, 1, uid, gid, 0, 0, 0, 0))


@pytest.mark.parametrize("mode,uid,gid,want,expected", [
    (0o600, 2001, 2001, "r", False),   # other: no bits
    (0o604, 2001, 2001, "r", True),    # other read
    (0o602, 2001, 2001, "w", True),    # other write
    (0o640, 2001, 2002, "r", True),    # agent's group may read
    (0o620, 2001, 2002, "w", True),    # agent's group may write
    (0o400, 2002, 2002, "r", True),    # agent owns it
    (0o066, 2002, 2002, "r", False),   # owner bits apply to owner, even if group/other allow
])
def test_agent_may_mode_bits(mode, uid, gid, want, expected):
    assert agent_may(st(mode, uid, gid), AGENT, want) is expected


def test_root_agent_may_everything():
    assert agent_may(st(0o000), ROOT_ID, "r") and agent_may(st(0o000), ROOT_ID, "w")


def test_protected_path(tmp_path):
    d = tmp_path / "rt"
    d.mkdir()
    os.chmod(d, 0o755)
    f = d / "key"
    f.write_text("k")
    os.chmod(f, 0o600)
    assert protected_path(str(f), AGENT, "rw")[0] == "PASS"
    os.chmod(f, 0o644)
    status, detail = protected_path(str(f), AGENT, "rw")
    assert status == "FAIL" and "may read" in detail
    os.chmod(f, 0o600)
    os.chmod(d, 0o777)
    status, detail = protected_path(str(f), AGENT, "rw")
    assert status == "FAIL" and "could replace" in detail
    assert protected_path(str(d / "missing"), AGENT, "r")[0] == "FAIL"


def test_protected_directory_checks_contents(tmp_path):
    d = tmp_path / "vault"
    d.mkdir()
    os.chmod(d, 0o700)
    (d / "ledger.txt").write_text("x")
    os.chmod(d / "ledger.txt", 0o606)
    status, detail = protected_path(str(d), AGENT, "rw")
    assert status == "FAIL" and "ledger.txt" in detail


def _cfg(tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / "seed").write_text("00" * 32)
    (keys / "pub").write_text("ab" * 32 + "\n")
    for n in ("logs", "vault", "src"):
        (tmp_path / n).mkdir()
    (tmp_path / "registry.json").write_text("{}")
    return {"runtime_user": "fitrah-runtime", "agent_user": "fitrah-agent",
            "signing_key": str(keys / "seed"), "public_key": str(keys / "pub"),
            "log_dir": str(tmp_path / "logs"), "registry": str(tmp_path / "registry.json"),
            "vault_dir": str(tmp_path / "vault"), "source_dir": str(tmp_path / "src")}


def _lookup(table):
    return lambda name: table.get(name)


def by_id(checks):
    return {c.id: c for c in checks}


def test_identity_checks(tmp_path):
    cfg = _cfg(tmp_path)
    ok = by_id(run_checks(cfg, euid=2001, env={}, run_regression=False,
                          lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": AGENT})))
    assert ok["P01"].status == "PASS" and ok["P02"].status == "PASS"
    same = Identity("fitrah-agent", 2001, (2001,), "/x")
    bad = by_id(run_checks(cfg, euid=2001, env={}, run_regression=False,
                           lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": same})))
    assert bad["P01"].status == "FAIL"
    shared = Identity("fitrah-agent", 2002, (2001, 2002), "/x")
    bad = by_id(run_checks(cfg, euid=2001, env={}, run_regression=False,
                           lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": shared})))
    assert bad["P01"].status == "FAIL" and "share group" in bad["P01"].detail
    as_root = by_id(run_checks(cfg, euid=0, env={}, run_regression=False,
                               lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": AGENT})))
    assert as_root["P02"].status == "FAIL"
    missing = by_id(run_checks(cfg, euid=2001, env={}, run_regression=False, lookup_fn=_lookup({})))
    assert missing["P01"].status == "FAIL"


def test_committed_test_key_is_rejected(tmp_path):
    cfg = _cfg(tmp_path)
    Path(cfg["public_key"]).write_text(preflight.COMMITTED_TEST_PUB.read_text())
    c = by_id(run_checks(cfg, euid=2001, env={}, run_regression=False,
                         lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": AGENT})))
    assert c["P03"].status == "FAIL" and "TC-05" in c["P03"].detail


def test_ssh_agent_is_a_host_leak(tmp_path):
    c = by_id(run_checks(_cfg(tmp_path), euid=2001, env={"SSH_AUTH_SOCK": "/tmp/agent.sock"},
                         run_regression=False,
                         lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": AGENT})))
    assert c["P05"].status == "FAIL"


def test_dynamic_checks_are_never_assumed():
    """Without the agent-side probe and containment test, the verdict cannot be READY."""
    from stage2.preflight import Check
    static_pass = [Check(f"P0{i}", "", "PASS", "") for i in range(1, 6)]
    assert verdict(static_pass) == "READY"
    assert verdict(static_pass + [Check("P06", "", "NOT_EVALUATED", "")]) == "ENVIRONMENT_INVALID"
    assert verdict([]) == "ENVIRONMENT_INVALID"


def test_probe_reports_accessible_and_missing_paths_as_fail(tmp_path):
    f = tmp_path / "readable"
    f.write_text("x")
    assert agent_probe.try_open(str(f), write=False) == "ALLOWED"
    assert agent_probe.try_open(str(tmp_path / "absent"), write=False) == "MISSING"
    cfg = {"signing_key": str(f), "log_file": str(f), "registry": str(f), "vault_file": str(f),
           "network_probe": ["192.0.2.1", 443]}
    rep = agent_probe.probe(cfg, connect=lambda: None)
    assert rep["verdict"] == "FAIL" and all(c["status"] == "FAIL" for c in rep["checks"])
    assert f.read_text() == "x"  # opened for write, never written


def test_probe_network_outcomes_injected():
    def refuse():
        raise OSError("no route")
    assert agent_probe.try_connect("192.0.2.1", 443, 0.1, connect=refuse) == "DENIED"
    assert agent_probe.try_connect("192.0.2.1", 443, 0.1, connect=lambda: None) == "ALLOWED"


def _probe(uid, net="DENIED", files="DENIED", n_files=6):
    checks = [{"check": f"file {i}", "outcome": files, "status": "PASS" if files == "DENIED" else "FAIL"}
              for i in range(n_files)]
    checks.append({"check": "external network", "target": "1.1.1.1:443", "outcome": net,
                   "status": "PASS" if net == "DENIED" else "FAIL"})
    return {"uid": uid, "euid": uid, "checks": checks}


def test_probe_report_is_authoritative_for_p06_p07(tmp_path):
    cfg = _cfg(tmp_path)
    run = lambda probe: by_id(run_checks(cfg, euid=2001, env={}, run_regression=False, probe=probe,
                                         lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": AGENT})))
    ok = run(_probe(AGENT.uid))
    assert ok["P06"].status == "PASS" and ok["P07"].status == "PASS"
    assert run(None)["P06"].status == "NOT_EVALUATED" and run(None)["P07"].status == "NOT_EVALUATED"
    wrong_uid = run(_probe(RUNTIME.uid))
    assert wrong_uid["P06"].status == "FAIL" and wrong_uid["P07"].status == "FAIL"
    assert run(_probe(AGENT.uid, net="ALLOWED"))["P06"].status == "FAIL"
    assert run(_probe(AGENT.uid, files="ALLOWED"))["P07"].status == "FAIL"
    assert run(_probe(AGENT.uid, n_files=3))["P07"].status == "FAIL"


def test_p03_reports_sha256_of_public_key_bytes(tmp_path):
    import hashlib
    cfg = _cfg(tmp_path)
    pub_hex = Path(cfg["public_key"]).read_text().split()[0]
    c = by_id(run_checks(cfg, euid=2001, env={}, run_regression=False,
                         lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": AGENT})))
    if c["P03"].status == "PASS":
        assert c["P03"].detail == "sha256 " + hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()
    assert preflight.public_key_fingerprint("00" * 32) == hashlib.sha256(bytes(32)).hexdigest()


def _s65(uid, status="PASS", cases=("fork", "double_fork", "setsid", "setpgid"), survivors=()):
    return {"scenario": "S65", "status": status, "control": {"survivors_of_killpg": ["setpgid", "setsid"]},
            "contained": {"cases": list(cases), "all_run_as_agent_uid": True, "census_covers_all": True,
                          "escape_denied": True, "terminate": {"ok": True, "killed": 5},
                          "oracle_cgroup": {"pass": not survivors, "procs": list(survivors)},
                          "oracle_uid": {"agent_uid": uid, "pass": not survivors, "processes": list(survivors)}}}


def test_p08_comes_from_the_s65_report(tmp_path):
    cfg = _cfg(tmp_path)
    run = lambda s65: by_id(run_checks(cfg, euid=2001, env={}, run_regression=False, s65=s65,
                                       lookup_fn=_lookup({"fitrah-runtime": RUNTIME, "fitrah-agent": AGENT})))["P08"]
    assert run(None).status == "NOT_EVALUATED"
    assert run(_s65(AGENT.uid)).status == "PASS"
    assert run(_s65(AGENT.uid, status="FAIL")).status == "FAIL"
    assert run(_s65(RUNTIME.uid)).status == "FAIL"
    assert run(_s65(AGENT.uid, cases=("fork",))).status == "FAIL"
    assert run(_s65(AGENT.uid, survivors=(1234,))).status == "FAIL"
