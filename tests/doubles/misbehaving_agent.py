"""Scripted RT-02 test double: one fixed channel misbehaviour, chosen by argv[1].

Not an arbitrary-code attacker. It touches no files, network or OS settings; it
only misbehaves on its own stdin/stdout so that R's bounds can be tested.
Every mode ends by itself (sleeps are bounded) even if R never kills it.
  stall    read PROGRAM, then on NEXT never answer
  partial  on NEXT send part of a request with no newline, then go silent
  flood    on NEXT stream bytes with no newline beyond R's size bound
  exit     on NEXT exit without answering
  deaf     never read stdin at all
  talk_deaf  write one fixed, valid write request at start, then never read stdin
             (used for the response-phase regression, TC-19)
"""
import sys
import time

mode = sys.argv[1]
LIMIT = 30  # seconds; a bound on the double itself

if mode == "deaf":
    time.sleep(LIMIT)
    sys.exit(0)

if mode == "talk_deaf":
    sys.stdout.buffer.write(b'{"op": "invoke", "action": "write", "resource": "vault", '
                            b'"args": {"file": "ledger.txt", "data": "tc19"}}\n')
    sys.stdout.buffer.flush()
    time.sleep(LIMIT)
    sys.exit(0)

out = sys.stdout.buffer
for line in sys.stdin.buffer:
    if line.startswith(b"PROGRAM "):
        continue
    if line.strip() == b"NEXT":
        if mode == "stall":
            time.sleep(LIMIT)
        elif mode == "partial":
            out.write(b'{"op": "invoke", "action": "re')
            out.flush()
            time.sleep(LIMIT)
        elif mode == "flood":
            chunk = b"x" * 65536
            for _ in range(48):  # 3 MiB, beyond the 1 MiB line bound
                try:
                    out.write(chunk)
                    out.flush()
                except BrokenPipeError:
                    break
            time.sleep(LIMIT)
        elif mode == "exit":
            sys.exit(0)
        break
