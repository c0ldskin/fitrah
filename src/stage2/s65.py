"""S65 descendant containment (TC-21), run as the runtime user inside the Stage 2 VM.

  PYTHONPATH=src python3 src/stage2/s65.py /srv/fitrah/stage2.json --out s65.json [--socket PATH]

1. Control, Stage 1 mechanics: launch the double with Popen + killpg as the runtime user and
   record which descendants survive killpg (expected: setsid and setpgid). Survivors are then
   killed by pid. This shows the test can detect an escape.
2. Contained, Stage 2 mechanics: launch the double through fitrah-agentctl as the agent user,
   census the cgroup, terminate with cgroup.kill, then apply two independent oracles:
   cgroup oracle  the agent's cgroup (read from /proc/<pid>/cgroup before teardown) is gone or empty
   uid oracle     no process anywhere in /proc is owned by the agent user
"""
from __future__ import annotations

import json
import os
import platform
import pwd
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from runtime.channel import Channel, HelperChannel  # noqa: E402
from stage2.agentctl_client import DEFAULT_SOCKET, AgentCtl  # noqa: E402

DOUBLE = ROOT / "tests" / "doubles" / "s65_descendants.py"
CASES = {"fork", "double_fork", "setsid", "setpgid"}


def cgroup2_mount() -> str:
    for line in open("/proc/self/mounts"):
        f = line.split()
        if f[2] == "cgroup2":
            return f[1]
    return "/sys/fs/cgroup"


def alive(pid: int) -> bool:
    try:
        st = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return False
    return "\nState:\tZ" not in st


def uid_scan(uid: int) -> list[int]:
    found = []
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                st = d.joinpath("status").read_text()
            except OSError:
                continue
            uids = [int(x) for x in st.split("\nUid:\t")[1].split("\n")[0].split()]
            if uid in uids:
                found.append(int(d.name))
    return found


def read_report(ch: Channel) -> dict:
    return json.loads(ch.recv_line(time.monotonic() + 15))


def control() -> dict:
    ch = Channel([sys.executable, "-I", str(DOUBLE)])
    rep = read_report(ch)
    pids = {d["case"]: d["pid"] for d in rep["descendants"]}
    ch.kill()
    time.sleep(0.5)
    survivors = sorted(c for c, p in pids.items() if alive(p))
    for p in pids.values():
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return {"mechanism": "killpg", "cases": sorted(pids), "survivors_of_killpg": survivors,
            "detects_escape": bool(survivors)}


def contained(sock: str, agent_uid: int) -> dict:
    agent_id = f"s65-{os.getpid()}"
    ch = HelperChannel(AgentCtl(sock), agent_id, "s65")
    rep = read_report(ch)
    procs = [rep["agent"], *rep["descendants"]]
    cg_line = [x for x in Path(f"/proc/{ch.pid}/cgroup").read_text().splitlines() if x.startswith("0::")][0]
    cg = Path(cgroup2_mount() + cg_line[3:])
    cg_before = cg.exists() and {p["pid"] for p in procs} <= set(int(x) for x in (cg / "cgroup.procs").read_text().split())
    census = ch.ctl.census(agent_id)
    ch.close(1.0)
    term = ch.terminated
    cg_left = [int(x) for x in (cg / "cgroup.procs").read_text().split()] if cg.exists() else []
    for _ in range(30):  # let init reap reparented zombies
        uid_left = uid_scan(agent_uid)
        if not uid_left:
            break
        time.sleep(0.1)
    leaders = {d["case"]: d["pgid"] != rep["agent"]["pgid"] for d in rep["descendants"]}
    return {
        "mechanism": "fitrah-agentctl, cgroup.kill", "agent_id": agent_id, "cgroup": str(cg),
        "cases": sorted(d["case"] for d in rep["descendants"]),
        "processes": procs,
        "left_agent_process_group": leaders,
        "all_run_as_agent_uid": all(p["uid"] == agent_uid for p in procs),
        "census": sorted(census), "census_covers_all": {p["pid"] for p in procs} <= set(census),
        "escape_attempts": {d["case"]: d["escape"] for d in rep["descendants"]},
        "escape_denied": all("MOVED" not in d["escape"] for d in rep["descendants"]),
        "terminate": term,
        "oracle_cgroup": {"all_in_cgroup_before": cg_before, "cgroup_exists_after": cg.exists(), "procs": cg_left,
                          "pass": cg_before and not cg_left},
        "oracle_uid": {"agent_uid": agent_uid, "processes": uid_left, "pass": not uid_left},
    }


def main() -> int:
    argv = sys.argv[1:]
    cfg = json.loads(Path(argv[0]).read_text())
    sock = argv[argv.index("--socket") + 1] if "--socket" in argv else DEFAULT_SOCKET
    agent_uid = pwd.getpwnam(cfg["agent_user"]).pw_uid
    ctrl = control()
    cont = contained(sock, agent_uid)
    ok = (cont["cases"] == sorted(CASES) and cont["census_covers_all"] and cont["all_run_as_agent_uid"]
          and cont["escape_denied"] and bool(cont["terminate"]) and cont["terminate"].get("ok")
          and cont["oracle_cgroup"]["pass"] and cont["oracle_uid"]["pass"]
          and cont["left_agent_process_group"].get("setsid") and cont["left_agent_process_group"].get("setpgid"))
    report = {"scenario": "S65", "design": "experiments/lab0/stage2-s65-design.md (TC-21 revision 2)",
              "status": "PASS" if ok else "FAIL", "runtime_uid": os.getuid(), "kernel": platform.release(),
              "control": ctrl, "contained": cont}
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "--out" in argv:
        Path(argv[argv.index("--out") + 1]).write_text(text)
    print(f"S65 {report['status']}: cases {cont['cases']}; killpg survivors {ctrl['survivors_of_killpg']}; "
          f"cgroup.kill killed {cont['terminate'].get('killed') if cont['terminate'] else None}; "
          f"cgroup oracle {cont['oracle_cgroup']['pass']}; uid oracle {cont['oracle_uid']['pass']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
