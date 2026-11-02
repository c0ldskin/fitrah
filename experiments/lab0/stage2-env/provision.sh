#!/usr/bin/env bash
# Provision the Fitrah Lab 0 Stage 2 environment inside the disposable VM (stage2-environment.md).
# Run once, as the admin user:   sudo bash provision.sh
# Creates two non-root identities, the runtime tree with restrictive permissions, a fresh
# Ed25519 key generated inside the VM, and installs the two dependencies offline.
# Runs no attacker code and no scenario.
set -euo pipefail
B="$(cd "$(dirname "$0")" && pwd)"
R=/srv/fitrah/runtime
PROBE=/srv/fitrah/agent-probe
say() { printf '\n==> %s\n' "$*"; }

[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

say "Identities (section 2)"
for u in fitrah-runtime fitrah-agent; do
    id "$u" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$u"
done
# Neither identity may hold sudo or share a group with the other
for u in fitrah-runtime fitrah-agent; do gpasswd -d "$u" sudo >/dev/null 2>&1 || true; done
id fitrah-runtime; id fitrah-agent

say "Runtime tree (section 3)"
install -d -o root -g root -m 0755 /srv/fitrah
install -d -o fitrah-runtime -g fitrah-runtime -m 0750 "$R" "$R/fitrah"
# Code in its own folder, so the Stage 2 key, log, registry and vault sit outside the repository
tar -xzf "$B/fitrah.tar.gz" -C "$R/fitrah"
chown -R fitrah-runtime:fitrah-runtime "$R"
chmod -R go-w "$R"
install -d -o fitrah-runtime -g fitrah-runtime -m 0700 "$R/keys" "$R/logs" "$R/vault"
for f in "$R/logs/stage2.jsonl" "$R/registry.json" "$R/vault/ledger.txt"; do
    [ -e "$f" ] || install -o fitrah-runtime -g fitrah-runtime -m 0600 /dev/null "$f"
done

say "Dependencies, offline, for the runtime user"
# The admin home is not readable by other users, so stage the wheels where the runtime user can read them
install -d -o root -g root -m 0755 /srv/fitrah/wheels
install -o root -g root -m 0644 "$B"/wheels/*.whl /srv/fitrah/wheels/
PIP_WHEEL=$(ls /srv/fitrah/wheels/pip-*.whl | head -1)
sudo -u fitrah-runtime -H python3 "$PIP_WHEEL/pip" install -q --user --break-system-packages \
    --no-index --find-links /srv/fitrah/wheels cryptography==50.0.1 pytest==9.1.1
sudo -u fitrah-runtime -H python3 -c "import cryptography, pytest; print('cryptography', cryptography.__version__, '| pytest', pytest.__version__)"

say "Fresh Ed25519 key, generated here, readable only by the runtime user (section 6)"
if [ ! -s "$R/keys/stage2-signing.seed" ]; then
    sudo -u fitrah-runtime -H bash -c "umask 077; cd '$R/keys' && python3 - <<'PY'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s
k = Ed25519PrivateKey.generate()
seed = k.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption()).hex()
pub = k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()
open('stage2-signing.seed', 'w').write(seed + '\n')
open('stage2-signing.pub', 'w').write(pub + '\n')
PY"
    chmod 0600 "$R/keys/stage2-signing.seed"; chmod 0644 "$R/keys/stage2-signing.pub"
fi
echo "public key fingerprint: $(cut -c1-16 "$R/keys/stage2-signing.pub")"

say "Config and agent-side probe"
grep -v '"_note"' "$R/fitrah/experiments/lab0/stage2-preflight.example.json" \
    | sed 's#"/srv/fitrah/runtime/src"#"/srv/fitrah/runtime/fitrah/src"#' > /srv/fitrah/stage2.json
chmod 0644 /srv/fitrah/stage2.json
install -d -o root -g root -m 0755 "$PROBE"
install -o root -g root -m 0644 "$R/fitrah/src/stage2/agent_probe.py" /srv/fitrah/stage2.json "$PROBE/"

say "Containment helper fitrah-agentctl (TC-21), root-owned"
L=/usr/local/lib/fitrah
install -d -o root -g root -m 0755 "$L" "$L/agents" /etc/fitrah
install -o root -g root -m 0755 "$R/fitrah/src/stage2/agentctl.py" "$L/agentctl.py"
install -o root -g root -m 0644 "$R/fitrah/tests/doubles/s65_descendants.py" "$L/agents/"
cat > /etc/fitrah/agentctl.json <<'JSON'
{"runtime_user": "fitrah-runtime", "agent_user": "fitrah-agent", "socket": "/run/fitrah-agentctl.sock",
 "terminate_timeout_s": 5, "max_agents": 32,
 "programs": {"s65": ["/usr/bin/python3", "-I", "/usr/local/lib/fitrah/agents/s65_descendants.py"]}}
JSON
chmod 0644 /etc/fitrah/agentctl.json
install -o root -g root -m 0644 "$B"/systemd/fitrah.slice "$B"/systemd/fitrah-agentctl.socket \
    "$B"/systemd/fitrah-agentctl.service /etc/systemd/system/
systemctl daemon-reload
systemctl stop fitrah-agentctl.service 2>/dev/null || true
systemctl enable --now fitrah-agentctl.socket
ls -l /run/fitrah-agentctl.sock
sha256sum "$L/agentctl.py" "$L/agents/s65_descendants.py" /etc/fitrah/agentctl.json /etc/systemd/system/fitrah*

say "Done. Next: bash run-preflight.sh"
