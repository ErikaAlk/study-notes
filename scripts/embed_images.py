#!/usr/bin/env python3
"""embed_images.py — keep study-notes HTML standalone by base64-inlining images.

Three subcommands:

  datauri <img>        Print a data: URI for one image. Paste it into an
                       <img src="..."> in the HTML (MODE C figures).

  inline <html>        Replace every LOCAL <img src="file.png"> in an HTML file
                       with a base64 data: URI, so the final file is fully
                       self-contained. (Skips srcs that are already data:/http(s).)

  tidy <img>           Prep a PHOTO/SCREENSHOT for embedding: auto-deskew (a phone
                       photo of a page is tilted a few degrees), trim the dead
                       margins, and downscale to a sane width. Run this BEFORE
                       datauri on any photo — a raw photo embedded as-is is
                       crooked and fills a whole screen. Eyeball the output.

datauri/inline are pure standard library. tidy needs numpy + opencv
(both already present wherever the OCR stack rapidocr-onnxruntime is installed).
"""
import argparse
import base64
import mimetypes
import os
import re
import sys

mimetypes.add_type("image/svg+xml", ".svg")


def to_data_uri(path):
    if not os.path.exists(path):
        sys.exit(f"Image not found: {path}")
    mime, _ = mimetypes.guess_type(path)
    if mime is None:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = f"image/{ext or 'png'}"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def cmd_datauri(args):
    uri = to_data_uri(args.image)
    print(uri)
    kb = (len(uri) * 3) // 4 // 1024
    sys.stderr.write(f"[{args.image}: ~{kb} KB base64]\n")


_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*)(["\'])(.*?)\2', re.IGNORECASE | re.DOTALL)


def cmd_inline(args):
    if not os.path.exists(args.html):
        sys.exit(f"HTML not found: {args.html}")
    base_dir = os.path.dirname(os.path.abspath(args.html))
    with open(args.html, "r", encoding="utf-8") as f:
        html = f.read()

    stats = {"inlined": 0, "skipped_remote": 0, "missing": 0}

    def repl(m):
        prefix, quote, src = m.group(1), m.group(2), m.group(3)
        low = src.strip().lower()
        if low.startswith(("data:", "http:", "https:", "//")):
            stats["skipped_remote"] += 1
            return m.group(0)
        img_path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if not os.path.exists(img_path):
            stats["missing"] += 1
            sys.stderr.write(f"  ! missing local image, left as-is: {src}\n")
            return m.group(0)
        uri = to_data_uri(img_path)
        stats["inlined"] += 1
        return f"{prefix}{quote}{uri}{quote}"

    new_html = _SRC_RE.sub(repl, html)
    out = args.out or args.html
    with open(out, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"Inlined {stats['inlined']} image(s) -> {out}  "
          f"(skipped remote/data: {stats['skipped_remote']}, missing: {stats['missing']})")
    if stats["missing"]:
        sys.exit(1)


# ---------------------------------------------------------------------------
# tidy — deskew + trim + downscale a photo/screenshot before embedding
# ---------------------------------------------------------------------------
# A phone photo of a textbook page is tilted a few degrees, ringed with dead
# margin, and 3000+px tall — embedded as-is it renders crooked and fills the
# whole screen. tidy fixes all three DETERMINISTICALLY (no eyeballed rotation
# or crop): the skew angle is found by projection profile (the angle that makes
# text/figure rows sharpest), the crop is the bounding box of the ink.

def _lazy_cv():
    try:
        import numpy as np
        import cv2
        return np, cv2
    except ImportError:
        sys.exit("tidy needs numpy + opencv. Run: pip install numpy opencv-python "
                 "--break-system-packages -q  (already present with rapidocr-onnxruntime)")


def _imread(path, np, cv2):
    """cv2.imread silently fails on non-ASCII (中文) Windows paths — decode via bytes."""
    if not os.path.exists(path):
        sys.exit(f"Image not found: {path}")
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"Could not decode image: {path}")
    return img


def _imwrite(path, img, cv2):
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        sys.exit(f"Could not encode image: {path}")
    buf.tofile(path)


def _bg_color(img, np):
    """Background estimate = median of the 1px border (paper, not ink)."""
    edges = np.concatenate([img[0, :], img[-1, :], img[:, 0], img[:, -1]])
    return [int(v) for v in np.median(edges, axis=0)]


def _ink_mask(gray, np, cv2):
    """Otsu-threshold ink (photos have grey paper, a fixed cutoff misfires)."""
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return ink


def _profile_score(prof, np):
    """Sharpness of a horizontal projection profile: sum of squared adjacent
    differences. Maximal when ink rows are level (deskewed) — the classic
    projection-profile deskew objective."""
    d = prof[1:] - prof[:-1]
    return float((d * d).sum())


def _estimate_skew(gray, np, cv2, limit=7.0):
    """Angle (deg, CCW-positive) that levels the ink rows; 0.0 if nothing to fix.
    Small tilts only — beyond ±limit the tilt is probably intentional content."""
    h, w = gray.shape
    s = 900.0 / max(h, w)
    if s < 1.0:
        gray = cv2.resize(gray, (max(1, int(w * s)), max(1, int(h * s))),
                          interpolation=cv2.INTER_AREA)
    ink = (_ink_mask(gray, np, cv2) > 0).astype(np.float32)
    if ink.sum() < 50:          # blank image — nothing to align on
        return 0.0
    ch, cw = ink.shape

    def score(angle):
        M = cv2.getRotationMatrix2D((cw / 2, ch / 2), angle, 1.0)
        r = cv2.warpAffine(ink, M, (cw, ch))
        return _profile_score(r.sum(axis=1), np)

    best = 0.0
    for step, span in ((0.5, limit), (0.1, 0.6)):
        cands = np.arange(best - span, best + span + 1e-9, step)
        best = float(max(cands, key=score))
    if abs(best) >= limit or abs(best) < 0.3:   # runaway / not worth resampling
        return 0.0
    return best


def _rotate(img, angle, np, cv2):
    """Rotate on an expanded canvas (corners kept), border filled with paper color."""
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(img, M, (nw, nh), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=_bg_color(img, np))


def _trim_bbox(gray, np, cv2, margin):
    """Bounding box of the ink + margin, ignoring single-speck rows/cols."""
    ink = _ink_mask(gray, np, cv2)
    min_px = 3 * 255                       # a row/col needs >=3 ink px to count
    rows = np.where(ink.sum(axis=1) > min_px)[0]
    cols = np.where(ink.sum(axis=0) > min_px)[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    h, w = gray.shape
    return (max(0, int(rows[0]) - margin), min(h, int(rows[-1]) + 1 + margin),
            max(0, int(cols[0]) - margin), min(w, int(cols[-1]) + 1 + margin))


def _edge_cut_edges(gray, np, cv2, min_run=12):
    """Names of image edges that content RUNS ALONG — the screenshot/photo itself probably
    cut the figure there; tidy cannot restore what the source never captured. Only judged
    on light-background images (a dark screenshot's background would read as 'ink' on
    every edge and drown the signal in false positives)."""
    ink = _ink_mask(gray, np, cv2) > 0
    if ink.mean() > 0.35:      # dark/cluttered background — signal unusable, stay quiet
        return []
    out = []
    for name, strip in (("top", ink[:2, :].any(0)), ("bottom", ink[-2:, :].any(0)),
                        ("left", ink[:, :2].any(1)), ("right", ink[:, -2:].any(1))):
        best = cur = 0
        for v in strip:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        if best >= min_run:
            out.append(name)
    return out


def cmd_tidy(args):
    np, cv2 = _lazy_cv()
    img = _imread(args.image, np, cv2)
    h0, w0 = img.shape[:2]
    steps = []

    cut = _edge_cut_edges(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), np, cv2)
    if cut:
        print(f"WARNING: content touches the {'/'.join(cut).upper()} edge(s) of the SOURCE "
              "image -- the figure may already be cut off in the screenshot/photo itself.")
        print("         tidy cannot restore missing content. If anything the problem mentions "
              "is missing, get a fuller screenshot/photo instead of embedding a half figure.")

    angle = 0.0
    if not args.no_deskew:
        angle = _estimate_skew(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), np, cv2)
        if angle:
            img = _rotate(img, angle, np, cv2)
            steps.append(f"deskewed {angle:+.1f}deg")

    if not args.no_trim:
        box = _trim_bbox(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), np, cv2, args.margin)
        if box:
            y0, y1, x0, x1 = box
            if (y1 - y0) * (x1 - x0) < img.shape[0] * img.shape[1] * 0.98:
                img = img[y0:y1, x0:x1]
                steps.append(f"trimmed to {img.shape[1]}x{img.shape[0]}px")

    if img.shape[1] > args.max_width:
        s = args.max_width / img.shape[1]
        img = cv2.resize(img, (args.max_width, max(1, int(round(img.shape[0] * s)))),
                         interpolation=cv2.INTER_AREA)
        steps.append(f"downscaled to {args.max_width}px wide")

    out = args.out or os.path.splitext(args.image)[0] + "_tidy.png"
    _imwrite(out, img, cv2)
    print(f"tidy {args.image} [{w0}x{h0}px] -> {out} [{img.shape[1]}x{img.shape[0]}px]  "
          f"({'; '.join(steps) or 'no change needed'})")
    print("EYEBALL the output (Read tool) before embedding -- deskew/trim can misjudge a dark "
          "or cluttered photo; if wrong, retry with --no-deskew/--no-trim or use the original.")
    print(f"Next: python3 scripts/embed_images.py datauri {out}")


def main():
    p = argparse.ArgumentParser(description="Base64-inline images to keep HTML standalone.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("datauri", help="print a data: URI for one image")
    pd.add_argument("image")
    pd.set_defaults(func=cmd_datauri)

    pi = sub.add_parser("inline", help="inline all local <img src> in an HTML file")
    pi.add_argument("html")
    pi.add_argument("-o", "--out", help="write to a new file (default: overwrite in place)")
    pi.set_defaults(func=cmd_inline)

    pt = sub.add_parser("tidy",
                        help="deskew + trim + downscale a photo/screenshot before embedding")
    pt.add_argument("image")
    pt.add_argument("-o", "--out", help="output image (default: <name>_tidy.png)")
    pt.add_argument("--max-width", type=int, default=1400,
                    help="downscale wider images to this width (default: 1400)")
    pt.add_argument("--margin", type=int, default=12,
                    help="px margin kept around the trimmed ink (default: 12)")
    pt.add_argument("--no-deskew", action="store_true", help="skip the rotation fix")
    pt.add_argument("--no-trim", action="store_true", help="skip the margin trim")
    pt.set_defaults(func=cmd_tidy)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
