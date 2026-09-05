"""
Stage 1: decode the 54 poisoned Georgia subset fonts in Surgery_ed8.pdf.

Each subset font uses Identity-H encoding + CIDToGIDMap /Identity, so the
2-byte code in the content stream IS the glyph id (GID) directly indexing
into the subset TrueType's own glyf/hmtx tables. The subset's ToUnicode CMap
is poisoned (every code -> U+FFFD), but the subset is a genuine Georgia
subset: it keeps Georgia's real advance widths and outlines. So for each GID
we can recover the source character by:
  1. computing the GID's advance width (scaled to 1000 units/em) from the
     subset font's own hmtx table,
  2. looking up which Georgia (regular/bold/italic/bold-italic) character(s)
     share that exact scaled width,
  3. if more than one candidate shares the width, breaking the tie by
     comparing glyf bounding boxes (also scaled to 1000 units/em) between
     the subset glyph and each candidate Georgia glyph.

Output: work/glyph_maps.json = { "<BaseFont tag+name>": {"<gid>": "<char>", ...}, ... }
Gate: 0 unmatched glyphs across all 54 subsets.
"""
import io
import json
import re
import sys
from pathlib import Path

import pymupdf as fitz
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = Path.home() / "Downloads" / "Surgery_ed8.pdf"
WORK = ROOT / "work"
WORK.mkdir(parents=True, exist_ok=True)

GEORGIA_DIR = Path("/System/Library/Fonts/Supplemental")
GEORGIA_FACES = {
    "regular": GEORGIA_DIR / "Georgia.ttf",
    "bold": GEORGIA_DIR / "Georgia Bold.ttf",
    "italic": GEORGIA_DIR / "Georgia Italic.ttf",
    "bolditalic": GEORGIA_DIR / "Georgia Bold Italic.ttf",
}


def scaled(raw, upm):
    return round(raw * 1000.0 / upm)


class GeorgiaFace:
    """Reverse index for one Georgia weight/style: width(1000-scale) -> [chars]."""

    def __init__(self, path):
        self.font = TTFont(str(path))
        self.upm = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()  # unicode codepoint -> glyph name
        self.hmtx = self.font["hmtx"]
        self.glyf = self.font["glyf"] if "glyf" in self.font else None
        self.width_index = {}  # width1000 -> list of unicode codepoints
        self.bbox_cache = {}  # codepoint -> (xmin,ymin,xmax,ymax) scaled
        for cp, gname in self.cmap.items():
            raw_w = self.hmtx[gname][0]
            w1000 = scaled(raw_w, self.upm)
            self.width_index.setdefault(w1000, []).append(cp)
            self.bbox_cache[cp] = self._bbox(gname)

    def _bbox(self, gname):
        if self.glyf is None:
            return (0, 0, 0, 0)
        g = self.glyf[gname]
        if getattr(g, "numberOfContours", 0) == 0:
            return (0, 0, 0, 0)
        try:
            xmin, ymin, xmax, ymax = g.xMin, g.yMin, g.xMax, g.yMax
        except AttributeError:
            return (0, 0, 0, 0)
        f = 1000.0 / self.upm
        return (round(xmin * f), round(ymin * f), round(xmax * f), round(ymax * f))

    def candidates(self, w1000):
        return self.width_index.get(w1000, [])

    def bbox(self, cp):
        return self.bbox_cache[cp]


def load_faces():
    faces = {}
    for name, path in GEORGIA_FACES.items():
        assert path.exists(), f"missing Georgia face: {path}"
        faces[name] = GeorgiaFace(path)
    return faces


def find_subset_fonts(doc):
    """Return list of dicts describing each of the 54 poisoned Georgia subsets."""
    n = doc.xref_length()
    out = []
    for xref in range(1, n):
        try:
            obj = doc.xref_object(xref, compressed=False)
        except Exception:
            continue
        if "/Type0" not in obj or "Georgia" not in obj or "/Identity-H" not in obj:
            continue
        m = re.search(r"/BaseFont\s*/(\S+)", obj)
        basefont = m.group(1)
        m2 = re.search(r"/DescendantFonts\s*(?:\[\s*)?(\d+)\s*0\s*R", obj)
        df_xref = int(m2.group(1))
        df_obj = doc.xref_object(df_xref, compressed=False)
        m2b = re.search(r"(\d+)\s*0\s*R", df_obj)
        cid_xref = int(m2b.group(1))
        cid_obj = doc.xref_object(cid_xref, compressed=False)
        m3 = re.search(r"/FontDescriptor\s*(\d+)\s*0\s*R", cid_obj)
        fd_xref = int(m3.group(1))
        fd_obj = doc.xref_object(fd_xref, compressed=False)
        w = re.search(r"/FontWeight\s*(\d+)", fd_obj)
        ia = re.search(r"/ItalicAngle\s*(-?\d+)", fd_obj)
        ff = re.search(r"/FontFile2\s*(\d+)\s*0\s*R", fd_obj)
        assert ff, f"subset {basefont} (xref {xref}) has no embedded FontFile2"
        out.append(
            {
                "xref": xref,
                "basefont": basefont,
                "fontfile2_xref": int(ff.group(1)),
                "weight": int(w.group(1)) if w else 400,
                "italic_angle": int(ia.group(1)) if ia else 0,
            }
        )
    return out


def face_order_for(info):
    """Pick which Georgia face(s) to try, in order, based on descriptor hints."""
    bold = info["weight"] >= 600
    italic = info["italic_angle"] != 0
    primary = "regular"
    if bold and italic:
        primary = "bolditalic"
    elif bold:
        primary = "bold"
    elif italic:
        primary = "italic"
    order = [primary] + [f for f in ("regular", "bold", "italic", "bolditalic") if f != primary]
    return order


def decode_subset(doc, info, faces):
    stream = doc.xref_stream(info["fontfile2_xref"])
    f = TTFont(io.BytesIO(stream))
    upm = f["head"].unitsPerEm
    glyph_order = f.getGlyphOrder()
    hmtx = f["hmtx"]
    glyf = f["glyf"] if "glyf" in f else None
    n_glyphs = len(glyph_order)

    def sub_bbox(gname):
        if glyf is None:
            return (0, 0, 0, 0)
        g = glyf[gname]
        if getattr(g, "numberOfContours", 0) == 0:
            return (0, 0, 0, 0)
        try:
            xmin, ymin, xmax, ymax = g.xMin, g.yMin, g.xMax, g.yMax
        except AttributeError:
            return (0, 0, 0, 0)
        fac = 1000.0 / upm
        return (round(xmin * fac), round(ymin * fac), round(xmax * fac), round(ymax * fac))

    gid_map = {}
    unmatched = []
    ties_resolved = 0
    face_order = face_order_for(info)

    for gid in range(1, n_glyphs):
        gname = glyph_order[gid]
        raw_w = hmtx[gname][0]
        w1000 = scaled(raw_w, upm)
        bbox_s = sub_bbox(gname)

        chosen = None
        for face_name in face_order:
            face = faces[face_name]
            cands = face.candidates(w1000)
            if not cands:
                continue
            if len(cands) == 1:
                chosen = cands[0]
                break
            # tie-break on bbox
            exact = [cp for cp in cands if face.bbox(cp) == bbox_s]
            if len(exact) == 1:
                chosen = exact[0]
                ties_resolved += 1
                break
            if len(exact) > 1:
                # still ambiguous after bbox; prefer lowest codepoint deterministically
                chosen = sorted(exact)[0]
                ties_resolved += 1
                break
            # no bbox match in this face; try nearest bbox distance as last resort
            def dist(cp):
                b = face.bbox(cp)
                return sum(abs(a - c) for a, c in zip(b, bbox_s))

            best = min(cands, key=dist)
            if dist(best) <= 4:  # small rounding tolerance
                chosen = best
                ties_resolved += 1
                break
        if chosen is None:
            unmatched.append(gid)
        else:
            gid_map[gid] = chr(chosen)

    return gid_map, unmatched, ties_resolved, n_glyphs


def main():
    doc = fitz.open(str(PDF_PATH))
    faces = load_faces()
    subsets = find_subset_fonts(doc)
    print(f"found {len(subsets)} Georgia Identity-H subset fonts")
    assert len(subsets) == 54, f"expected 54 subsets, found {len(subsets)}"

    all_maps = {}
    total_unmatched = 0
    total_ties = 0
    total_glyphs = 0
    per_subset_report = []

    for info in subsets:
        gid_map, unmatched, ties, n_glyphs = decode_subset(doc, info, faces)
        key = info["basefont"]
        all_maps[key] = {str(g): c for g, c in gid_map.items()}
        total_unmatched += len(unmatched)
        total_ties += ties
        total_glyphs += n_glyphs - 1  # exclude .notdef
        per_subset_report.append((key, n_glyphs - 1, ties, len(unmatched)))
        if unmatched:
            print(f"  UNMATCHED in {key}: gids={unmatched}")

    print(f"total glyphs: {total_glyphs}, ties resolved: {total_ties}, unmatched: {total_unmatched}")

    out = {
        "faces_used": list(GEORGIA_FACES.keys()),
        "subset_count": len(subsets),
        "total_glyphs": total_glyphs,
        "ties_resolved": total_ties,
        "unmatched": total_unmatched,
        "maps": all_maps,
    }
    out_path = WORK / "glyph_maps.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")

    assert total_unmatched == 0, f"GATE FAILED: {total_unmatched} unmatched glyphs"
    print("GATE PASSED: 0 unmatched glyphs across all 54 subsets")


if __name__ == "__main__":
    main()
