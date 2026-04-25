#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from PIL import Image, ImageSequence

DEFAULT_W = 90
DEFAULT_H = 36

UPPER = "\u2580"
LOWER = "\u2584"

def detect_bg(img):
    img = img.convert("RGB")
    w, h = img.size
    px = img.load()
    samples = []
    band = max(1, min(w, h) // 12)
    for x in range(w):
        for y in list(range(band)) + list(range(h - band, h)):
            samples.append(px[x, y])
    for y in range(h):
        for x in list(range(band)) + list(range(w - band, w)):
            samples.append(px[x, y])
    bucketed = [(r >> 5 << 5, g >> 5 << 5, b >> 5 << 5) for r, g, b in samples]
    cluster = Counter(bucketed).most_common(1)[0][0]
    matching = [s for s, b in zip(samples, bucketed) if b == cluster]
    n = len(matching) or 1
    return (
        sum(p[0] for p in matching) // n,
        sum(p[1] for p in matching) // n,
        sum(p[2] for p in matching) // n,
    )

def is_bg(px, bg, tol):
    if len(px) == 4 and px[3] < 32:
        return True
    if bg is None:
        return False
    r, g, b = px[:3]
    br, bgr, bb = bg
    return abs(r - br) + abs(g - bgr) + abs(b - bb) < tol

def fit(iw, ih, max_w, max_h):
    aspect = iw / ih
    out_w = max_w
    out_h = max(1, round(max_w / aspect / 2))
    if out_h > max_h:
        out_h = max_h
        out_w = max(1, round(max_h * 2 * aspect))
    if out_w > max_w:
        out_w = max_w
    return out_w, out_h

def render_frame(frame, max_w, max_h, bg, tol, no_bg):
    img = frame.convert("RGBA")
    iw, ih = img.size
    cw, ch = fit(iw, ih, max_w, max_h)
    img = img.resize((cw, ch * 2), Image.LANCZOS)
    px = img.load()

    lines = []
    for cy in range(ch):
        parts = []
        last_fg = None
        last_bg = None
        for cx in range(cw):
            top = px[cx, cy * 2]
            bot = px[cx, cy * 2 + 1]
            top_t = no_bg and is_bg(top, bg, tol)
            bot_t = no_bg and is_bg(bot, bg, tol)

            if top_t and bot_t:
                if last_fg is not None or last_bg is not None:
                    parts.append("\x1b[0m")
                    last_fg = None
                    last_bg = None
                parts.append(" ")
                continue

            if top_t:
                fg = bot[:3]
                if last_bg is not None:
                    parts.append("\x1b[49m")
                    last_bg = None
                if fg != last_fg:
                    parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m")
                    last_fg = fg
                parts.append(LOWER)
            elif bot_t:
                fg = top[:3]
                if last_bg is not None:
                    parts.append("\x1b[49m")
                    last_bg = None
                if fg != last_fg:
                    parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m")
                    last_fg = fg
                parts.append(UPPER)
            else:
                fg = top[:3]
                bc = bot[:3]
                changes = []
                if fg != last_fg:
                    changes.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}")
                    last_fg = fg
                if bc != last_bg:
                    changes.append(f"48;2;{bc[0]};{bc[1]};{bc[2]}")
                    last_bg = bc
                if changes:
                    parts.append("\x1b[" + ";".join(changes) + "m")
                parts.append(UPPER)
        parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines

def gif_frames(path):
    im = Image.open(path)
    delays = []
    frames = []
    for f in ImageSequence.Iterator(im):
        delays.append(f.info.get("duration", 80))
        frames.append(f.copy())
    return frames, delays

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("-w", "--width", type=int, default=DEFAULT_W)
    ap.add_argument("-H", "--height", type=int, default=DEFAULT_H)
    ap.add_argument("-t", "--tol", type=int, default=180)
    ap.add_argument("--keep-bg", action="store_true")
    ap.add_argument("--bg", default=None)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"missing: {src}", file=sys.stderr)
        sys.exit(1)

    frames, delays = gif_frames(src)
    if not frames:
        print("no frames", file=sys.stderr)
        sys.exit(1)

    if args.bg:
        bg = tuple(int(x) for x in args.bg.split(","))
    else:
        bg = detect_bg(frames[0])

    encoded = []
    real_h = 0
    for f in frames:
        lines = render_frame(f, args.width, args.height, bg, args.tol, not args.keep_bg)
        real_h = max(real_h, len(lines))
        encoded.append("\n".join(lines))

    avg_delay = sum(delays) / len(delays)
    fps = max(1, round(1000.0 / max(20, avg_delay)))

    header = {
        "v": 2,
        "src": src.name,
        "w": args.width,
        "h": args.height,
        "rh": real_h,
        "fps": fps,
        "frames": len(encoded),
        "delays_ms": delays,
        "bg_removed": not args.keep_bg,
    }

    with open(args.output, "w", encoding="utf-8") as out:
        out.write("ZZZ1\n")
        out.write(json.dumps(header) + "\n")
        for fr in encoded:
            out.write("\x1eFRAME\n")
            out.write(fr)
            out.write("\n")
        out.write("\x1eEND\n")
    print(f"wrote {args.output}  ({len(encoded)} frames, ~{fps} fps, {real_h} rows)")

if __name__ == "__main__":
    main()
