"""Digital DNA data structures and canonical encoding for Fitrah Lab 0.

This module is the only code shared between the runtime (R) and the
independent verifier. It contains data definitions and encoding only, no
enforcement logic, so a bug in R's checks cannot leak into the verifier.

Capabilities are strings of the form "action:resource", for example
"read:vault" or "spawn:R". Core rules are dicts with keys id, effect,
action and resource.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

PROTECTED_FIELDS = ("id", "parent", "core", "C", "Dg", "status")
RECORD_FIELDS = PROTECTED_FIELDS + ("mut",)


def canon(obj: Any) -> bytes:
    """Canonical JSON: UTF-8, sorted keys, no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(obj: Any) -> str:
    return sha256_hex(canon(obj))


def normalise_core(core: list[dict]) -> list[dict]:
    """Cores compare as sets of rules; order of rules is not significant."""
    return sorted((dict(r) for r in core), key=lambda r: canon(r))


def make_record(id_: str, parent: str | None, core: list[dict], C: list[str], Dg: list[str],
                mut: dict | None = None, status: str = "alive") -> dict:
    return {
        "id": id_,
        "parent": parent,
        "core": normalise_core(core),
        "C": sorted(set(C)),
        "Dg": sorted(set(Dg)),
        "mut": dict(mut or {}),
        "status": status,
    }


def registry_digest(registry: dict[str, dict]) -> str:
    return digest([registry[k] for k in sorted(registry)])


def vault_digest(files: dict[str, str]) -> str:
    return digest(dict(sorted(files.items())))


def clone(obj: Any) -> Any:
    return copy.deepcopy(obj)
