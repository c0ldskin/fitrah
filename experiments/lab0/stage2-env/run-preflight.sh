#!/usr/bin/env bash
# Stage 2 preflight (section 9): static checks as the runtime user, dynamic probe as the agent user.
# Read-only. Run as the admin user:   bash run-preflight.sh
set -uo pipefail
R=/srv/fitrah/runtime
OUT="$HOME/stage2-preflight"
mkdir -p "$OUT"
stamp=$(date +%Y%m%dT%H%M%S)

echo "==> Agent-side probe as fitrah-agent"
sudo -u fitrah-agent -H python3 -I /srv/fitrah/agent-probe/agent_probe.py /srv/fitrah/agent-probe/stage2.json > "/tmp/agent-probe-$stamp.json"
cat "/tmp/agent-probe-$stamp.json" | tee "$OUT/agent-probe-$stamp.json"
chmod 0644 "/tmp/agent-probe-$stamp.json"

echo; echo "==> S65 descendant containment as fitrah-runtime, through fitrah-agentctl (TC-21)"
sudo -u fitrah-runtime -H bash -c "cd '$R/fitrah' && PYTHONPATH=src python3 src/stage2/s65.py /srv/fitrah/stage2.json --out /tmp/s65-$stamp.json"
sudo cp "/tmp/s65-$stamp.json" "$OUT/" && sudo chown "$USER" "$OUT/s65-$stamp.json"

echo; echo "==> Preflight as fitrah-runtime (P06, P07 from the probe, TC-20; P08 from S65, TC-21)"
sudo -u fitrah-runtime -H bash -c "cd '$R/fitrah' && PYTHONPATH=src python3 src/stage2/preflight.py /srv/fitrah/stage2.json --probe /tmp/agent-probe-$stamp.json --s65 /tmp/s65-$stamp.json --out /tmp/preflight-$stamp.json"
sudo cp "/tmp/preflight-$stamp.json" "$OUT/" 2>/dev/null && sudo chown "$USER" "$OUT/preflight-$stamp.json"

echo; echo "==> Environment facts"
{ echo "kernel: $(uname -r)"; echo "os: $(. /etc/os-release; echo "$PRETTY_NAME")"; echo "python: $(python3 --version)";
  echo "cgroup: $(stat -fc %T /sys/fs/cgroup)";
  echo "cgroup.kill available: $([ -e /sys/fs/cgroup/system.slice/cgroup.kill ] && echo yes || echo no)";
  echo "cgroup controllers: $(cat /sys/fs/cgroup/cgroup.controllers)"; echo "init: $(ps -p 1 -o comm=)"; ip -br addr 2>/dev/null || cat /proc/net/route; } | tee "$OUT/environment-$stamp.txt"
echo; echo "==> Containment TCB (TC-21)"
{ sha256sum /usr/local/lib/fitrah/agentctl.py /usr/local/lib/fitrah/agents/* /etc/fitrah/agentctl.json /etc/systemd/system/fitrah*;
  systemctl show fitrah-agentctl.service -p ControlGroup -p Delegate -p User -p ActiveState;
  ls -l /run/fitrah-agentctl.sock; ls -ld /sys/fs/cgroup/fitrah.slice/fitrah-agentctl.service/agents 2>&1;
  sudo journalctl -u fitrah-agentctl.service --no-pager -n 20 -o cat; } | tee "$OUT/tcb-$stamp.txt"
echo; echo "Reports in $OUT"
