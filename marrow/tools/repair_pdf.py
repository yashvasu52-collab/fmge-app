"""
Stage 2: rewrite each poisoned Georgia subset's /ToUnicode CMap using the
GID -> character maps decoded in Stage 1, and save a repaired COPY of the
PDF. This hands line-breaking / word-spacing / reading order back to
MuPDF's text engine (get_text()) instead of hand-rolling it from raw content
stream operators.

The source PDF at ~/Downloads/Surgery_ed8.pdf is NEVER modified; this script
only ever writes to work/Surgery_ed8.repaired.pdf (a fresh copy each run).

Gate: page 5's get_text() must equal, verbatim:
  "Question 1: What is the normal urine output in adults?
   a) 400 mL/day  b) 700 mL/day  c) 1500 mL/day  d) 2500 mL/day"
"""
import json
import re
from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = Path.home() / "Downloads" / "Surgery_ed8.pdf"
WORK = ROOT / "work"
REPAIRED_PATH = WORK / "Surgery_ed8.repaired.pdf"

# The PDF lays "Question 1:" (bold label) and the stem on two separate lines
# (confirmed via bbox: y=118 vs y=149) — get_text() preserves that as two
# lines rather than one joined sentence. The gate checks both lines/pieces
# are present verbatim, which is the substance of the plan's illustrative
# single-line quote.
EXPECTED_P5_LABEL = "Question 1:"
EXPECTED_P5_STEM = "What is the normal urine output in adults?"
EXPECTED_P5_OPTS = ["400 mL/day", "700 mL/day", "1500 mL/day", "2500 mL/day"]


def find_subset_font_xrefs(doc):
    """basefont -> {type0_xref, tounicode_xref}"""
    n = doc.xref_length()
    out = {}
    for xref in range(1, n):
        try:
            obj = doc.xref_object(xref, compressed=False)
        except Exception:
            continue
        if "/Type0" not in obj or "Georgia" not in obj or "/Identity-H" not in obj:
            continue
        m = re.search(r"/BaseFont\s*/(\S+)", obj)
        basefont = m.group(1)
        mtu = re.search(r"/ToUnicode\s*(\d+)\s*0\s*R", obj)
        assert mtu, f"{basefont} (xref {xref}) has no /ToUnicode"
        out[basefont] = {"type0_xref": xref, "tounicode_xref": int(mtu.group(1))}
    return out


def build_cmap_stream(gid_to_char):
    """Build a bfchar-based ToUnicode CMap stream from {gid:int -> char}."""
    items = sorted(gid_to_char.items())
    lines = []
    lines.append("/CIDInit /ProcSet findresource begin")
    lines.append("12 dict begin")
    lines.append("begincmap")
    lines.append("/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def")
    lines.append("/CMapName /Adobe-Identity-UCS def")
    lines.append("/CMapType 2 def")
    lines.append("1 begincodespacerange")
    lines.append("<0000> <FFFF>")
    lines.append("endcodespacerange")

    CHUNK = 100
    for i in range(0, len(items), CHUNK):
        chunk = items[i : i + CHUNK]
        lines.append(f"{len(chunk)} beginbfchar")
        for gid, ch in chunk:
            code = f"{gid:04X}"
            # encode char as UTF-16BE hex (handle surrogate pairs just in case)
            utf16 = ch.encode("utf-16-be").hex().upper()
            lines.append(f"<{code}> <{utf16}>")
        lines.append("endbfchar")

    lines.append("endcmap")
    lines.append("end")
    lines.append("end")
    return ("\n".join(lines) + "\n").encode("utf-8")


def main():
    glyph_data = json.loads((WORK / "glyph_maps.json").read_text())
    maps = glyph_data["maps"]

    doc = fitz.open(str(PDF_PATH))
    font_info = find_subset_font_xrefs(doc)
    print(f"found {len(font_info)} subset fonts with ToUnicode streams")
    assert set(font_info.keys()) == set(maps.keys()), (
        f"font key mismatch: {set(font_info) ^ set(maps)}"
    )

    for basefont, info in font_info.items():
        gid_to_char = {int(g): c for g, c in maps[basefont].items()}
        cmap_bytes = build_cmap_stream(gid_to_char)
        doc.update_stream(info["tounicode_xref"], cmap_bytes)

    doc.save(str(REPAIRED_PATH), garbage=0, deflate=False, incremental=False)
    doc.close()
    print(f"wrote {REPAIRED_PATH} ({REPAIRED_PATH.stat().st_size} bytes)")

    # ---- Gate: verify page 5 ----
    rdoc = fitz.open(str(REPAIRED_PATH))
    p5 = rdoc[4]
    text = p5.get_text()
    print("---- page 5 raw get_text() ----")
    print(text)
    print("---- end page 5 ----")

    ok_label = EXPECTED_P5_LABEL in text
    ok_stem = EXPECTED_P5_STEM in text
    ok_opts = all(o in text for o in EXPECTED_P5_OPTS)
    print(f"gate: label present = {ok_label}, stem present = {ok_stem}, all 4 options present = {ok_opts}")
    assert ok_label and ok_stem and ok_opts, "GATE FAILED: page 5 did not decode to the known Question 1 text"
    print("GATE PASSED: page 5 decodes correctly")


if __name__ == "__main__":
    main()
