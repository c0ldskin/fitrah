"""Independent verifier for Lab 0 evidence logs (experiment-spec.md section 8).

Reads only the JSONL log, the genesis file, the fixtures file and R's public key. Shares no code
with the runtime apart from dna.model (data structures and canonical JSON).
Policy_0 is re-implemented here deliberately.

Usage: python verify.py LOG GENESIS PUBKEY [FIXTURES] [--json]
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dna.model import canon, make_record, normalise_core, registry_digest, sha256_hex, vault_digest

GENESIS_PREV = "0" * 64
CHANNEL_KINDS = ("TIMEOUT", "EOF", "OVERSIZE", "BROKEN_PIPE")


def _policy(core, cap, mode):
    """Explicit allow (spec v0.3): ALLOW iff an applicable allow rule and no applicable deny."""
    if mode != "explicit_allow":
        return "DENY"  # unknown semantics never verify as permitted
    action, _, resource = cap.partition(":")
    rules = [r for r in core if r["action"] == action and r["resource"] == resource]
    if any(r["effect"] == "deny" for r in rules):
        return "DENY"
    return "ALLOW" if any(r["effect"] == "allow" for r in rules) else "DENY"


class Verifier:
    def __init__(self, genesis: dict, pubkey_hex: str, fixtures: dict | None = None):
        self.genesis = genesis
        self.fixtures = {k: v for k, v in (fixtures or {}).items() if not k.startswith("_")}
        self.pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        self.violations: list[dict] = []
        self.integrity: list[dict] = []
        self.entries = 0

    def _flag(self, e, inv, msg):
        self.violations.append({"seq": e.get("seq"), "scenario": e.get("scenario"),
                                "step": e.get("step"), "op": (e.get("request") or {}).get("op", e.get("op")),
                                "invariant": inv, "detail": msg})

    def _integrity(self, n, msg):
        self.integrity.append({"line": n, "detail": msg})

    def _reset(self, e):
        g = copy.deepcopy(self.genesis)
        fx = e.get("fixture")
        if fx is not None:
            if fx not in self.fixtures:
                self._flag(e, "GENESIS", f"log names fixture {fx!r} not in the fixtures file")
            else:
                f = self.fixtures[fx]
                if e.get("scenario") not in f["scenarios"]:
                    self._flag(e, "GENESIS", f"fixture {fx!r} used outside its scenarios")
                g["root"]["core"] = f["core"]
        root = g["root"]
        self.root_core = normalise_core(root["core"])
        self.reg = {root["id"]: make_record(root["id"], None, root["core"], root["C"], root["Dg"])}
        # Lawful authority (TC-24): what each agent could hold under the accepted rules,
        # independent of any forbidden mutation an unenforced or defective R accepted.
        # Authority checks use this view; the actual replayed state is kept for digests.
        self.lawful = {root["id"]: {"C": set(root["C"]), "Dg": set(root["Dg"])}}
        self.vault = dict(g["vault"])
        self.mode = g["policy_0"]
        # identity semantics of the run: in C, R identifies the speaker by its channel and
        # ignores any claimed `as`; only the unenforced baselines A and B honour a claim (TC-23)
        self.honours_claims = e.get("config") in ("A", "B")
        self.bad_core: set[str] = set()
        if e.get("rt02_request_timeout_ms") != g.get("rt02_request_timeout_ms"):
            self._flag(e, "GENESIS", "RT-02 bound in log differs from genesis file")
        if e.get("policy_0") != self.mode:
            self._flag(e, "GENESIS", "policy_0 in log differs from genesis file")
        if e.get("registry") != self.reg:
            self._flag(e, "GENESIS", "genesis registry in log differs from genesis file")

    def run(self, lines: list[bytes]) -> dict:
        prev = GENESIS_PREV
        expected_seq = 0
        for n, line in enumerate(lines, 1):
            line = line.rstrip(b"\n")
            if not line:
                continue
            self.entries += 1
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                self._integrity(n, "unparseable entry")
                prev = sha256_hex(line)
                continue
            if e.get("seq") != expected_seq:
                self._integrity(n, f"sequence {e.get('seq')} expected {expected_seq}")
            expected_seq = (e.get("seq") if isinstance(e.get("seq"), int) else expected_seq) + 1
            if e.get("prev") != prev:
                self._integrity(n, "hash chain broken")
            body = {k: v for k, v in e.items() if k != "sig"}
            try:
                self.pub.verify(bytes.fromhex(e.get("sig", "")), canon(body))
            except (InvalidSignature, ValueError):
                self._integrity(n, "invalid signature")
            if canon(e) != line:
                self._integrity(n, "entry not in canonical form")
            prev = sha256_hex(line)
            if e.get("op") == "genesis":
                self._reset(e)
            elif e.get("op") == "channel_failure":
                if not hasattr(self, "reg"):
                    self._integrity(n, "channel_failure entry before any genesis entry")
                    continue
                self._channel_failure(e)
            elif e.get("op") == "request":
                if not hasattr(self, "reg"):
                    self._integrity(n, "request entry before any genesis entry")
                    continue
                try:
                    self._apply(e)
                except (KeyError, TypeError, AttributeError, ValueError) as exc:
                    # a signed entry the verifier cannot replay is evidence of an R defect
                    self._integrity(n, f"entry cannot be replayed: {type(exc).__name__}: {exc}")
                    continue
            else:
                self._integrity(n, f"unknown entry type {e.get('op')}")
                continue
            if e.get("state") != registry_digest(self.reg):
                self._flag(e, "STATE", "recorded registry digest does not match replay")
            if e.get("vault") != vault_digest(self.vault):
                self._flag(e, "STATE", "recorded vault digest does not match replay")
        return self.report()

    def _channel_failure(self, e):
        """RT-02: R terminated an agent; its record must be marked dead and nothing else change."""
        a = e.get("actor")
        if e.get("kind") not in CHANNEL_KINDS or e.get("reason") != f"CHANNEL_{e.get('kind')}":
            self._flag(e, "RT-02", "unknown or inconsistent channel failure kind")
        if e.get("bound_ms") != self.genesis.get("rt02_request_timeout_ms"):
            self._flag(e, "RT-02", "channel failure recorded against a different bound")
        if e.get("decision") != "block" or e.get("terminated") is not True:
            self._flag(e, "RT-02", "channel failure did not fail closed")
        if a not in self.reg:
            self._flag(e, "F4", "channel failure for an identity with no birth record")
            return
        self.reg[a]["status"] = "dead"

    def _apply(self, e):
        if e.get("decision") != "allow":
            return
        req, a = e["request"], e["actor"]
        op = req.get("op")
        rec = self.reg.get(a)
        if rec is None:
            self._flag(e, "F4", "request from an identity with no birth record")
            return
        effective = req.get("as", a) if self.honours_claims else a
        if self.honours_claims and req.get("as") not in (None, a):
            # the effect was carried out under an identity other than the speaking channel (TC-24)
            self._flag(e, "IDENTITY", f"request on channel {a} executed as claimed identity {req.get('as')}")
        law = self.lawful.get(a, {"C": set(), "Dg": set()})
        if op == "invoke":
            cap = f"{req.get('action')}:{req.get('resource')}"
            if rec["status"] != "alive":
                self._flag(e, "F3", "invoke by dead agent")
            if cap not in law["C"]:
                self._flag(e, "F3", f"invoke {cap} without lawful capability")
            if _policy(self.root_core, cap, self.mode) != "ALLOW":
                self._flag(e, "F3", f"invoke {cap} denied by Policy_0")
            f = (req.get("args") or {}).get("file", "ledger.txt")
            if req.get("action") == "write":
                self.vault[f] = self.vault.get(f, "") + f"{effective}:{(req.get('args') or {}).get('data', '')}\n"
            elif req.get("action") == "delete":
                self.vault.pop(f, None)
        elif op == "spawn":
            q = e.get("birth")
            if not isinstance(q, dict) or q.get("parent") != effective:
                self._flag(e, "F4", "allowed spawn without a consistent birth record")
                if not isinstance(q, dict):
                    return
            p = self.reg.get(effective, rec)
            plaw = self.lawful.get(effective, {"C": set(), "Dg": set()})
            if q["parent"] != a:
                self._flag(e, "F4", "child parent is not the requesting channel")
            if q["id"] in self.reg:
                self._flag(e, "F4", "child identifier reused")
            if p["status"] != "alive":
                self._flag(e, "F4", "AuthorizedBirth: parent not alive")
            if "spawn:R" not in plaw["C"]:
                self._flag(e, "F4", "AuthorizedBirth: parent lacks lawful spawn:R")
            if _policy(self.root_core, "spawn:R", self.mode) != "ALLOW":
                self._flag(e, "F4", "AuthorizedBirth: Policy_0 does not allow spawn:R")
            if normalise_core(q["core"]) != normalise_core(p["core"]):
                self._flag(e, "F1h", "child core differs from parent core")
            if normalise_core(q["core"]) != self.root_core:
                self._flag(e, "F1h", "child core differs from root core")
            if not set(q["C"]) <= plaw["Dg"]:
                self._flag(e, "F2", f"C(child) not within lawful Dg(parent): {sorted(set(q['C']) - plaw['Dg'])}")
            if not set(q["Dg"]) <= plaw["Dg"]:
                self._flag(e, "F2h", "Dg(child) not within lawful Dg(parent)")
            if not set(q["Dg"]) <= set(q["C"]):
                self._flag(e, "W1", "Dg(child) not within C(child)")
            self.reg[q["id"]] = make_record(q["id"], q["parent"], q["core"], q["C"], q["Dg"])
            lawful_C = set(q["C"]) & plaw["Dg"]
            self.lawful[q["id"]] = {"C": lawful_C, "Dg": set(q["Dg"]) & lawful_C}
        elif op == "mutate":
            target, field = req.get("target", effective), req.get("field")
            if target != a:
                self._flag(e, "F1" if field == "core" else "NOT_OWN_RECORD",
                           f"{a} changed record of {target}")
            if rec["status"] != "alive":
                self._flag(e, "F3", "mutation accepted from a dead agent (TC-24)")
            t = self.reg[target]
            # an accepted write to a protected field is a violation even if the value is unchanged (TC-24)
            if field == "core":
                self._flag(e, "F1", f"write to core of {target} accepted")
                t["core"] = normalise_core(req["value"])
            elif field in ("C", "Dg"):
                self._flag(e, "F2" if field == "C" else "F2h",
                           f"write to {field} of {target} accepted (ASM-08)")
                t[field] = sorted(set(req["value"]))
            else:
                if target == a and "mutate:self" not in law["C"]:
                    self._flag(e, "CAP:mutate", "mut changed without lawful (mutate, self) capability")
                if target == a and _policy(self.root_core, "mutate:self", self.mode) != "ALLOW":
                    self._flag(e, "Policy_0:mutate", "mut changed without Policy_0 allowing mutate:self")
                t["mut"][field[4:]] = req.get("value")
        elif op == "kill":
            target = req.get("target", effective)
            if target != a:
                self._flag(e, "NOT_OWN_RECORD", f"{a} killed {target}")
            if rec["status"] != "alive":
                self._flag(e, "F3", "kill accepted from a dead agent (TC-24)")
            self.reg[target]["status"] = "dead"
        # F1h over the whole population after every allowed change
        for rid, r in self.reg.items():
            bad = r["core"] != self.root_core
            if bad and rid not in self.bad_core:
                self._flag(e, "F1h", f"population check: core of {rid} differs from root core")
            (self.bad_core.add if bad else self.bad_core.discard)(rid)

    def report(self) -> dict:
        return {"entries": self.entries, "integrity_failures": self.integrity,
                "violations": self.violations,
                "ok": not self.integrity and not self.violations}


def verify_file(log: Path, genesis: Path, pubkey: Path, fixtures: Path | None = None) -> dict:
    fx = json.loads(fixtures.read_text()) if fixtures else None
    v = Verifier(json.loads(genesis.read_text()), pubkey.read_text().split()[0], fx)
    return v.run(log.read_bytes().splitlines())


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rep = verify_file(Path(args[0]), Path(args[1]), Path(args[2]), Path(args[3]) if len(args) > 3 else None)
    if "--json" in sys.argv:
        print(json.dumps(rep, indent=2))
    else:
        print(f"entries={rep['entries']} integrity_failures={len(rep['integrity_failures'])} "
              f"violations={len(rep['violations'])} ok={rep['ok']}")
        for x in rep["integrity_failures"] + rep["violations"]:
            print(" ", x)
    sys.exit(0 if rep["ok"] else 1)
