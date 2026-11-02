"""Deliberately defective runtimes for Stage 1B experiment 3 (fault injection).

Each defect disables exactly one enforcement property. `_enforced` below is a copy
of runtime.monitor.Monitor._enforced with one guarded change per defect, so R's
own code carries no test hooks. `tests/test_stage1b.py` proves that the copy with
no defect is decision- and evidence-identical to R on Stage 1 scenarios and on
generated histories.
"""
from __future__ import annotations

from dna.model import clone, registry_digest
from runtime.monitor import Malformed, _caps, _core, normalise_core, policy_0
from stage1b.direct import DirectMonitor

DEFECTS = {
    "D01": "skip core equality on birth",
    "D02": "skip C(child) within Dg(parent)",
    "D03": "skip Dg(child) within C(child) (W1)",
    "D04": "skip Policy_0 on invoke",
    "D05": "skip Policy_0 on spawn",
    "D06": "skip (mutate, self) capability check",
    "D07": "skip Policy_0 on mutation",
    "D08": "trust claimed identity instead of channel identity",
    "D09": "allow birth from a dead parent",
    "D10a": "omit birth evidence",
    "D10b": "falsify birth evidence (logged record differs from registry)",
    "D10c": "falsify birth evidence and the state digest consistently",
    "D11": "break RT-01 rollback",
}


class DefectiveMonitor(DirectMonitor):
    defect: str | None = None

    def __init__(self, *a, defect: str | None = None, **kw):
        self.defect = defect
        self._shadow: dict[str, dict] = {}
        super().__init__(*a, **kw)

    def _on(self, d: str) -> bool:
        return self.defect == d

    # D10c: the digest R records is computed over the falsified view
    def _state(self) -> str:
        if not getattr(self, "_shadow", None):
            return super()._state()
        view = clone(self.registry)
        for aid, fields in self._shadow.items():
            if aid in view:
                view[aid].update(fields)
        return registry_digest(view)

    # D11
    def _rollback(self, snapshot) -> None:
        if self._on("D11"):
            return
        super()._rollback(snapshot)

    def _enforced(self, a: str, req: dict):
        if self._on("D08"):
            claimed = req.get("as")
            if isinstance(claimed, str) and claimed in self.registry:
                a = claimed
        op = req["op"]
        rec = self.registry[a]
        if op == "invoke":
            cap = self._invoke_cap(req)
            if not self._alive(a):
                return "block", "ACTOR_DEAD", None
            if cap not in rec["C"]:
                return "block", "NO_CAP", None
            if not self._on("D04") and policy_0(rec["core"], cap, self.policy_mode) != "ALLOW":
                return "block", "CORE_FORBIDS", None
            self._perform(a, req)
            return "allow", "PERMITTED_0", None
        if op == "spawn":
            child = req.get("child")
            if not isinstance(child, dict):
                raise Malformed("child")
            core_q = normalise_core(_core(child.get("core")))
            C_q, Dg_q = set(_caps(child.get("C"))), set(_caps(child.get("Dg")))
            q_id = self._next_id()
            if not self._on("D09") and not self._alive(a):
                return "block", "PARENT_DEAD", None
            if "spawn:R" not in rec["C"]:
                return "block", "NO_SPAWN_CAP", None
            if not self._on("D05") and policy_0(rec["core"], "spawn:R", self.policy_mode) != "ALLOW":
                return "block", "CORE_FORBIDS", None
            if not self._on("D01") and core_q != rec["core"]:
                return "block", "CORE_MISMATCH", None
            if not self._on("D02") and not C_q <= set(rec["Dg"]):
                return "block", "CAP_NOT_DELEGABLE", None
            if not self._on("D03") and not Dg_q <= C_q:
                return "block", "W1_VIOLATION", None
            birth = self._birth(a, q_id, core_q, C_q, Dg_q, req)
            if self._on("D10a"):
                birth = None
            elif self._on("D10b") or self._on("D10c"):
                birth = dict(birth, C=[], Dg=[])
                if self._on("D10c"):
                    self._shadow[q_id] = {"C": [], "Dg": []}
            return "allow", "AUTHORIZED_BIRTH", birth
        if op == "mutate":
            target, field = req.get("target", a), req.get("field")
            if not isinstance(field, str):
                raise Malformed("field")
            if target != a:
                return "block", "NOT_OWN_RECORD", None
            if not self._alive(a):
                return "block", "ACTOR_DEAD", None
            if field == "core":
                return "block", "CORE_IMMUTABLE", None
            if field in ("C", "Dg", "id", "parent", "status"):
                return "block", "PROTECTED_FIELD", None
            if not field.startswith("mut.") or len(field) <= 4:
                raise Malformed("field")
            if not self._on("D06") and "mutate:self" not in rec["C"]:
                return "block", "NO_CAP", None
            if not self._on("D07") and policy_0(rec["core"], "mutate:self", self.policy_mode) != "ALLOW":
                return "block", "CORE_FORBIDS", None
            rec["mut"][field[4:]] = req.get("value")
            return "allow", "MUTABLE_FIELD", None
        if op == "kill":
            if req.get("target", a) != a:
                return "block", "NOT_OWN_RECORD", None
            if not self._alive(a):
                return "block", "ACTOR_DEAD", None
            rec["status"] = "dead"
            return "allow", "SELF_KILL", None
        raise Malformed(op)
