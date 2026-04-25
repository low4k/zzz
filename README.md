# zzz

animated colored ASCII art for the terminal, rendered from real GIFs.

```
zzz render in.gif out.zzz
zzz play out.zzz
zzz loop out.zzz
```

what it does:

1. takes a GIF, splits it into frames
2. removes the background (corner-sample chroma key — turn it off with `--keep-bg`)
3. maps each pixel to a character based on brightness, plus a 24-bit ANSI color
4. dumps it all into a `.zzz` file
5. plays it back in your terminal at the original frame rate

`.zzz` files are plain text. they hold a tiny JSON header and the pre-rendered ANSI for each frame, so playback is just `read → print → sleep`.

## install

needs `python3` with `Pillow`, and the [rock](https://github.com/) interpreter.

```
pip install Pillow
```

drop the `zzz` repo somewhere on your `PATH`, or just call `./zzz` from the checkout.

## usage

```
zzz render <gif> <out.zzz> [-w 90] [-H 36] [-t 60] [--keep-bg] [--bg R,G,B]
zzz play   <file.zzz> [loops] [fps]
zzz loop   <file.zzz>
zzz info   <file.zzz>
```

flags:

- `-w` / `-H` — output width / max height in cells. defaults: 90 × 36.
- `-t` — chroma-key tolerance. higher = more pixels treated as background. default 60.
- `--keep-bg` — skip background removal entirely.
- `--bg R,G,B` — force a specific background color instead of corner-sampling.

playback:

- `loops` defaults to 1. pass 0 (or use `loop`) for infinite.
- `fps` overrides the GIF's native frame rate.

## file format

```
ZZZ1
{"v":1,"src":"input.gif","w":90,"h":36,"fps":24,"frames":116,"delays_ms":[...],"bg_removed":true}
\x1eFRAME
<ansi-encoded frame>
\x1eFRAME
<ansi-encoded frame>
...
\x1eEND
```

each frame body is just a block of pre-rendered ANSI text, ready to print.

## tips

- darker terminal themes look much better
- truecolor terminal required (most modern ones; check `echo $COLORTERM`)
- if the subject blends with the background, render with `--keep-bg` and use `--bg R,G,B` to nuke a specific color instead
- for the smoothest playback, render at the actual cell aspect of your terminal — most are about 2:1 (height:width) which is what zzz assumes
