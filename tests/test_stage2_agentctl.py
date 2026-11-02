"""fitrah-agentctl refusal paths (TC-21). Unprivileged; no cgroup or root needed.
The live launch/terminate path is exercised by src/stage2/s65.py inside the Stage 2 VM.
"""
from __future__ import annotations

import json
import os
import socket
import stat

import pytest

from stage2 import agentctl
from stage2.agentctl import Helper, Refused, load_config, parse_request, secure_file

CFG = {"programs": {"s65": ["/usr/bin/python3", "-I", "/srv/fitrah/agents/s65_descendants.py"]}}


def req(**kw) -> bytes:
    return json.dumps(kw).encode()


def test_valid_requests_parse():
    assert parse_request(req(op="launch", agent_id="s65-1", program="s65"), CFG)["program"] == "s65"
    assert parse_request(req(op="terminate", agent_id="a1"), CFG)["op"] == "terminate"
    assert parse_request(req(op="census", agent_id="a1"), CFG)["op"] == "census"


@pytest.mark.parametrize("raw, why", [
    (b"not json", "malformed JSON"),
    (b"\xff\xfe", "malformed JSON"),
    (b"[1, 2]", "unknown op"),
    (req(op="shell", agent_id="a1"), "unknown op"),
    (req(agent_id="a1"), "unknown op"),
    (req(op="launch", agent_id="a1", program="/bin/sh"), "program not in allowlist"),
    (req(op="launch", agent_id="a1", program=["s65"]), "program not in allowlist"),
    (req(op="launch", agent_id="a1"), "fields must be exactly"),
    (req(op="launch", agent_id="a1", program="s65", argv=["-c", "id"]), "fields must be exactly"),
    (req(op="launch", agent_id="a1", program="s65", env={"LD_PRELOAD": "x"}), "fields must be exactly"),
    (req(op="terminate", agent_id="a1", path="/sys/fs/cgroup"), "fields must be exactly"),
    (req(op="terminate", agent_id="../agents"), "bad agent_id"),
    (req(op="terminate", agent_id="A1"), "bad agent_id"),
    (req(op="terminate", agent_id=""), "bad agent_id"),
    (req(op="terminate", agent_id="a" * 33), "bad agent_id"),
    (req(op="terminate", agent_id="a1\n"), "bad agent_id"),
    (req(op="terminate", agent_id=7), "bad agent_id"),
    (b"{" + b" " * 5000 + b"}", "request too large"),
])
def test_refusals(raw, why):
    with pytest.raises(Refused, match=why):
        parse_request(raw, CFG)


def test_allowlist_file_must_be_root_owned(tmp_path):
    p = tmp_path / "agentctl.json"
    p.write_text(json.dumps(CFG))
    if os.geteuid() != 0:
        with pytest.raises(Refused, match="not root-owned"):
            load_config(str(p))
    else:
        os.chmod(p, 0o666)
        with pytest.raises(Refused, match="writable by others"):
            secure_file(str(p))


def test_allowlist_rejects_bad_entries(tmp_path):
    p = tmp_path / "agentctl.json"
    for programs in ({"S65": ["/x"]}, {"s65": []}, {"s65": ["/x", 3]}):
        p.write_text(json.dumps({"programs": programs}))
        with pytest.raises(Refused, match="bad allowlist entry"):
            load_config(str(p), check_owner=False)


def fake_helper(tmp_path, monkeypatch, uid=4242):
    class Pw:
        def __init__(self, n, u):
            self.pw_name, self.pw_uid, self.pw_gid, self.pw_dir = n, u, u, "/"
    users = {"rt": Pw("rt", uid), "ag": Pw("ag", uid + 1)}
    monkeypatch.setattr(agentctl.pwd, "getpwnam", lambda n: users[n])
    root = tmp_path / "cg"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "cgroup.procs").write_text("")
    return Helper({"runtime_user": "rt", "agent_user": "ag", "max_agents": 2, **CFG}, root)


def test_root_identities_refused(tmp_path, monkeypatch):
    class Pw:
        pw_uid = pw_gid = 0
        pw_dir = "/"
    monkeypatch.setattr(agentctl.pwd, "getpwnam", lambda n: Pw())
    with pytest.raises(Refused, match="non-root"):
        Helper({"runtime_user": "root", "agent_user": "root", **CFG}, tmp_path)


def test_existing_and_missing_cgroups_refused(tmp_path, monkeypatch):
    h = fake_helper(tmp_path, monkeypatch)
    (h.agents / "a1").mkdir()
    with pytest.raises(Refused, match="already exists"):
        h.launch("a1", "s65")
    with pytest.raises(Refused, match="no such agent"):
        h.terminate("a2")
    with pytest.raises(Refused, match="no such agent"):
        h.census("a2")


def test_agent_limit_and_missing_cgroup_kill(tmp_path, monkeypatch):
    h = fake_helper(tmp_path, monkeypatch)
    with pytest.raises(Refused, match="cgroup.kill"):
        h.launch("a1", "s65")
    (h.agents / "x1").mkdir()
    (h.agents / "x2").mkdir()
    with pytest.raises(Refused, match="too many agents"):
        h.launch("a1", "s65")


def test_wrong_peer_uid_refused_and_no_fds_sent(tmp_path, monkeypatch):
    h = fake_helper(tmp_path, monkeypatch, uid=os.getuid() + 1)
    a, b = socket.socketpair()
    b.sendall(req(op="census", agent_id="a1") + b"\n")
    h.handle(a)
    msg, fds, _, _ = socket.recv_fds(b, 4096, 2)
    assert fds == []
    assert json.loads(msg) == {"ok": False, "error": f"peer uid {os.getuid()} is not the runtime user"}


def test_handle_refuses_bad_request_from_runtime_user(tmp_path, monkeypatch):
    h = fake_helper(tmp_path, monkeypatch)
    h.runtime_uid = os.getuid()  # the test process plays the runtime user
    a, b = socket.socketpair()
    b.sendall(req(op="launch", agent_id="a1", program="/bin/sh") + b"\n")
    h.handle(a)
    msg, fds, _, _ = socket.recv_fds(b, 4096, 2)
    assert fds == [] and json.loads(msg)["error"] == "program not in allowlist"


def test_census_reads_cgroup(tmp_path, monkeypatch):
    h = fake_helper(tmp_path, monkeypatch)
    (h.agents / "a1").mkdir()
    (h.agents / "a1" / "cgroup.procs").write_text("10\n11\n")
    assert h.census("a1") == {"ok": True, "pids": [10, 11]}


def test_helper_source_is_small():
    lines = open(agentctl.__file__).read().splitlines()
    assert len(lines) < 240 and not any(l.startswith(("import subprocess", "from subprocess")) for l in lines)
    assert stat.S_ISREG(os.stat(agentctl.__file__).st_mode)
