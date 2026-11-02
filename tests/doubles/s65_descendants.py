"""S65 scripted test double (TC-21). No LLM, no files, no network.

Spawns descendants that leave the agent's process group, then reports them on stdout:
  fork         plain child
  double_fork  grandchild after its parent exits (reparented away from the agent)
  setsid       double-forked grandchild that starts a new session
  setpgid      child of the setsid process that starts a new process group
Each descendant also tries to move itself out of its cgroup, and reports whether that was denied.
All survivors hold no channel and sleep for a bounded time, so the double ends by itself.
"""
import json
import os
import sys
import time

LIMIT = 120  # seconds; a bound on the double itself


def cgroup2_mount() -> str:
    for line in open("/proc/self/mounts"):
        f = line.split()
        if f[2] == "cgroup2":
            return f[1]
    return "/sys/fs/cgroup"


def cgroup_escape() -> str:
    line = [x for x in open("/proc/self/cgroup").read().splitlines() if x.startswith("0::")][0]
    mount = cgroup2_mount()
    own = mount + line[3:]
    outcomes = []
    for target in (os.path.dirname(own), mount):
        try:
            with open(os.path.join(target, "cgroup.procs"), "w") as f:
                f.write(str(os.getpid()))
            outcomes.append("MOVED")
        except OSError as e:
            outcomes.append(type(e).__name__)
    return ",".join(outcomes)


def survive(case: str, report: int) -> None:
    rec = {"case": case, "pid": os.getpid(), "sid": os.getsid(0), "pgid": os.getpgid(0),
           "uid": os.getuid(), "escape": cgroup_escape()}
    os.write(report, (json.dumps(rec) + "\n").encode())
    os.close(report)
    null = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(null, fd)
    time.sleep(LIMIT)
    os._exit(0)


def main() -> None:
    r, w = os.pipe()
    if os.fork() == 0:
        os.close(r)
        survive("fork", w)
    for case in ("double_fork", "setsid"):
        mid = os.fork()
        if mid == 0:
            os.close(r)
            if os.fork() == 0:
                if case == "setsid":
                    os.setsid()
                    if os.fork() == 0:
                        os.setpgid(0, 0)
                        survive("setpgid", w)
                survive(case, w)
            os._exit(0)
        os.waitpid(mid, 0)
    os.close(w)
    seen, buf, deadline = [], b"", time.monotonic() + 10
    while len(seen) < 4 and time.monotonic() < deadline:
        chunk = os.read(r, 4096)
        if not chunk:
            break
        buf += chunk
        *lines, buf = buf.split(b"\n")
        seen += [json.loads(x) for x in lines if x]
    me = {"case": "agent", "pid": os.getpid(), "sid": os.getsid(0), "pgid": os.getpgid(0), "uid": os.getuid()}
    sys.stdout.write(json.dumps({"agent": me, "descendants": seen}) + "\n")
    sys.stdout.flush()
    sys.stdin.readline()  # EXIT or EOF
    time.sleep(LIMIT)  # stay alive: the helper must kill the agent too


if __name__ == "__main__":
    main()
