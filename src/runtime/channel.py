"""Deadline-bounded line channel between R and one agent process (RT-02).

Every read and write R performs on an agent's pipes is bounded by a deadline,
so an agent cannot stall R by never answering, by sending a partial line, by
streaming without a newline, or by refusing to read (which would eventually
block R's writes on a full pipe). Reads are also bounded in size.

Only raw file descriptors are used (no buffered text wrappers), so readiness
reported by `select` matches the bytes actually available.
"""
from __future__ import annotations

import os
import select
import signal
import subprocess
import time

MAX_LINE_BYTES = 1 << 20  # 1 MiB per request line


class ChannelFailure(Exception):
    """The agent did not complete a channel operation within its bound."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind  # TIMEOUT | EOF | OVERSIZE | BROKEN_PIPE


class Channel:
    def __init__(self, argv: list[str]):
        # own process group, so termination reaches anything the agent forked (Stage 2 readiness);
        # a process that calls setsid() escapes this, which only an OS container or cgroup prevents
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0,
                                     start_new_session=True)
        self._in = self.proc.stdin.fileno()
        self._out = self.proc.stdout.fileno()
        os.set_blocking(self._in, False)
        os.set_blocking(self._out, False)
        self._buf = b""

    def send_line(self, data: bytes, deadline: float) -> None:
        view = memoryview(data + b"\n")
        while view:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ChannelFailure("TIMEOUT")
            _, writable, _ = select.select([], [self._in], [], remaining)
            if not writable:
                raise ChannelFailure("TIMEOUT")
            try:
                n = os.write(self._in, view)
            except BlockingIOError:
                continue
            except (BrokenPipeError, OSError):
                raise ChannelFailure("BROKEN_PIPE") from None
            view = view[n:]

    def recv_line(self, deadline: float) -> bytes:
        while b"\n" not in self._buf:
            if len(self._buf) > MAX_LINE_BYTES:
                raise ChannelFailure("OVERSIZE")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ChannelFailure("TIMEOUT")
            readable, _, _ = select.select([self._out], [], [], remaining)
            if not readable:
                raise ChannelFailure("TIMEOUT")
            try:
                chunk = os.read(self._out, 65536)
            except BlockingIOError:
                continue
            if not chunk:
                raise ChannelFailure("EOF")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        if len(line) > MAX_LINE_BYTES:
            raise ChannelFailure("OVERSIZE")
        return line

    def kill(self) -> None:
        self._kill_group()
        self.proc.wait(timeout=10)
        self._close_pipes()

    def _kill_group(self) -> None:
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def close(self, grace: float) -> None:
        """Ask the agent to exit; kill it if it has not exited within `grace` seconds."""
        try:
            self.send_line(b"EXIT", time.monotonic() + grace)
        except ChannelFailure:
            pass
        self._close_pipes()
        try:
            self.proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        self._kill_group()  # always reap the group, even after a clean exit
        self.proc.wait(timeout=10)

    def _close_pipes(self) -> None:
        for f in (self.proc.stdin, self.proc.stdout):
            try:
                f.close()
            except OSError:
                pass


class HelperChannel(Channel):
    """Stage 2 mode (TC-21): the agent is launched by fitrah-agentctl into its own cgroup as the
    agent user; termination is cgroup.kill through the helper. Stage 1 keeps Channel and killpg."""

    def __init__(self, ctl, agent_id: str, program: str):
        self.ctl, self.agent_id = ctl, agent_id
        self.pid, self._in, self._out = ctl.launch(agent_id, program)
        os.set_blocking(self._in, False)
        os.set_blocking(self._out, False)
        self._buf = b""
        self.terminated: dict | None = None

    def _kill_group(self) -> None:
        if self.terminated is None:
            self.terminated = self.ctl.terminate(self.agent_id)

    def kill(self) -> None:
        self._kill_group()
        self._close_pipes()

    def close(self, grace: float) -> None:
        try:
            self.send_line(b"EXIT", time.monotonic() + grace)
        except ChannelFailure:
            pass
        self._close_pipes()
        self._kill_group()  # always contain the whole cgroup, even after a clean exit

    def _close_pipes(self) -> None:
        for fd in (self._in, self._out):
            try:
                os.close(fd)
            except OSError:
                pass
        self._in = self._out = -1
