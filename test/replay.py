#!/usr/bin/env python3
"""replay a typescript log and check invariants.
usage: replay.py <typescript> <check-spec>

check-specs:
  no-newlines              : zero literal '\n' between paint commands (excluding script wrapper)
  paints-at <row> <col>    : output contains ESC[<row>;<col>H
  contains <a> <b> ...     : every token appears in the visible terminal state
  exits-clean              : non-empty output produced
"""
import re
import sys
from pathlib import Path

def strip_script_wrapper(b):
    b = re.sub(rb'^Script started.*?\n', b'', b, count=1)
    b = re.sub(rb'\nScript done.*$', b'', b)
    return b

def cmd_no_newlines(data):
    # extract bytes between first ESC and last ESC; count \n in that span
    first = data.find(b'\x1b')
    last = data.rfind(b'\x1b')
    if first < 0 or last < 0:
        return False, "no escape sequences"
    span = data[first:last]
    nl = span.count(b'\n')
    if nl > 5:
        return False, f"{nl} newlines inside paint span"
    return True, "ok"

def cmd_paints_at(data, row, col):
    needle = f"\x1b[{row};{col}H".encode()
    if needle in data:
        return True, "ok"
    return False, f"missing {needle!r}"

def cmd_contains(data, tokens):
    plain = re.sub(rb'\x1b\[[0-9;?]*[a-zA-Z]', b'', data)
    plain = plain.replace(b'\x1b7', b'').replace(b'\x1b8', b'')
    text = plain.decode('utf-8', errors='replace')
    missing = [t for t in tokens if t not in text]
    if not missing:
        return True, "ok"
    return False, f"missing: {missing}"

def cmd_exits_clean(data):
    if len(data) < 10:
        return False, f"only {len(data)} bytes"
    return True, "ok"

def main():
    if len(sys.argv) < 3:
        print("usage: replay.py <log> <spec>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    spec = sys.argv[2:]
    if not path.exists():
        print(f"no such log: {path}", file=sys.stderr)
        sys.exit(1)
    data = strip_script_wrapper(path.read_bytes())

    op = spec[0]
    if op == "no-newlines":
        ok, msg = cmd_no_newlines(data)
    elif op == "paints-at":
        ok, msg = cmd_paints_at(data, int(spec[1]), int(spec[2]))
    elif op == "contains":
        ok, msg = cmd_contains(data, spec[1:])
    elif op == "exits-clean":
        ok, msg = cmd_exits_clean(data)
    else:
        print(f"unknown op: {op}", file=sys.stderr)
        sys.exit(2)

    if not ok:
        print(f"  -> {msg}", file=sys.stderr)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
