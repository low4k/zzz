#!/usr/bin/env python3
"""denoise a .zzz file.

scans every cell in every frame, clusters the foreground colors used,
then drops any cell whose color is rare/isolated (likely a downsampling
artifact). the result is a cleaner silhouette that holds its shape.

usage: clean.py <in.zzz> <out.zzz> [--min-count N] [--keep-top K]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

UPPER = "\u2580"
LOWER = "\u2584"
SGR = re.compile(r"\x1b\[([0-9;]*)m")

def parse(path):
    raw = Path(path).read_bytes()
    if not raw.startswith(b"ZZZ1\n"):
        sys.exit("not a zzz file")
    body = raw[5:]
    nl = body.index(b"\n")
    header = json.loads(body[:nl].decode())
    rest = body[nl + 1:]
    parts = rest.split(b"\x1eFRAME\n")
    frames = []
    for p in parts[1:]:
        if p.startswith(b"\x1eEND"):
            break
        end = p.find(b"\x1eEND")
        chunk = p[:end] if end >= 0 else p
        if chunk.endswith(b"\n"):
            chunk = chunk[:-1]
        frames.append(chunk.decode("utf-8"))
    return header, frames

def cells(line):
    """yield (fg, bg, glyph) per visible cell."""
    fg = None
    bg = None
    i = 0
    while i < len(line):
        m = SGR.match(line, i)
        if m:
            params = m.group(1).split(";")
            j = 0
            while j < len(params):
                p = params[j]
                if p == "" or p == "0":
                    fg = None
                    bg = None
                    j += 1
                elif p == "38" and j + 4 < len(params) and params[j+1] == "2":
                    fg = (int(params[j+2]), int(params[j+3]), int(params[j+4]))
                    j += 5
                elif p == "48" and j + 4 < len(params) and params[j+1] == "2":
                    bg = (int(params[j+2]), int(params[j+3]), int(params[j+4]))
                    j += 5
                elif p == "39":
                    fg = None
                    j += 1
                elif p == "49":
                    bg = None
                    j += 1
                else:
                    j += 1
            i = m.end()
            continue
        ch = line[i]
        i += 1
        if ch == " ":
            yield (None, None, " ")
        else:
            yield (fg, bg, ch)

def bucket(c):
    if c is None:
        return None
    return (c[0] >> 4 << 4, c[1] >> 4 << 4, c[2] >> 4 << 4)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--min-count", type=int, default=8,
                    help="drop colors that appear in fewer total cells than this")
    ap.add_argument("--keep-top", type=int, default=0,
                    help="if >0, keep only the K most-common color buckets")
    args = ap.parse_args()

    header, frames = parse(args.inp)

    # phase 1: count color usage across all frames
    counts = Counter()
    for fr in frames:
        for line in fr.split("\n"):
            for fg, bg, ch in cells(line):
                if ch == " ":
                    continue
                if fg:
                    counts[bucket(fg)] += 1
                if bg:
                    counts[bucket(bg)] += 1

    if args.keep_top > 0:
        keep = set(b for b, _ in counts.most_common(args.keep_top))
    else:
        keep = set(b for b, n in counts.items() if n >= args.min_count)

    sys.stderr.write(f"colors: total={len(counts)} kept={len(keep)}\n")

    # phase 2: rewrite frames keeping only cells whose colors are in `keep`
    out_frames = []
    for fr in frames:
        new_lines = []
        for line in fr.split("\n"):
            buf = []
            last_fg = None
            last_bg = None
            for fg, bg, ch in cells(line):
                fg_ok = fg is not None and bucket(fg) in keep
                bg_ok = bg is not None and bucket(bg) in keep
                if ch == " " or (not fg_ok and not bg_ok):
                    if last_fg is not None or last_bg is not None:
                        buf.append("\x1b[0m")
                        last_fg = None
                        last_bg = None
                    buf.append(" ")
                    continue
                changes = []
                if fg_ok and fg != last_fg:
                    changes.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}")
                    last_fg = fg
                elif not fg_ok and last_fg is not None:
                    changes.append("39")
                    last_fg = None
                if bg_ok and bg != last_bg:
                    changes.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}")
                    last_bg = bg
                elif not bg_ok and last_bg is not None:
                    changes.append("49")
                    last_bg = None
                if changes:
                    buf.append("\x1b[" + ";".join(changes) + "m")
                # if only one of fg/bg survived we may want to swap glyph
                if not fg_ok and bg_ok:
                    # bg block was the surviving color; render as solid block on bg
                    buf.append(LOWER if ch == UPPER else UPPER)
                else:
                    buf.append(ch)
            buf.append("\x1b[0m")
            new_lines.append("".join(buf))
        out_frames.append("\n".join(new_lines))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("ZZZ1\n")
        f.write(json.dumps(header) + "\n")
        for fr in out_frames:
            f.write("\x1eFRAME\n")
            f.write(fr)
            f.write("\n")
        f.write("\x1eEND\n")
    print(f"wrote {args.out}")

if __name__ == "__main__":
    main()
