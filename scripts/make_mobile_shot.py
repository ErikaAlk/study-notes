#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_mobile_shot.py — a CORRECT mobile screenshot of a study-notes page.

Headless Chrome misrenders a narrow top-level viewport on high-DPI displays
(it lays the page out wider than the window and clips the right edge). A real
browser at 390px renders the mobile layout perfectly. To get that correctness
reproducibly, render a desktop-width wrapper that embeds the notes HTML in a
390px <iframe>: headless renders the wide top-level fine, the 390px sub-frame
forces the true mobile layout, then we crop the iframe region.

Usage:  python scripts/make_mobile_shot.py [examples/<notes>.html] [assets/mobile.png] [iframe_height]
"""
import os
import subprocess
import sys

from PIL import Image

HTML = sys.argv[1] if len(sys.argv) > 1 else "examples/重积分应用与含参积分（MODE-B·作业反推章节笔记）.html"
OUT = sys.argv[2] if len(sys.argv) > 2 else "assets/mobile.png"
IFRAME_H = int(sys.argv[3]) if len(sys.argv) > 3 else 1700
MW = 390

CHROME = next((p for p in [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
] if os.path.exists(p)), None)


def main():
    if CHROME is None:
        sys.exit("no Chrome/Edge found")
    src = os.path.basename(HTML)
    wrapper = os.path.join(os.path.dirname(HTML) or ".", "_mobile_wrap.html")
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8">'
                '<body style="margin:0;background:#111">'
                f'<iframe src="{src}" style="width:{MW}px;height:{IFRAME_H}px;'
                'border:0;display:block" scrolling="no"></iframe>')
    cap = OUT + ".cap.png"
    url = "file:///" + os.path.abspath(wrapper).replace("\\", "/")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--virtual-time-budget=12000",
                    f"--window-size={MW + 60},{IFRAME_H + 40}",
                    f"--screenshot={os.path.abspath(cap)}", url],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    im = Image.open(cap).convert("RGB")
    im.crop((0, 0, MW, min(IFRAME_H, im.height))).save(OUT)
    os.remove(cap)
    os.remove(wrapper)
    print(f"wrote {OUT}  {Image.open(OUT).size}")


if __name__ == "__main__":
    main()
