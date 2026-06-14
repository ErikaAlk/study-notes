#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_hero.py — composite the README hero banner from REAL screenshots.

Dark background, a real desktop screenshot in a browser frame (center) and a real
mobile screenshot in a phone frame (right, overlapping), with a tagline and
selling-point pills on the left. The layout is built as HTML and screenshotted with
headless Chrome so the real PNGs are pixel-accurate and the Chinese copy is crisp
(unlike text-to-image). Reproducible — always from real run artifacts.

Usage:  python scripts/make_hero.py
Output: assets/hero.png  (1280x640)
"""
import base64
import os
import subprocess
import sys

CHROME = next((p for p in [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
] if os.path.exists(p)), None)

DESKTOP_SRC = "examples/重积分应用与含参积分（MODE-B·作业反推章节笔记）.html"
MOBILE_PNG = "assets/mobile.png"


def shot(url, out, size, budget=10000):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", f"--virtual-time-budget={budget}",
                    f"--window-size={size}", f"--screenshot={os.path.abspath(out)}", url],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def main():
    if CHROME is None:
        sys.exit("no Chrome/Edge found")
    os.makedirs("assets", exist_ok=True)

    # 1. real desktop capture (top of a MODE-B page: header → formula box → example)
    dtmp = "assets/_hero_desktop.png"
    shot("file:///" + os.path.abspath(DESKTOP_SRC).replace("\\", "/"), dtmp, "1180,1500")
    if not os.path.exists(MOBILE_PNG):
        subprocess.run([sys.executable, "scripts/make_mobile_shot.py"], check=True)

    desk, mob = b64(dtmp), b64(MOBILE_PNG)
    hero = "assets/_hero_layout.html"
    with open(hero, "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html><meta charset="utf-8">
<style>
  *{{margin:0;box-sizing:border-box;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
  body{{width:1280px;height:640px;overflow:hidden;
       background:radial-gradient(1200px 700px at 78% 18%,#2a2550 0%,#171627 48%,#0e0d18 100%);color:#e8e6de}}
  .wrap{{display:flex;height:100%;align-items:center;padding:0 56px;gap:24px}}
  .left{{width:430px;flex:none}}
  .kicker{{font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:#AFA9EC;font-weight:700;margin-bottom:14px}}
  h1{{font-size:42px;line-height:1.18;font-weight:800;letter-spacing:-.5px}}
  h1 .hl{{color:#7F77DD}}
  .sub{{margin-top:16px;font-size:16px;line-height:1.7;color:#a8a69e}}
  .pills{{margin-top:22px;display:flex;flex-wrap:wrap;gap:8px}}
  .pill{{font-size:12.5px;font-weight:600;padding:6px 13px;border-radius:20px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05)}}
  .p1{{color:#AFA9EC}} .p2{{color:#5DCAA5}} .p3{{color:#EF9F27}} .p4{{color:#F0997B}}
  .stage{{position:relative;flex:1;height:100%}}
  .browser{{position:absolute;left:8px;top:96px;width:560px;border-radius:12px;overflow:hidden;
           box-shadow:0 24px 60px rgba(0,0,0,.55);border:1px solid rgba(255,255,255,.08)}}
  .bar{{height:30px;background:#201f33;display:flex;align-items:center;gap:7px;padding:0 13px}}
  .dot{{width:11px;height:11px;border-radius:50%}} .r{{background:#ff5f57}} .y{{background:#febc2e}} .g{{background:#28c840}}
  .browser img{{display:block;width:100%}}
  .phone{{position:absolute;right:4px;top:150px;width:212px;border-radius:26px;padding:8px;
         background:#2a2842;box-shadow:0 22px 50px rgba(0,0,0,.6);border:1px solid rgba(255,255,255,.1)}}
  .phone img{{display:block;width:100%;border-radius:18px}}
</style>
<div class="wrap">
  <div class="left">
    <div class="kicker">Study Notes · Agent Skill</div>
    <h1>一章课本或一份作业，<br>变成<span class="hl">考前想收藏</span>的<br>那一个 HTML</h1>
    <div class="sub">KaTeX 数学 · 彩色分区 · 可折叠推导 · 盲解双算核验 — 单个自包含文件，零依赖即开即读。</div>
    <div class="pills">
      <span class="pill p1">PDF → 学习笔记</span>
      <span class="pill p2">作业 → 章节笔记</span>
      <span class="pill p3">作业 → 全解</span>
      <span class="pill p4">KaTeX · 可折叠 · 深色模式</span>
    </div>
  </div>
  <div class="stage">
    <div class="browser"><div class="bar"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span></div><img src="{desk}"></div>
    <div class="phone"><img src="{mob}"></div>
  </div>
</div>""")
    shot("file:///" + os.path.abspath(hero).replace("\\", "/"), "assets/hero.png", "1280,640", budget=4000)
    os.remove(dtmp)
    os.remove(hero)
    from PIL import Image
    print(f"wrote assets/hero.png  {Image.open('assets/hero.png').size}")


if __name__ == "__main__":
    main()
