#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from PIL import Image, ImageSequence

CHARS = " .'`,:;-~+*=oxOX#%@$"
DEFAULT_W = 90
DEFAULT_H = 36

def luma(r, g, b):
    return (0.299 * r + 0.587 * g + 0.114 * b)

def char_for(brightness):
    n = len(CHARS) - 1
    idx = int(round(brightness / 255.0 * n))
    if idx < 0: idx = 0
    if idx > n: idx = n
    return CHARS[idx]

def sample_bg(img):
    w, h = img.size
    pts = [(0,0),(w-1,0),(0,h-1),(w-1,h-1),
           (w//2,0),(w//2,h-1),(0,h//2),(w-1,h//2)]
    rs, gs, bs = [], [], []
    for x, y in pts:
        px = img.getpixel((x, y))
        if len(px) == 4:
            r, g, b, a = px
            if a < 16: continue
        else:
            r, g, b = px[:3]
        rs.append(r); gs.append(g); bs.append(b)
    if not rs: return None
    return (sum(rs)//len(rs), sum(gs)//len(gs), sum(bs)//len(bs))

def is_bg(px, bg, tol):
    if bg is None: return False
    if len(px) == 4 and px[3] < 24: return True
    r, g, b = px[:3]
    br, bg_, bb = bg
    d = abs(r-br) + abs(g-bg_) + abs(b-bb)
    return d < tol

def render_frame(frame, target_w, target_h, bg, tol, no_bg):
    img = frame.convert("RGBA")
    iw, ih = img.size
    aspect = iw / ih
    cell = aspect / 0.5
    out_w = target_w
    out_h = int(target_w / cell)
    if out_h > target_h:
        out_h = target_h
        out_w = int(out_h * cell)
    img = img.resize((out_w, out_h), Image.LANCZOS)

    rows = []
    for y in range(out_h):
        cells = []
        prev = None
        run = []
        for x in range(out_w):
            px = img.getpixel((x, y))
            if no_bg and is_bg(px, bg, tol):
                if prev is not None:
                    cells.append((prev, "".join(run)))
                    prev, run = None, []
                cells.append((None, " "))
                continue
            r, g, b = px[:3]
            ch = char_for(luma(r, g, b))
            key = (r, g, b)
            if key == prev:
                run.append(ch)
            else:
                if prev is not None:
                    cells.append((prev, "".join(run)))
                prev, run = key, [ch]
        if prev is not None:
            cells.append((prev, "".join(run)))
        rows.append(cells)
    return rows

def encode_frame(rows):
    ESC = "\x1b["
    RESET = ESC + "0m"
    parts = []
    for cells in rows:
        line = []
        last = None
        for color, text in cells:
            if color is None:
                if last is not None:
                    line.append(RESET); last = None
                line.append(text)
            else:
                if color != last:
                    r, g, b = color
                    line.append(f"{ESC}38;2;{r};{g};{b}m"); last = color
                line.append(text)
        if last is not None:
            line.append(RESET)
        parts.append("".join(line))
    return "\n".join(parts)

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
    ap.add_argument("-t", "--tol", type=int, default=60)
    ap.add_argument("--keep-bg", action="store_true")
    ap.add_argument("--bg", default=None)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"missing: {src}", file=sys.stderr); sys.exit(1)

    frames, delays = gif_frames(src)
    if not frames:
        print("no frames", file=sys.stderr); sys.exit(1)

    if args.bg:
        bg = tuple(int(x) for x in args.bg.split(","))
    else:
        bg = sample_bg(frames[0].convert("RGBA"))

    encoded = []
    for f in frames:
        rows = render_frame(f, args.width, args.height, bg, args.tol, not args.keep_bg)
        encoded.append(encode_frame(rows))

    avg_delay = sum(delays) / len(delays)
    fps = max(1, round(1000.0 / max(20, avg_delay)))

    header = {
        "v": 1,
        "src": src.name,
        "w": args.width,
        "h": args.height,
        "fps": fps,
        "frames": len(encoded),
        "delays_ms": delays,
        "bg_removed": not args.keep_bg,
    }

    with open(args.output, "w", encoding="utf-8") as out:
        out.write("ZZZ1\n")
        out.write(json.dumps(header) + "\n")
        for i, fr in enumerate(encoded):
            out.write("\x1eFRAME\n")
            out.write(fr)
            out.write("\n")
        out.write("\x1eEND\n")
    print(f"wrote {args.output}  ({len(encoded)} frames, ~{fps} fps)")

if __name__ == "__main__":
    main()
