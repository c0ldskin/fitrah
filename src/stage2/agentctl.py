"""fitrah-agentctl: the Stage 2 privileged helper (TC-21 revision 2). Part of the TCB.

Runs as root under systemd (Delegate=yes), so it owns a root-only cgroup subtree.
Serves exactly three requests from the runtime user, one JSON line per connection:
  {"op": "launch", "agent_id": ID, "program": NAME}   -> pid, plus the agent's stdin/stdout via SCM_RIGHTS
  {"op": "terminate", "agent_id": ID}                -> cgroup.kill, wait empty, rmdir, count killed
  {"op": "census", "agent_id": ID}                   -> pids in the agent's cgroup
Programs come only from the root-owned allowlist. R never supplies a path, argv or environment.
Standard library only.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import signal
import socket
import stat
import sys
import time
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")
MAX_REQUEST = 4096
KEYS = {"launch": {"op", "agent_id", "program"}, "terminate": {"op", "agent_id"}, "census": {"op", "agent_id"}}


class Refused(Exception):
    pass


def log(event: str, **kw) -> None:
    print(json.dumps({"event": event, **kw}, sort_keys=True), file=sys.stderr, flush=True)


def secure_file(path: str) -> None:
    """Root-owned and writable by nobody else, for the file and every parent directory."""
    p = Path(path)
    for q in [p, *p.parents]:
        st = q.stat()
        if st.st_uid != 0 or st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise Refused(f"not root-owned or writable by others: {q}")


def load_config(path: str, check_owner: bool = True) -> dict:
    if check_owner:
        secure_file(path)
    cfg = json.loads(Path(path).read_text())
    for name, argv in cfg["programs"].items():
        if not ID_RE.fullmatch(name) or not argv or not all(isinstance(a, str) for a in argv):
            raise Refused(f"bad allowlist entry {name!r}")
        if check_owner:
            for a in argv:
                if a.startswith("/"):
                    secure_file(a)
    return cfg


def parse_request(raw: bytes, cfg: dict) -> dict:
    """Validate one request line. Every refusal path raises Refused."""
    if len(raw) > MAX_REQUEST:
        raise Refused("request too large")
    try:
        req = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise Refused("malformed JSON") from None
    if not isinstance(req, dict) or req.get("op") not in KEYS:
        raise Refused("unknown op")
    if set(req) != KEYS[req["op"]]:
        raise Refused(f"fields must be exactly {sorted(KEYS[req['op']])}")
    if not isinstance(req["agent_id"], str) or not ID_RE.fullmatch(req["agent_id"]):
        raise Refused("bad agent_id")
    if req["op"] == "launch" and (not isinstance(req["program"], str) or req["program"] not in cfg["programs"]):
        raise Refused("program not in allowlist")
    return req


def read_procs(cg: Path) -> list[int]:
    return [int(x) for x in (cg / "cgroup.procs").read_text().split()]


class Helper:
    def __init__(self, cfg: dict, root: Path):
        self.cfg, self.root = cfg, root
        self.agents = root / "agents"
        self.runtime_uid = pwd.getpwnam(cfg["runtime_user"]).pw_uid
        self.agent = pwd.getpwnam(cfg["agent_user"])
        if self.agent.pw_uid == 0 or self.runtime_uid == 0:
            raise Refused("runtime and agent users must be non-root")

    def setup(self) -> None:
        """Move the helper into supervisor/ (no-internal-process rule) and create agents/."""
        for d in (self.root / "supervisor", self.agents):
            d.mkdir(mode=0o755, exist_ok=True)
        (self.root / "supervisor" / "cgroup.procs").write_text(str(os.getpid()))
        if not (self.agents / "cgroup.procs").exists():
            raise Refused("agents cgroup missing")

    def cgroup(self, agent_id: str, exists: bool) -> Path:
        cg = self.agents / agent_id
        if cg.exists() != exists:
            raise Refused("agent cgroup already exists" if cg.exists() else "no such agent")
        return cg

    def launch(self, agent_id: str, program: str) -> tuple[dict, list[int]]:
        if len([p for p in self.agents.iterdir() if p.is_dir()]) >= self.cfg.get("max_agents", 32):
            raise Refused("too many agents")
        cg = self.cgroup(agent_id, exists=False)
        if not (self.agents / "cgroup.kill").exists():
            raise Refused("kernel lacks cgroup.kill")
        cg.mkdir(mode=0o755)
        argv = [a.replace("{agent_id}", agent_id) for a in self.cfg["programs"][program]]
        in_r, in_w = os.pipe()
        out_r, out_w = os.pipe()
        pid = os.fork()
        if pid == 0:  # child: enter the cgroup while still root, then drop to the agent user and exec
            try:
                (cg / "cgroup.procs").write_text(str(os.getpid()))
                os.dup2(in_r, 0)
                os.dup2(out_w, 1)
                null = os.open(os.devnull, os.O_WRONLY)
                os.dup2(null, 2)
                os.closerange(3, os.sysconf("SC_OPEN_MAX"))
                os.setgroups([])
                os.setgid(self.agent.pw_gid)
                os.setuid(self.agent.pw_uid)
                if os.getuid() != self.agent.pw_uid or os.geteuid() != self.agent.pw_uid:
                    os._exit(126)
                os.chdir(self.agent.pw_dir)
                signal.signal(signal.SIGCHLD, signal.SIG_DFL)
                env = {"PATH": "/usr/bin:/bin", "HOME": self.agent.pw_dir, "LANG": "C.UTF-8"}
                os.execve(argv[0], argv, env)
            finally:
                os._exit(127)
        os.close(in_r)
        os.close(out_w)
        log("launch", agent_id=agent_id, program=program, pid=pid)
        return {"ok": True, "pid": pid}, [in_w, out_r]

    def terminate(self, agent_id: str) -> dict:
        cg = self.cgroup(agent_id, exists=True)
        before = read_procs(cg)
        (cg / "cgroup.kill").write_text("1")
        deadline = time.monotonic() + self.cfg.get("terminate_timeout_s", 5)
        while read_procs(cg):
            if time.monotonic() > deadline:
                log("terminate_timeout", agent_id=agent_id, left=read_procs(cg))
                return {"ok": False, "error": "cgroup not empty after kill", "left": read_procs(cg)}
            time.sleep(0.01)
        cg.rmdir()
        log("terminate", agent_id=agent_id, killed=len(before))
        return {"ok": True, "killed": len(before), "pids": before, "procs_after": []}

    def census(self, agent_id: str) -> dict:
        return {"ok": True, "pids": read_procs(self.cgroup(agent_id, exists=True))}

    def handle(self, conn: socket.socket) -> None:
        fds: list[int] = []
        try:
            uid = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            peer_uid = int.from_bytes(uid[4:8], sys.byteorder)
            if peer_uid != self.runtime_uid:
                raise Refused(f"peer uid {peer_uid} is not the runtime user")
            conn.settimeout(5)
            raw = b""
            while not raw.endswith(b"\n") and len(raw) <= MAX_REQUEST:
                chunk = conn.recv(MAX_REQUEST + 1)
                if not chunk:
                    break
                raw += chunk
            req = parse_request(raw.strip(), self.cfg)
            if req["op"] == "launch":
                reply, fds = self.launch(req["agent_id"], req["program"])
            else:
                reply = getattr(self, req["op"])(req["agent_id"])
        except Refused as e:
            reply = {"ok": False, "error": str(e)}
            log("refused", reason=str(e))
        except (OSError, ValueError) as e:
            reply = {"ok": False, "error": f"helper error: {type(e).__name__}"}
            log("error", detail=repr(e))
        try:
            socket.send_fds(conn, [json.dumps(reply).encode() + b"\n"], fds)
        except OSError:
            pass
        finally:
            for fd in fds:
                os.close(fd)
            conn.close()


def cgroup2_mount() -> str:
    for line in open("/proc/self/mounts"):
        f = line.split()
        if f[2] == "cgroup2":
            return f[1]
    return "/sys/fs/cgroup"


def own_cgroup() -> Path:
    line = [x for x in Path("/proc/self/cgroup").read_text().splitlines() if x.startswith("0::")][0]
    return Path(cgroup2_mount()) / line[3:].lstrip("/")


def main() -> int:
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "/etc/fitrah/agentctl.json"
    cfg = load_config(cfg_path)
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)  # the kernel reaps agents; no zombies
    root = Path(cfg["cgroup_root"]) if cfg.get("cgroup_root") else own_cgroup()
    helper = Helper(cfg, root)
    helper.setup()
    if os.environ.get("LISTEN_PID") == str(os.getpid()) and os.environ.get("LISTEN_FDS") == "1":
        srv = socket.socket(fileno=3)  # systemd socket activation
    else:
        path = cfg["socket"]
        if os.path.exists(path):
            os.unlink(path)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        os.chown(path, helper.runtime_uid, -1)
        os.chmod(path, 0o600)
        srv.listen(8)
    log("ready", cgroup_root=str(root))
    while True:
        conn, _ = srv.accept()
        helper.handle(conn)


if __name__ == "__main__":
    sys.exit(main())
