"""Scripted Lab 0 agent: an untrusted, separate OS process.

It imports nothing from the Fitrah runtime. Protocol over stdin/stdout:
  PROGRAM <json list>   first line, the agent's fixed program (from its parent)
  NEXT                  send the next request from the program
  <json>                R's response to the last request (recorded, not trusted)
  EXIT                  terminate
Run with `python -I` so nothing from the working directory is imported.
"""
import json
import sys


def main() -> None:
    program = []
    responses = []
    for line in sys.stdin:
        line = line.rstrip("\n")
        if line.startswith("PROGRAM "):
            program = json.loads(line[len("PROGRAM "):])
        elif line == "NEXT":
            req = program.pop(0) if program else {"op": "noop"}
            sys.stdout.write(json.dumps(req, sort_keys=True) + "\n")
            sys.stdout.flush()
        elif line == "EXIT":
            break
        elif line:
            responses.append(line)


if __name__ == "__main__":
    main()
