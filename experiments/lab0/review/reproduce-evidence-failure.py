"""Off-VM RT-01 counterexample; no agents, keys or protected files."""
import json
from pathlib import Path
from runtime.monitor import Monitor

class FailingLog:
    def __init__(self):
        self.entries = []
    def append(self, entry):
        if entry['op'] == 'request':
            raise OSError('injected evidence append failure')
        self.entries.append(entry)

genesis = json.loads(Path('experiments/lab0/genesis.json').read_text())
log = FailingLog()
m = Monitor(genesis, 'C', log, 'RT01-evidence-failure', 'local-review')
before = dict(m.vault)
try:
    m.handle(genesis['root']['id'], json.dumps(dict(op='invoke', action='write', resource='vault', args=dict(data='test-only'))))
except OSError as exc:
    result = dict(error=str(exc), vault_changed=m.vault != before,
                  request_evidence_count=sum(e['op'] == 'request' for e in log.entries),
                  agent_processes_launched=False)
    print(json.dumps(result, indent=2))
    assert result['vault_changed'] and result['request_evidence_count'] == 0
else:
    raise AssertionError('Expected injected failure')

