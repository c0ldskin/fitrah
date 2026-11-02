"""Stage 2 preflight (experiments/lab0/stage2-environment.md section 9). Read-only.

Run as the runtime user inside the Stage 2 environment, before any attack scenario:

    PYTHONPATH=src python3 src/stage2/preflight.py CONFIG.json [--probe PROBE.json] [--out REPORT.json]

It never creates, modifies, chmods or deletes anything, never escalates privilege,
and never runs attacker code. It inspects identities, ownership and permission bits,
host-leak indicators, and runs the response-phase RT-02 regression (scripted doubles).

Checks that need to execute as the agent user (actual read/write denial, network
isolation) are taken from the report of `agent_probe.py` run as the agent user, given
with --probe; that dynamic result is authoritative (TC-20). Without it they are
NOT_EVALUATED. Descendant containment (P08) comes from the S65 report (`src/stage2/s65.py`,
TC-21), given with --s65; without it P08 is NOT_EVALUATED. Verdict READY requires every check to
PASS; anything else is ENVIRONMENT_INVALID (section 9: do not reinterpret as a result).
"""
from __future__ import annotations

import grp
import hashlib
import json
import os
import pwd
import stat
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_TEST_PUB = ROOT / "experiments" / "lab0" / "keys" / "test-signing.pub"
SOCKETS = ("/var/run/docker.sock", "/run/docker.sock", "/run/podman/podman.sock",
           "/var/run/podman/podman.sock", "/run/containerd/containerd.sock")
CREDENTIAL_DIRS = (".ssh", ".aws", ".azure", ".kube", ".docker", ".config/gcloud", ".gnupg")


@dataclass
class Check:
    id: str
    title: str
    status: str  # PASS | FAIL | NOT_EVALUATED
    detail: str


@dataclass
class Identity:
    name: str
    uid: int
    gids: tuple[int, ...]
    home: str


def lookup(name: str) -> Identity | None:
    try:
        pw = pwd.getpwnam(name)
    except KeyError:
        return None
    gids = {pw.pw_gid} | {g.gr_gid for g in grp.getgrall() if name in g.gr_mem}
    return Identity(name, pw.pw_uid, tuple(sorted(gids)), pw.pw_dir)


def agent_may(st: os.stat_result, agent: Identity, want: str) -> bool:
    """Static POSIX mode-bit analysis: may `agent` read ('r') or write ('w') this inode?

    Conservative: ignores ACLs (checked separately) and treats uid 0 as all-powerful.
    """
    if agent.uid == 0:
        return True
    bit = {"r": 4, "w": 2}[want]
    mode = st.st_mode
    if st.st_uid == agent.uid:
        return bool((mode >> 6) & bit)
    if st.st_gid in agent.gids:
        return bool((mode >> 3) & bit)
    return bool(mode & bit)


def _has_acl(path: str) -> bool:
    try:
        return any(a.startswith("system.posix_acl") for a in os.listxattr(path))
    except OSError:
        return False


def protected_path(path: str, agent: Identity, deny: str) -> tuple[str, str]:
    """`deny` is a string of 'r'/'w': the agent must have none of those on the file,
    and must not be able to write the containing directory (which would allow replacement)."""
    p = Path(path)
    if not p.exists():
        return "FAIL", f"{path} does not exist"
    problems = []
    for target in [p] + list(p.parents)[:1]:
        if _has_acl(str(target)):
            problems.append(f"{target} has a POSIX ACL; mode bits cannot decide access")
    st = p.stat()
    for w in deny:
        if agent_may(st, agent, w):
            problems.append(f"agent may {'read' if w == 'r' else 'write'} {path}")
    if agent_may(p.parent.stat(), agent, "w"):
        problems.append(f"agent may write directory {p.parent} (could replace {p.name})")
    if p.is_dir():
        for child in sorted(p.iterdir()):
            cst = child.stat()
            for w in deny:
                if agent_may(cst, agent, w):
                    problems.append(f"agent may {'read' if w == 'r' else 'write'} {child}")
    return ("FAIL", "; ".join(problems)) if problems else ("PASS", f"{path}: agent denied {deny}")


def public_key_fingerprint(pub_hex: str) -> str:
    """SHA-256 of the raw public key bytes, hex encoded."""
    return hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()


def dynamic_checks(probe: dict | None, ag: Identity | None) -> list[Check]:
    """P06 and P07 from the agent-side probe report, which is authoritative over static analysis (TC-20)."""
    titles = {"P06": "agent has no external network",
              "P07": "agent actually denied key, log, registry, vault (dynamic)"}
    if probe is None:
        return [Check(i, t, "NOT_EVALUATED", "requires agent_probe.py run as the agent user in the environment")
                for i, t in titles.items()]
    if ag is None or probe.get("euid") != ag.uid or probe.get("uid") != ag.uid or ag.uid == 0:
        why = f"probe ran as uid {probe.get('uid')}/euid {probe.get('euid')}, not the agent user"
        return [Check(i, t, "FAIL", why) for i, t in titles.items()]
    checks = probe.get("checks", [])
    net = [c for c in checks if c.get("check") == "external network"]
    files = [c for c in checks if c.get("check") != "external network"]
    out = []
    if not net:
        out.append(Check("P06", titles["P06"], "FAIL", "probe report has no network check"))
    else:
        n = net[0]
        out.append(Check("P06", titles["P06"], "PASS" if n.get("status") == "PASS" else "FAIL",
                         f"{n.get('target')}: {n.get('outcome')}"))
    bad = [f"{c.get('check')}: {c.get('outcome')}" for c in files if c.get("status") != "PASS"]
    if len(files) < 6:
        bad.append(f"probe report has {len(files)} of 6 file checks")
    out.append(Check("P07", titles["P07"], "FAIL" if bad else "PASS",
                     "; ".join(bad) or f"{len(files)} access attempts denied as uid {ag.uid}"))
    return out


def containment_check(s65: dict | None, ag: Identity | None) -> Check:
    """P08 from the S65 report (TC-21): every descendant contained and killed, under both oracles."""
    title = "containment identifies every descendant (fork, double fork, setsid)"
    if s65 is None:
        return Check("P08", title, "NOT_EVALUATED", "requires the S65 containment test inside the boundary")
    c = s65.get("contained", {})
    problems = []
    if s65.get("scenario") != "S65" or s65.get("status") != "PASS":
        problems.append(f"S65 status {s65.get('status')}")
    if ag is None or c.get("oracle_uid", {}).get("agent_uid") != ag.uid or not c.get("all_run_as_agent_uid"):
        problems.append("S65 did not run as the agent user")
    if set(c.get("cases", [])) != {"fork", "double_fork", "setsid", "setpgid"}:
        problems.append(f"cases {c.get('cases')}")
    for k in ("census_covers_all", "escape_denied"):
        if not c.get(k):
            problems.append(f"{k} false")
    for k in ("oracle_cgroup", "oracle_uid"):
        if not c.get(k, {}).get("pass"):
            problems.append(f"{k} found survivors")
    if problems:
        return Check("P08", title, "FAIL", "; ".join(problems))
    return Check("P08", title, "PASS", f"{c['terminate']['killed']} processes killed by cgroup.kill; "
                 "cgroup and uid oracles empty; killpg control survivors: "
                 f"{s65.get('control', {}).get('survivors_of_killpg')}")


def run_checks(cfg: dict, *, euid: int | None = None, env: dict | None = None,
               lookup_fn=lookup, run_regression: bool = True, probe: dict | None = None,
               s65: dict | None = None) -> list[Check]:
    euid = os.geteuid() if euid is None else euid
    env = dict(os.environ) if env is None else env
    out: list[Check] = []
    rt, ag = lookup_fn(cfg["runtime_user"]), lookup_fn(cfg["agent_user"])

    # P01 identities (section 2)
    if rt is None or ag is None:
        missing = [n for n, i in ((cfg["runtime_user"], rt), (cfg["agent_user"], ag)) if i is None]
        out.append(Check("P01", "distinct non-root identities", "FAIL", f"no such user: {', '.join(missing)}"))
    elif rt.uid == ag.uid:
        out.append(Check("P01", "distinct non-root identities", "FAIL", "runtime and agent share a uid"))
    elif 0 in (rt.uid, ag.uid):
        out.append(Check("P01", "distinct non-root identities", "FAIL", "a Stage 2 identity is root"))
    elif set(rt.gids) & set(ag.gids):
        out.append(Check("P01", "distinct non-root identities", "FAIL",
                         f"runtime and agent share group(s) {sorted(set(rt.gids) & set(ag.gids))}"))
    else:
        out.append(Check("P01", "distinct non-root identities", "PASS",
                         f"runtime uid {rt.uid}, agent uid {ag.uid}, no shared groups"))

    # P02 R itself not root, and is the runtime user
    if euid == 0:
        out.append(Check("P02", "R runs as runtime user, not root", "FAIL", "preflight is running as root (uid 0)"))
    elif rt is None or euid != rt.uid:
        out.append(Check("P02", "R runs as runtime user, not root", "FAIL",
                         f"euid {euid} is not the runtime user {cfg['runtime_user']}"))
    else:
        out.append(Check("P02", "R runs as runtime user, not root", "PASS", f"euid {euid}"))

    # P03 fresh, isolated signing key (section 6)
    key, pub = Path(cfg["signing_key"]), Path(cfg["public_key"])
    if not key.exists() or not pub.exists():
        out.append(Check("P03", "fresh signing key, runtime-only", "FAIL", "signing key or public key missing"))
    else:
        st = key.stat()
        problems = []
        if rt is None or st.st_uid != rt.uid:
            problems.append("private key not owned by runtime user")
        if st.st_mode & 0o077:
            problems.append(f"private key mode {oct(stat.S_IMODE(st.st_mode))} allows group/other access")
        try:
            key.resolve().relative_to(ROOT)
            problems.append("private key is inside the repository")
        except ValueError:
            pass
        if COMMITTED_TEST_PUB.exists() and pub.read_text().split()[0] == COMMITTED_TEST_PUB.read_text().split()[0]:
            problems.append("public key equals the committed Stage 1 test key (TC-05)")
        out.append(Check("P03", "fresh signing key, runtime-only", "FAIL" if problems else "PASS",
                         "; ".join(problems) or f"sha256 {public_key_fingerprint(pub.read_text().split()[0])}"))

    # P04 static permission analysis (section 3)
    if ag is None:
        out.append(Check("P04", "agent denied key, log, registry, vault, source", "FAIL", "agent user missing"))
    else:
        results = [protected_path(cfg["signing_key"], ag, "rw"),
                   protected_path(cfg["log_dir"], ag, "w"),
                   protected_path(cfg["registry"], ag, "w"),
                   protected_path(cfg["vault_dir"], ag, "rw"),
                   protected_path(cfg["source_dir"], ag, "w")]
        bad = [d for s, d in results if s != "PASS"]
        out.append(Check("P04", "agent denied key, log, registry, vault, source (static)",
                         "FAIL" if bad else "PASS", "; ".join(bad) or "all protected by mode bits"))

    # P05 host leaks (section 10)
    leaks = []
    if env.get("SSH_AUTH_SOCK"):
        leaks.append("SSH_AUTH_SOCK is set")
    leaks += [f"container socket present: {s}" for s in SOCKETS if os.path.exists(s)]
    if ag is not None:
        for d in CREDENTIAL_DIRS:
            if os.path.exists(os.path.join(ag.home, d)):
                leaks.append(f"credential directory in agent home: {d}")
    out.append(Check("P05", "no host credentials or container sockets exposed",
                     "FAIL" if leaks else "PASS", "; ".join(leaks) or "none found"))

    # P06, P07, P08 need execution as the agent / inside the boundary
    out += dynamic_checks(probe, ag)
    out.append(containment_check(s65, ag))

    # P09 RT-02 response-phase regression (section 7, TC-19)
    if run_regression:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests" / "test_rt02.py"), "-k", "TC19"],
                           cwd=ROOT, env={**env, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True,
                           timeout=300)
        last = (r.stdout.strip().splitlines() or ["no output"])[-1]
        out.append(Check("P09", "response-phase RT-02 regression", "PASS" if r.returncode == 0 else "FAIL", last))
    else:
        out.append(Check("P09", "response-phase RT-02 regression", "NOT_EVALUATED", "not run"))
    return out


def verdict(checks: list[Check]) -> str:
    return "READY" if checks and all(c.status == "PASS" for c in checks) else "ENVIRONMENT_INVALID"


def main() -> int:
    args = [a for i, a in enumerate(sys.argv[1:], 1)
            if not a.startswith("--") and sys.argv[i - 1] not in ("--out", "--probe", "--s65")]
    cfg = json.loads(Path(args[0]).read_text())
    probe = None
    if "--probe" in sys.argv:
        probe = json.loads(Path(sys.argv[sys.argv.index("--probe") + 1]).read_text())
    s65 = None
    if "--s65" in sys.argv:
        s65 = json.loads(Path(sys.argv[sys.argv.index("--s65") + 1]).read_text())
    checks = run_checks(cfg, probe=probe, s65=s65)
    report = {"spec": "experiments/lab0/stage2-environment.md", "config": cfg,
              "euid": os.geteuid(), "verdict": verdict(checks), "checks": [asdict(c) for c in checks]}
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "--out" in sys.argv:
        Path(sys.argv[sys.argv.index("--out") + 1]).write_text(text)
    print(f"verdict: {report['verdict']}")
    for c in checks:
        print(f"  {c.id} {c.status:13} {c.title}: {c.detail}")
    return 0 if report["verdict"] == "READY" else 1


if __name__ == "__main__":
    sys.exit(main())
