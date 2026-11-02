"""In-process driver for Stage 1B (experiments/lab0/stage1b-robustness.md).

DirectMonitor is R (runtime.monitor.Monitor) with one change: agents are not OS
processes. `_launch` registers a stub channel instead of starting a process, so
R's decision and state logic can be driven millions of times. Everything that
decides allow/block, every state change and every evidence entry is R's own code.

The process and channel layer is covered separately by the Stage 1 and RT-02
tests, and `experiments.cross_check_process_path` replays a sample of generated
histories through the real process path to show the decisions are identical.

A program containing LAUNCH_FAIL makes the stub fail like a child that cannot
receive its program in time (RT-02), which exercises RT-01 rollback.
"""
from __future__ import annotations

import copy
import json

from runtime.channel import ChannelFailure
from runtime.monitor import Monitor

LAUNCH_FAIL = {"__stage1b__": "launch_fail"}


class _Stub:
    def kill(self):
        pass

    def close(self, grace):
        pass


class NullLog:
    """Evidence sink for the exhaustive search: keeps sequence numbers, writes nothing."""

    def __init__(self):
        self.seq = 0

    def append(self, entry):
        self.seq += 1
        return entry

    def close(self):
        pass


class DirectMonitor(Monitor):
    def _launch(self, agent_id, program):
        self.procs[agent_id] = _Stub()
        if isinstance(program, list) and LAUNCH_FAIL in program:
            raise ChannelFailure("TIMEOUT")

    def submit(self, actor: str, request) -> dict:
        """One request on `actor`'s channel. `request` is a dict or a raw string."""
        self.step += 1
        raw = request if isinstance(request, str) else json.dumps(request, sort_keys=True)
        return self.handle(actor, raw)

    # -- snapshot helpers for the exhaustive search ---------------------------------------
    def load_state(self, registry: dict, vault: dict, counter: int) -> None:
        self.registry = copy.deepcopy(registry)
        self.vault = dict(vault)
        self.spawn_counter = counter
        self.procs = {a: _Stub() for a in self.registry}
