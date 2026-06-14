#!/usr/bin/env bash
# make_showcase.sh — regenerate every README asset from REAL example outputs.
#
# Usage:   bash scripts/make_showcase.sh
#
# Produces (always from real run artifacts in examples/ — never a mocked page):
#   assets/hero.png             composite banner (desktop + phone + tagline)
#   assets/demo.gif             smooth scroll-through of a MODE-B page
#   assets/mobile.png           true 390px mobile view (iframe-wrapper renderer)
#   assets/toc-desktop.png      MODE-A structure: themed header + hierarchical TOC
#   assets/examples-desktop.png MODE-B content: formula box + worked examples + answer boxes
#
# Needs Chrome or Edge + Python with Pillow.  KaTeX renders during the
# virtual-time budget, so no manual wait is required.
set -euo pipefail
cd "$(dirname "$0")/.."

BROWSER=""
for c in "/c/Program Files/Google/Chrome/Application/chrome.exe" \
         "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
         "$(command -v google-chrome || true)" "$(command -v chromium || true)"; do
  [ -n "$c" ] && [ -e "$c" ] && BROWSER="$c" && break
done
[ -n "$BROWSER" ] || { echo "no Chrome/Edge found"; exit 1; }
PY="$(command -v python || command -v py || command -v python3)"
mkdir -p assets

A="examples/动力学学习笔记（MODE-A·学习笔记）.html"
B="examples/重积分应用与含参积分（MODE-B·作业反推章节笔记）.html"
url(){ echo "file:///$(command -v cygpath >/dev/null 2>&1 && cygpath -m "$(realpath "$1")" || realpath "$1")"; }
winpath(){ command -v cygpath >/dev/null 2>&1 && cygpath -w "$PWD/$1" || echo "$PWD/$1"; }

shot(){ # shot <out> <WxH> <url>
  "$BROWSER" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --virtual-time-budget=10000 --window-size="$2" --screenshot="$(winpath "$1")" "$3" 2>/dev/null
  echo "wrote $1"
}

# 1. MODE-A structure shot (header + hierarchical colour-coded TOC)
shot "assets/toc-desktop.png" "1280,1700" "$(url "$A")"

# 2. MODE-B content shot — full capture, then crop the worked-examples band with PIL
shot "assets/_full_b.png" "1280,4200" "$(url "$B")"
"$PY" - <<'PYCROP'
from PIL import Image
im = Image.open("assets/_full_b.png").convert("RGB")
# crop the formula-box + worked-examples band (skip the long TOC in the middle)
im.crop((0, 1180, 1280, min(3380, im.height))).save("assets/examples-desktop.png")
import os; os.remove("assets/_full_b.png")
print("wrote assets/examples-desktop.png", Image.open("assets/examples-desktop.png").size)
PYCROP

# 3. true mobile view
"$PY" scripts/make_mobile_shot.py

# 4. demo GIF
"$PY" scripts/make_demo_gif.py

# 5. composite hero
"$PY" scripts/make_hero.py

echo "--- assets ---"; ls -la assets/
