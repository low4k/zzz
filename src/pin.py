#!/usr/bin/env python3
"""Pin a .zzz animation at a fixed (row,col) on the terminal.

No trailing newline per frame: writes go through sys.stdout.buffer.write
so they never scroll the host terminal.
"""
import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

ESC = b"\x1b"

def parse_zzz(path):
    raw = Path(path).read_bytes()
    if not raw.startswith(b"ZZZ1\n"):
        sys.stderr.write("not a zzz file\n")
        sys.exit(1)
    body = raw[5:]
    nl = body.index(b"\n")
    header = json.loads(body[:nl].decode("utf-8"))
    rest = body[nl + 1:]
    frames = []
    parts = rest.split(b"\x1eFRAME\n")
    for p in parts[1:]:
        if p.startswith(b"\x1eEND"):
            break
        end = p.find(b"\x1eEND")
        chunk = p[:end] if end >= 0 else p
        if chunk.endswith(b"\n"):
            chunk = chunk[:-1]
        frames.append(chunk)
    return header, frames

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("row", type=int)
    ap.add_argument("col", type=int)
    ap.add_argument("loops", type=int, nargs="?", default=0)
    ap.add_argument("fps", type=int, nargs="?", default=0)
    ap.add_argument("park_row", type=int, nargs="?", default=999)
    args = ap.parse_args()

    header, frames = parse_zzz(args.file)
    if not frames:
        return
    fps = args.fps or header.get("fps", 12)
    delay = 1.0 / max(1, fps)

    out = sys.stdout.buffer
    out.write(ESC + b"[?25l")
    out.flush()

    stop = {"v": False}
    def _sig(*_):
        stop["v"] = True
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    iterations = args.loops if args.loops > 0 else 10**9
    try:
        for _ in range(iterations):
            for fr in frames:
                if stop["v"]:
                    raise KeyboardInterrupt
                lines = fr.split(b"\n")
                # One atomic write per frame: save cursor (DECSC), paint each
                # row at its absolute (row, col), reset attrs, restore cursor
                # (DECRC). Because the whole frame is a single write+flush,
                # other processes writing to the tty cannot interleave between
                # our save and restore. The foreground always keeps full
                # control of the cursor.
                buf = bytearray()
                buf += ESC + b"7"
                for i, line in enumerate(lines):
                    buf += ESC + f"[{args.row + i};{args.col}H".encode()
                    buf += line
                buf += ESC + b"[0m"
                buf += ESC + b"8"
                try:
                    out.write(bytes(buf))
                    out.flush()
                except BrokenPipeError:
                    return
                time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            out.write(ESC + b"[?25h")
            out.flush()
        except Exception:
            pass

if __name__ == "__main__":
    main()
