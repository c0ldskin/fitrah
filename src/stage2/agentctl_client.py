"""R's side of the fitrah-agentctl protocol (TC-21). Runs as the runtime user, unprivileged."""
from __future__ import annotations

import json
import os
import socket

DEFAULT_SOCKET = "/run/fitrah-agentctl.sock"


class HelperRefused(Exception):
    pass


class AgentCtl:
    def __init__(self, path: str = DEFAULT_SOCKET, timeout: float = 15.0):
        self.path, self.timeout = path, timeout

    def request(self, req: dict) -> tuple[dict, list[int]]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout)
            s.connect(self.path)
            s.sendall(json.dumps(req).encode() + b"\n")
            msg, fds, _, _ = socket.recv_fds(s, 65536, 2)
            while not msg.endswith(b"\n"):
                more = s.recv(65536)
                if not more:
                    break
                msg += more
        reply = json.loads(msg)
        if not reply.get("ok"):
            for fd in fds:
                os.close(fd)
            raise HelperRefused(reply.get("error", "refused"))
        return reply, fds

    def launch(self, agent_id: str, program: str) -> tuple[int, int, int]:
        """Returns (pid, fd for the agent's stdin, fd for the agent's stdout)."""
        reply, fds = self.request({"op": "launch", "agent_id": agent_id, "program": program})
        if len(fds) != 2:
            raise HelperRefused("helper did not pass two pipe descriptors")
        return reply["pid"], fds[0], fds[1]

    def terminate(self, agent_id: str) -> dict:
        return self.request({"op": "terminate", "agent_id": agent_id})[0]

    def census(self, agent_id: str) -> list[int]:
        return self.request({"op": "census", "agent_id": agent_id})[0]["pids"]
