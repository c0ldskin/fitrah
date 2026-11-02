"""TC-27: actual retained bytes and state after injected I/O failures."""
import json
from pathlib import Path

import pytest

from runtime.evidence import EvidenceLog, EvidenceFailure, load_signing_key
from runtime.monitor import Monitor, RunInvalid
from simulator.verify import Verifier

LAB = Path(__file__).resolve().parents[1] / 'experiments' / 'lab0'
GENESIS = json.loads((LAB / 'genesis.json').read_text())
KEY = load_signing_key(LAB / 'keys/test-signing.seed')
PUB = (LAB / 'keys/test-signing.pub').read_text().strip()
WRITE = json.dumps(dict(op='invoke', action='write', resource='vault', args=dict(data='tc27')))


class FaultFile:
    def __init__(self, stream, fault):
        self.stream, self.fault = stream, fault
        self.triggered = False
    def __getattr__(self, name):
        return getattr(self.stream, name)
    def write(self, data):
        if self.fault == 'before':
            raise OSError('before write')
        if self.fault in ('partial', 'rollback'):
            self.stream.write(data[:7])
            raise OSError('after partial write')
        if self.fault == 'short':
            return self.stream.write(data[:7])
        return self.stream.write(data)
    def flush(self):
        if self.fault == 'flush' and not self.triggered:
            self.triggered = True
            raise OSError('flush')
        return self.stream.flush()
    def truncate(self, offset):
        if self.fault == 'rollback':
            raise OSError('truncate')
        return self.stream.truncate(offset)


def setup_run(tmp_path):
    path = tmp_path / 'evidence.jsonl'
    log = EvidenceLog(path, KEY)
    m = Monitor(GENESIS, 'C', log, 'TC27', 'test')
    return path, log, m


@pytest.mark.parametrize('fault', ['before', 'partial', 'short', 'flush', 'sign'])
def test_failed_commit_restores_bytes_state_and_rejects_continuation(tmp_path, fault):
    path, log, m = setup_run(tmp_path)
    before = path.read_bytes(), dict(m.vault), json.dumps(m.registry), log.seq, log.prev
    if fault == 'sign':
        class BadKey:
            def sign(self, data):
                raise ValueError('sign failed')
        log.key = BadKey()
    else:
        log.fh = FaultFile(log.fh, fault)
    with pytest.raises(RunInvalid):
        m.handle(GENESIS['root']['id'], WRITE)
    assert (path.read_bytes(), m.vault, json.dumps(m.registry), log.seq, log.prev) == before
    with pytest.raises(RunInvalid):
        m.handle(GENESIS['root']['id'], WRITE)
    with pytest.raises(RunInvalid):
        m.run([], [])
    with pytest.raises(EvidenceFailure):
        log.append({'op': 'anything'})
    assert Verifier(GENESIS, PUB).run(path.read_bytes().splitlines())['ok']
    log.close()


def test_failed_evidence_rollback_retains_artifact_and_invalidates_run(tmp_path):
    path, log, m = setup_run(tmp_path)
    before, vault, seq, head = path.read_bytes(), dict(m.vault), log.seq, log.prev
    log.fh = FaultFile(log.fh, 'rollback')
    with pytest.raises(RunInvalid):
        m.handle(GENESIS['root']['id'], WRITE)
    assert path.read_bytes() == before + b'{"actor'
    assert m.vault == vault and (log.seq, log.prev) == (seq, head)
    assert m.failed and log.failed
    log.close()


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_unlogged_birth_rolls_back_and_retains_failed_cleanup_handle(tmp_path, cleanup_fails):
    path, log, m = setup_run(tmp_path)
    class Child:
        calls = 0
        def kill(self):
            self.calls += 1
            if cleanup_fails:
                raise OSError('cleanup failed')
    child = Child()
    m._launch = lambda agent_id, program: m.procs.update({agent_id: child})
    log.fh = FaultFile(log.fh, 'before')
    req = dict(op='spawn', child=dict(core=GENESIS['root']['core'], C=['read:vault'], Dg=[]), program=[])
    with pytest.raises(RunInvalid):
        m.handle(GENESIS['root']['id'], json.dumps(req))
    assert len(m.registry) == 1 and m.spawn_counter == 2 and child.calls == 1
    assert ('a1' in m.procs) == cleanup_fails
    assert m.failed
    log.close()


def test_successful_bytes_and_verifier_unchanged(tmp_path):
    path, log, m = setup_run(tmp_path)
    assert m.handle(GENESIS['root']['id'], WRITE)['decision'] == 'allow'
    log.close()
    assert Verifier(GENESIS, PUB).run(path.read_bytes().splitlines())['ok']
    # Reconstruct expected canonical bytes using the original append algorithm.
    from dna.model import canon, sha256_hex
    prev = '0' * 64
    expected = []
    for seq, raw in enumerate(path.read_bytes().splitlines()):
        entry = json.loads(raw)
        sig = entry.pop('sig')
        assert entry['seq'] == seq and entry['prev'] == prev
        assert KEY.sign(canon(entry)).hex() == sig
        line = canon(dict(entry, sig=sig))
        expected.append(line + b'\n')
        prev = sha256_hex(line)
    assert path.read_bytes() == b''.join(expected)


def test_run_attempts_all_cleanup_even_when_one_close_fails(tmp_path):
    path, log, m = setup_run(tmp_path)
    closed = []
    class Child:
        def __init__(self, name):
            self.name = name
        def close(self, grace):
            closed.append(self.name)
            if self.name == 'first':
                raise OSError('close failed')
    m._launch = lambda agent_id, program: m.procs.update(first=Child('first'), second=Child('second'))
    with pytest.raises(RunInvalid):
        m.run([], [])
    assert closed == ['first', 'second'] and m.failed
    log.close()


def test_entry_preparation_failure_restores_effect(tmp_path):
    path, log, m = setup_run(tmp_path)
    before, vault = path.read_bytes(), dict(m.vault)
    def bad_digest():
        raise ValueError('digest preparation failed')
    m._vault = bad_digest
    with pytest.raises(RunInvalid):
        m.handle(GENESIS['root']['id'], WRITE)
    assert m.vault == vault and path.read_bytes() == before and m.failed
    log.close()


def test_timeout_cleanup_failure_retains_handle_for_shutdown(tmp_path):
    from runtime.channel import ChannelFailure
    path, log, m = setup_run(tmp_path)
    calls = []
    class Child:
        def send_line(self, *args):
            raise ChannelFailure('TIMEOUT')
        def kill(self):
            calls.append('kill')
            raise OSError('kill failed')
        def close(self, grace):
            calls.append('close')
    m._launch = lambda agent_id, program: m.procs.update({agent_id: Child()})
    with pytest.raises(RunInvalid):
        m.run([], [GENESIS['root']['id']])
    assert calls == ['kill', 'close'] and m.failed
    assert len(path.read_bytes().splitlines()) == 1
    log.close()
