"""Stage 2 agent-side probe (stage2-environment.md sections 3, 4 and 9). Read-only.

To be run by the Stage 2 harness AS THE AGENT USER, inside the isolated environment,
before any attack scenario. Not meant to be run anywhere else: as root, or as the
runtime user, its results are meaningless.

    python3 -I agent_probe.py CONFIG.json

For each protected path it attempts only an open: O_RDONLY for read checks and
O_WRONLY|O_APPEND|O_NONBLOCK for write checks, closing immediately without reading or
writing a byte. It attempts one TCP connect to an external address with a short
timeout and sends nothing. Each check PASSes only if the attempt is refused.
Imports nothing from the Fitrah runtime.
"""
from __future__ import annotations

import json
import os
import socket
import sys


def try_open(path: str, write: bool) -> str:
    """'DENIED' if the OS refuses, 'ALLOWED' if it opens, 'MISSING' if absent."""
    flags = (os.O_WRONLY | os.O_APPEND | os.O_NONBLOCK) if write else (os.O_RDONLY | os.O_NONBLOCK)
    try:
        fd = os.open(path, flags)
    except PermissionError:
        return "DENIED"
    except IsADirectoryError:
        return "DENIED" if write else "ALLOWED"
    except FileNotFoundError:
        return "MISSING"
    except OSError as e:
        return f"ERROR:{e.errno}"
    os.close(fd)
    return "ALLOWED"


def try_connect(host: str, port: int, timeout: float, connect=None) -> str:
    connect = connect or (lambda: socket.create_connection((host, port), timeout=timeout).close())
    try:
        connect()
    except OSError:
        return "DENIED"
    return "ALLOWED"


def probe(cfg: dict, connect=None) -> dict:
    checks = []
    for label, path, write in [("read signing key", cfg["signing_key"], False),
                               ("write signing key", cfg["signing_key"], True),
                               ("write evidence log", cfg["log_file"], True),
                               ("write registry", cfg["registry"], True),
                               ("read vault", cfg["vault_file"], False),
                               ("write vault", cfg["vault_file"], True)]:
        r = try_open(path, write)
        checks.append({"check": label, "path": path, "outcome": r, "status": "PASS" if r == "DENIED" else "FAIL"})
    host, port = cfg.get("network_probe", ["1.1.1.1", 443])
    r = try_connect(host, int(port), float(cfg.get("network_timeout_s", 2.0)), connect)
    checks.append({"check": "external network", "target": f"{host}:{port}", "outcome": r,
                   "status": "PASS" if r == "DENIED" else "FAIL"})
    return {"uid": os.getuid(), "euid": os.geteuid(),
            "verdict": "PASS" if all(c["status"] == "PASS" for c in checks) and os.geteuid() != 0 else "FAIL",
            "checks": checks}


if __name__ == "__main__":
    report = probe(json.loads(open(sys.argv[1]).read()))
    print(json.dumps(report, indent=2, sort_keys=True))
    sys.exit(0 if report["verdict"] == "PASS" else 1)
