"""
extract_images.py — Stage: image extraction for the Surgery_ed8 PDF pipeline.

Extracts, losslessly where possible, every embedded raster figure, composites
known multi-tile split figures into single images, and renders vector-drawn
table diagrams to PNG. Writes everything flat into images/_raw/ plus a
manifest at work/images_manifest.json. Chapter numbers are NOT assigned here
(that depends on a structure.json this stage does not have) — every image is
recorded with its page_index/page_number/xref/kind/rect/file so a later stage
(build_bank.py) can re-file it into chNN/ directories.

Source PDF is opened read-only and never modified.
"""

import json
import re
import statistics
import sys
from collections import Counter

import pymupdf

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SRC_PDF = "/Users/yashvasu/Downloads/Surgery_ed8.pdf"
ROOT = "/Users/yashvasu/Desktop/study/marrow"
RAW_DIR = f"{ROOT}/images/_raw"
MANIFEST_PATH = f"{ROOT}/work/images_manifest.json"

BLANK_XREF = 4398  # confirmed blank full-bleed CMYK plate present on every page

# Multi-tile adjacency detection
TILE_EDGE_TOL = 2.0        # pt — max gap to consider two image rects "abutting"
TILE_OVERLAP_FRAC_MIN = 0.3  # min fraction of the shorter side that must overlap

# Vector-table detection
DRAW_CLUSTER_TOL = 3.0     # pt — gap tolerance for clustering drawing items
MIN_CLUSTER_ITEMS = 5
MIN_TABLE_W = 60.0
MIN_TABLE_H = 12.0
TABLE_RENDER_DPI = 300
TABLE_PAD = 4.0
ANSWERKEY_SHORTFRAC_THRESHOLD = 0.75
AMBIGUOUS_SHORTFRAC_LOW = 0.55  # log-as-ambiguous band below the exclude threshold

SHORT_TOKEN_PAT = re.compile(r'^[a-dA-D]$|^\d{1,4}$')


def log(msg):
    print(msg, flush=True)


_USED_FILENAMES = set()


def dedupe_filename(fname):
    """A handful of pages legitimately place the same xref twice (same
    figure reused for two sub-questions on one page); guard against the
    resulting filename collision rather than silently overwriting."""
    if fname not in _USED_FILENAMES:
        _USED_FILENAMES.add(fname)
        return fname
    stem, dot, ext = fname.rpartition('.')
    n = 2
    while True:
        candidate = f"{stem}_dup{n}.{ext}"
        if candidate not in _USED_FILENAMES:
            _USED_FILENAMES.add(candidate)
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Small geometry helpers (pymupdf's Rect.intersects()/|= special-case
# zero-area rects as "empty" and silently no-op, which breaks on the
# axis-aligned line segments that make up table-grid drawings — so these
# helpers do plain coordinate math instead of using Rect boolean operators)
# ---------------------------------------------------------------------------

def union_find(n):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    return find, union


def manual_union_bbox(rects):
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return pymupdf.Rect(x0, y0, x1, y1)


def rects_touch(r1, r2, tol):
    """Plain AABB overlap-with-tolerance test; safe for zero-area (line) rects."""
    return not (r1.x1 + tol < r2.x0 or r2.x1 + tol < r1.x0 or
                r1.y1 + tol < r2.y0 or r2.y1 + tol < r1.y0)


def tiles_adjacent(r1, r2, tol=TILE_EDGE_TOL, overlap_frac_min=TILE_OVERLAP_FRAC_MIN):
    """True if r1/r2 are two image placements that abut edge-to-edge (same
    logical figure split into separate embedded XObjects), not just two
    unrelated images that happen to be near each other."""
    def yoverlap(a, b):
        return max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))

    def xoverlap(a, b):
        return max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))

    if abs(r1.x1 - r2.x0) <= tol or abs(r2.x1 - r1.x0) <= tol:
        mind = min(r1.height, r2.height) or 1.0
        if yoverlap(r1, r2) >= overlap_frac_min * mind:
            return True
    if abs(r1.y1 - r2.y0) <= tol or abs(r2.y1 - r1.y0) <= tol:
        mind = min(r1.width, r2.width) or 1.0
        if xoverlap(r1, r2) >= overlap_frac_min * mind:
            return True
    return False


# ---------------------------------------------------------------------------
# Raster figures + multi-tile compositing
# ---------------------------------------------------------------------------

def is_confirmed_blank(doc, page, im):
    """Extra safety net beyond the hardcoded BLANK_XREF: a near-full-page
    image with no other images on the page and near-zero pixel variance.
    Only ever excludes a CONFIRMED blank; never guesses."""
    bbox = pymupdf.Rect(im['bbox'])
    pw, ph = page.rect.width, page.rect.height
    if not (bbox.width > 0.95 * pw and bbox.height > 0.95 * ph):
        return False
    try:
        pix = pymupdf.Pixmap(doc, im['xref'])
        if pix.colorspace and pix.colorspace.n > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        # cheap variance sample via pixmap.tobytes-free approach: sample
        # via a shrunk pixmap to keep this fast
        small = pymupdf.Pixmap(pix, max(1, pix.width // 32) or 1, max(1, pix.height // 32) or 1, None)
        samples = small.samples
        if not samples:
            return False
        mean = sum(samples) / len(samples)
        var = sum((s - mean) ** 2 for s in samples) / len(samples)
        return var < 25  # near-uniform color across the whole page-sized image
    except Exception:
        return False


def composite_tiles(doc, tiles):
    """tiles: list of dicts with 'xref' and 'rect' (pymupdf.Rect), 2+ items
    whose placements abut to form one larger rectangle. Returns (pixmap_rgb_or_gray,
    union_rect) with the tiles pasted at their correct relative pixel offsets,
    built from a blank canvas via pymupdf.Pixmap — no re-sampling of tile
    pixels themselves, only lossless placement."""
    scales = []
    pixmaps = []
    for t in tiles:
        pm = pymupdf.Pixmap(doc, t['xref'])
        pixmaps.append(pm)
        scales.append(pm.width / t['rect'].width if t['rect'].width else 1.0)
        scales.append(pm.height / t['rect'].height if t['rect'].height else 1.0)
    scale = statistics.mean(scales)

    union_rect = manual_union_bbox([t['rect'] for t in tiles])
    canvas_w = max(round(union_rect.width * scale), 1)
    canvas_h = max(round(union_rect.height * scale), 1)

    cs_names = {pm.colorspace.name for pm in pixmaps if pm.colorspace}
    if len(cs_names) > 1 or any(pm.colorspace is None for pm in pixmaps):
        pixmaps = [pymupdf.Pixmap(pymupdf.csRGB, pm) if pm.colorspace and pm.colorspace.name != 'DeviceRGB' else pm
                   for pm in pixmaps]
        cs = pymupdf.csRGB
    else:
        cs = pixmaps[0].colorspace

    canvas = pymupdf.Pixmap(cs, (0, 0, canvas_w, canvas_h), 0)
    canvas.clear_with(255)
    for t, pm in zip(tiles, pixmaps):
        ox = round((t['rect'].x0 - union_rect.x0) * scale)
        oy = round((t['rect'].y0 - union_rect.y0) * scale)
        pm.set_origin(ox, oy)
        canvas.copy(pm, pm.irect)

    if canvas.colorspace and canvas.colorspace.n > 3:
        canvas = pymupdf.Pixmap(pymupdf.csRGB, canvas)
    return canvas, union_rect


def process_raster_figures(doc, manifest, counters):
    n_pages = doc.page_count
    for pno in range(n_pages):
        page = doc[pno]
        raw_infos = page.get_image_info(xrefs=True)
        infos = []
        for im in raw_infos:
            if im['xref'] == BLANK_XREF:
                continue
            if is_confirmed_blank(doc, page, im):
                counters['extra_blanks_excluded'] += 1
                log(f"  [blank-plate excluded] page {pno + 1} xref {im['xref']}")
                continue
            infos.append(im)

        if not infos:
            continue

        n = len(infos)
        find, union = union_find(n)
        rects = [pymupdf.Rect(im['bbox']) for im in infos]
        for i in range(n):
            for j in range(i + 1, n):
                if tiles_adjacent(rects[i], rects[j]):
                    union(i, j)

        groups = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)

        page_num = pno + 1
        for idxs in groups.values():
            members = [infos[i] for i in idxs]
            if len(members) >= 2:
                tiles = [{'xref': m['xref'], 'rect': pymupdf.Rect(m['bbox'])} for m in members]
                try:
                    canvas, union_rect = composite_tiles(doc, tiles)
                except Exception as e:
                    log(f"  [tile-composite FAILED] page {page_num} xrefs {[t['xref'] for t in tiles]}: {e}")
                    counters['tile_composite_failed'] += 1
                    continue
                xref_tag = "-".join(str(t['xref']) for t in sorted(tiles, key=lambda t: t['xref']))
                fname = dedupe_filename(f"p{page_num:04d}_xref{xref_tag}.png")
                fpath = f"{RAW_DIR}/{fname}"
                canvas.save(fpath)
                manifest.append({
                    "page_index": pno,
                    "page_number": page_num,
                    "xref": [t['xref'] for t in tiles],
                    "kind": "figure_tile",
                    "rect": [union_rect.x0, union_rect.y0, union_rect.x1, union_rect.y1],
                    "file": f"images/_raw/{fname}",
                })
                counters['figure_tile'] += 1
            else:
                m = members[0]
                xref = m['xref']
                try:
                    d = doc.extract_image(xref)
                except Exception as e:
                    log(f"  [extract_image FAILED] page {page_num} xref {xref}: {e}")
                    counters['extract_failed'] += 1
                    continue
                ext = d['ext']
                fname = dedupe_filename(f"p{page_num:04d}_xref{xref}.{ext}")
                fpath = f"{RAW_DIR}/{fname}"
                with open(fpath, 'wb') as fh:
                    fh.write(d['image'])
                bbox = m['bbox']
                manifest.append({
                    "page_index": pno,
                    "page_number": page_num,
                    "xref": xref,
                    "kind": "figure",
                    "rect": [bbox[0], bbox[1], bbox[2], bbox[3]],
                    "file": f"images/_raw/{fname}",
                })
                counters['figure'] += 1

        if page_num % 150 == 0:
            log(f"[figures] processed through page {page_num}/{n_pages} "
                f"— figures={counters['figure']} tiles={counters['figure_tile']}")


# ---------------------------------------------------------------------------
# Vector table diagrams
# ---------------------------------------------------------------------------

def cluster_page_drawings(drawings, tol=DRAW_CLUSTER_TOL):
    n = len(drawings)
    find, union = union_find(n)
    rects = [d['rect'] for d in drawings]
    for i in range(n):
        for j in range(i + 1, n):
            if rects_touch(rects[i], rects[j], tol):
                union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return groups


def classify_cluster_text(page, union_rect, pad=TABLE_PAD):
    clip = pymupdf.Rect(union_rect.x0 - pad, union_rect.y0 - pad,
                         union_rect.x1 + pad, union_rect.y1 + pad) & page.rect
    words = page.get_text("words", clip=clip)
    tokens = [w[4] for w in words]
    combined = " ".join(tokens)
    tokset = set(tokens)

    if len(tokens) < 3:
        return "skip_no_text", 0.0, len(tokens)

    if (re.search(r'Answer\s*Key', combined, re.I) or
            re.search(r'Question\s*No', combined, re.I) or
            re.search(r'Correct\s*Option', combined, re.I)):
        return "exclude_answerkey", 0.0, len(tokens)

    if {'Chapter', 'Title', 'Page'} <= tokset or \
       (re.search(r'\bContents\b', combined) and re.search(r'\bChapter\b', combined)):
        return "exclude_toc", 0.0, len(tokens)

    n_short = sum(1 for t in tokens if SHORT_TOKEN_PAT.match(t))
    frac_short = n_short / len(tokens)
    if frac_short >= ANSWERKEY_SHORTFRAC_THRESHOLD:
        return "exclude_shortfrac", frac_short, len(tokens)

    return "keep", frac_short, len(tokens)


def process_vector_tables(doc, manifest, counters, ambiguous_log):
    n_pages = doc.page_count
    for pno in range(n_pages):
        page = doc[pno]
        drawings = page.get_drawings()
        if len(drawings) < MIN_CLUSTER_ITEMS:
            continue

        groups = cluster_page_drawings(drawings)
        page_num = pno + 1
        table_idx = 0
        for idxs in groups.values():
            if len(idxs) < MIN_CLUSTER_ITEMS:
                continue
            rects = [drawings[i]['rect'] for i in idxs]
            union_rect = manual_union_bbox(rects)
            pw, ph = page.rect.width, page.rect.height
            if union_rect.width > 0.97 * pw and union_rect.height > 0.97 * ph:
                continue
            if union_rect.width < MIN_TABLE_W or union_rect.height < MIN_TABLE_H:
                continue

            verdict, frac_short, ntok = classify_cluster_text(page, union_rect)
            if verdict == "skip_no_text":
                continue
            if verdict in ("exclude_answerkey", "exclude_toc"):
                counters[verdict] += 1
                continue
            if verdict == "exclude_shortfrac":
                counters['exclude_shortfrac'] += 1
                continue

            if AMBIGUOUS_SHORTFRAC_LOW <= frac_short < ANSWERKEY_SHORTFRAC_THRESHOLD:
                ambiguous_log.append({
                    "page_number": page_num, "frac_short": round(frac_short, 2),
                    "n_tokens": ntok, "rect": [union_rect.x0, union_rect.y0, union_rect.x1, union_rect.y1],
                })

            table_idx += 1
            pad = TABLE_PAD
            clip = pymupdf.Rect(union_rect.x0 - pad, union_rect.y0 - pad,
                                 union_rect.x1 + pad, union_rect.y1 + pad) & page.rect
            try:
                pix = page.get_pixmap(clip=clip, dpi=TABLE_RENDER_DPI)
            except Exception as e:
                log(f"  [table render FAILED] page {page_num} cluster {table_idx}: {e}")
                counters['table_render_failed'] += 1
                continue
            fname = dedupe_filename(f"p{page_num:04d}_table{table_idx}.png")
            fpath = f"{RAW_DIR}/{fname}"
            pix.save(fpath)
            manifest.append({
                "page_index": pno,
                "page_number": page_num,
                "xref": None,
                "kind": "table",
                "rect": [clip.x0, clip.y0, clip.x1, clip.y1],
                "file": f"images/_raw/{fname}",
            })
            counters['table'] += 1

        if page_num % 150 == 0:
            log(f"[tables] processed through page {page_num}/{n_pages} — tables={counters['table']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    doc = pymupdf.open(SRC_PDF)
    assert doc.is_pdf
    n_pages = doc.page_count
    log(f"Opened {SRC_PDF} read-only ({n_pages} pages).")

    manifest = []
    counters = Counter()
    ambiguous_log = []

    log("=== Pass 1/2: raster figures + multi-tile composites ===")
    process_raster_figures(doc, manifest, counters)

    log("=== Pass 2/2: vector table diagrams ===")
    process_vector_tables(doc, manifest, counters, ambiguous_log)

    doc.close()

    out = {
        "source_pdf": SRC_PDF,
        "page_count": n_pages,
        "note": "Chapter numbers are NOT assigned in this stage; use page_index/page_number "
                "with the other stage's structure.json to re-file into chNN/ later.",
        "counts": {
            "figure": counters['figure'],
            "figure_tile": counters['figure_tile'],
            "table": counters['table'],
            "extra_blanks_excluded": counters['extra_blanks_excluded'],
            "extract_failed": counters['extract_failed'],
            "tile_composite_failed": counters['tile_composite_failed'],
            "table_render_failed": counters['table_render_failed'],
            "excluded_answerkey_clusters": counters['exclude_answerkey'] + counters['exclude_shortfrac'],
            "excluded_toc_clusters": counters['exclude_toc'],
        },
        "ambiguous_table_pages": ambiguous_log,
        "images": manifest,
    }
    with open(MANIFEST_PATH, 'w') as fh:
        json.dump(out, fh, indent=2)

    log("")
    log("=== SUMMARY ===")
    log(f"Raster figures (incl. tile composites counted once each): "
        f"{counters['figure']} single + {counters['figure_tile']} composited "
        f"= {counters['figure'] + counters['figure_tile']} total")
    log(f"Vector table images: {counters['table']}")
    log(f"Extra blank plates excluded (beyond xref {BLANK_XREF}): {counters['extra_blanks_excluded']}")
    log(f"Answer-key/TOC clusters excluded: "
        f"{counters['exclude_answerkey'] + counters['exclude_shortfrac']} answerkey, "
        f"{counters['exclude_toc']} toc")
    log(f"Ambiguous table-page clusters logged: {len(ambiguous_log)}")
    log(f"Failures: extract={counters['extract_failed']} "
        f"tile_composite={counters['tile_composite_failed']} table_render={counters['table_render_failed']}")
    log(f"Manifest written to: {MANIFEST_PATH}")
    log(f"Images written to: {RAW_DIR}")


if __name__ == "__main__":
    main()
