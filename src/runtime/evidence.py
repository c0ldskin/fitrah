"""Hash-chained, Ed25519-signed JSONL evidence log, written only by R (F5).

Each entry carries `seq` and `prev` (SHA-256 of the previous full line,
including its signature). The signature covers the canonical encoding of the
entry without the `sig` field. Ed25519 signatures are deterministic, so a fixed
key gives byte-identical logs across runs.
"""
from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dna.model import canon, sha256_hex

GENESIS_PREV = "0" * 64


class EvidenceFailure(RuntimeError):
    """The run is invalid; retained evidence may require diagnostic inspection."""


def load_signing_key(seed_path: Path) -> Ed25519PrivateKey:
    seed = bytes.fromhex(seed_path.read_text().split()[0])
    return Ed25519PrivateKey.from_private_bytes(seed)


class EvidenceLog:
    def __init__(self, path: Path, key: Ed25519PrivateKey):
        self.path = path
        self.key = key
        # Avoid buffered bytes being written again after a rollback/truncate.
        self.fh = open(path, "wb", buffering=0)
        self.failed = False
        self.seq = 0
        self.prev = GENESIS_PREV

    def append(self, entry: dict) -> dict:
        if self.failed:
            raise EvidenceFailure('evidence writer is failed; start a new run')
        offset = None
        try:
            offset = self.fh.tell()
            body = {"seq": self.seq, "prev": self.prev, **entry}
            body["sig"] = self.key.sign(canon(body)).hex()
            line = canon(body)
            data = line + b"\n"
            written = self.fh.write(data)
            if written != len(data):
                raise OSError('incomplete evidence write')
            self.fh.flush()
        except Exception as exc:
            self.failed = True
            try:
                if offset is None:
                    raise OSError('evidence checkpoint unavailable')
                self.fh.seek(offset)
                self.fh.truncate(offset)
                self.fh.flush()
            except Exception as rollback:
                raise EvidenceFailure('evidence append and rollback failed; retain artifacts') from rollback
            raise EvidenceFailure('evidence append failed; suffix restored; run aborted') from exc
        self.prev = sha256_hex(line)
        self.seq += 1
        return body

    def close(self) -> None:
        self.fh.close()
