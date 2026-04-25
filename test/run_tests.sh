#!/bin/bash
# zzz test harness. runs each test in a 100x30 PTY, replays via pyte,
# checks invariants. exit 0 on pass, 1 on fail.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZZZ="$ROOT/zzz"
SAMPLE="$ROOT/examples/toru.zzz"
TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

PASS=0
FAIL=0

check() {
    local name="$1" cmd="$2" want="$3"
    local out="$TMP/$name.log"
    rm -f "$out"
    eval "TERM=xterm-256color script -q -c \"stty cols 100 rows 30; $cmd\" \"$out\"" </dev/null >/dev/null 2>&1 || true
    if python3 "$ROOT/test/replay.py" "$out" $want; then
        echo "  pass  $name"
        PASS=$((PASS+1))
    else
        echo "  FAIL  $name"
        FAIL=$((FAIL+1))
    fi
}

[ ! -f "$SAMPLE" ] && { echo "missing $SAMPLE"; exit 1; }
[ ! -x "$ZZZ" ] && { echo "missing $ZZZ"; exit 1; }

echo "zzz tests"

# pin must paint glyphs at the requested position and emit zero literal newlines
check "pin-no-newlines" \
    "timeout 1 $ZZZ pin $SAMPLE 5 10 2 24" \
    "no-newlines"

# pin must paint at (row, col)
check "pin-position" \
    "timeout 1 $ZZZ pin $SAMPLE 5 10 2 24" \
    "paints-at 5 10"

# pin must restore cursor (DECRC) so external writes stay where the writer left them
check "pin-cursor-safe" \
    "(echo BEFORE; timeout 1 $ZZZ pin $SAMPLE 1 50 2 24; echo AFTER) | cat" \
    "contains BEFORE AFTER"

# play must complete one full loop and exit
check "play-loops-once" \
    "timeout 3 $ZZZ play $SAMPLE 1 24" \
    "exits-clean"

# info dumps header info without crashing
check "info-runs" \
    "$ZZZ info $SAMPLE" \
    "contains frames fps source"

echo
echo "  $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
