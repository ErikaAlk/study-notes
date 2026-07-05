#!/usr/bin/env python3
"""Self-contained regression tests for embed_images.py — mainly the `tidy` pipeline
(deskew + trim + downscale) that preps a phone photo/screenshot for embedding.

All fixtures are synthesized in-memory (numpy), no image files or OCR needed.
Run:  python test_embed_images.py     (needs numpy + opencv, same as tidy itself)
"""
import os
import tempfile

import embed_images as e

try:
    import numpy as np
    import cv2
except ImportError:
    print("SKIP  numpy/opencv not installed — tidy tests need them (pip install numpy opencv-python)")
    raise SystemExit(0)


def _page(w=900, h=700):
    """A synthetic 'photographed page': light-grey paper, dark text-like rows."""
    img = np.full((h, w, 3), 235, np.uint8)
    for y in range(120, 560, 60):                       # text rows
        cv2.rectangle(img, (140, y), (760, y + 16), (40, 40, 40), -1)
    cv2.rectangle(img, (300, 580, ), (600, 640), (40, 40, 40), 2)   # a figure box
    return img


def run():
    n = 0

    # 1. a level page needs no deskew (angle below the 0.3 deg action threshold -> 0.0)
    gray = cv2.cvtColor(_page(), cv2.COLOR_BGR2GRAY)
    a = e._estimate_skew(gray, np, cv2)
    assert a == 0.0, f"level page must estimate 0.0, got {a}"
    n += 1

    # 2. a page tilted +2.4 deg is estimated as ~-2.4 (the correcting rotation)
    tilted = e._rotate(_page(), 2.4, np, cv2)
    a = e._estimate_skew(cv2.cvtColor(tilted, cv2.COLOR_BGR2GRAY), np, cv2)
    assert abs(a + 2.4) <= 0.3, f"tilt +2.4deg must estimate ~-2.4, got {a}"
    n += 1

    # 3. a blank image never crashes the estimator (no ink to align on)
    blank = np.full((300, 300), 235, np.uint8)
    assert e._estimate_skew(blank, np, cv2) == 0.0, "blank image must estimate 0.0"
    n += 1

    # 4. _trim_bbox finds the ink bounding box + margin (and ignores lone specks)
    img = np.full((500, 400), 235, np.uint8)
    img[100:200, 50:150] = 30
    img[400, 300] = 30                                  # a 1px speck must not extend the box
    y0, y1, x0, x1 = e._trim_bbox(img, np, cv2, margin=10)
    assert (y0, y1, x0, x1) == (90, 210, 40, 160), f"bad bbox: {(y0, y1, x0, x1)}"
    n += 1

    # 5. end-to-end cmd_tidy: tilted 2000px-wide photo -> deskewed, trimmed, <=1400px wide
    big = cv2.resize(_page(), (2000, 1556), interpolation=cv2.INTER_CUBIC)
    big = e._rotate(big, 3.0, np, cv2)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "题七照片.png")          # non-ASCII path must work on Windows
        e._imwrite(src, big, cv2)
        out = os.path.join(td, "fig_q7.png")

        class A:
            pass
        args = A()
        args.image, args.out = src, out
        args.max_width, args.margin = 1400, 12
        args.no_deskew = args.no_trim = False
        e.cmd_tidy(args)

        got = e._imread(out, np, cv2)
        assert got.shape[1] <= 1400, f"not downscaled: {got.shape}"
        resid = e._estimate_skew(cv2.cvtColor(got, cv2.COLOR_BGR2GRAY), np, cv2)
        assert abs(resid) <= 0.3, f"residual tilt after tidy: {resid}"
        # trimmed: strictly smaller than the no-trim run on BOTH axes — compare with the
        # downscale disabled (post-downscale heights only compare aspect, not size)
        out2, out3 = os.path.join(td, "q7_notrim.png"), os.path.join(td, "q7_trim.png")
        args.max_width = 10**6
        args.out, args.no_trim = out2, True
        e.cmd_tidy(args)
        args.out, args.no_trim = out3, False
        e.cmd_tidy(args)
        raw, trim = e._imread(out2, np, cv2), e._imread(out3, np, cv2)
        assert trim.shape[0] < raw.shape[0] and trim.shape[1] < raw.shape[1], \
            f"margins not trimmed: {trim.shape} vs no-trim {raw.shape}"
        n += 1

        # 6. datauri on the tidy output yields a PNG data URI (the documented next step)
        uri = e.to_data_uri(out)
        assert uri.startswith("data:image/png;base64,"), uri[:40]
        n += 1

    print(f"OK  embed_images tidy tests passed ({n}/{n})")


if __name__ == "__main__":
    run()
