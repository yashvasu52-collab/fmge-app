"""
Stage 3: segment the repaired PDF into 54 chapters x questions/options/
answer-key/solutions, using MuPDF's block-level text extraction (which
already groups wrapped lines into paragraph-ish units) and the string
markers that mark structure ("Question N:", "a)".."d)", "Solution to
Question N:", answer-key "<qno>\n<letter>" rows, "Detailed Explanations",
"Answer Key"), NOT page boundaries (answer-key tables + Detailed
Explanations + Solution 1 share one page in 26/54 chapters).

Output: work/structure.json
Gate: per-chapter #Q == #Sol == #AK == maxQ, matching a hardcoded reference
table built from the same source-of-truth regex counts used here.
"""
import json
import re
from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
REPAIRED_PATH = WORK / "Surgery_ed8.repaired.pdf"

WATERMARK_TEXT = "Sold by @itachibot"
TITLE_RE = re.compile(r"^Question (\d+):$")
SOL_RE = re.compile(r"^Solution to Question (\d+):$")
OPT_RE = re.compile(r"^([a-d])\)\s*(.*)$", re.S)
AK_ROW_RE = re.compile(r"^(\d{1,3})\n([a-dA-D])$")
DETAILED_EXPL_RE = re.compile(r"^Detailed Explanations$")
ANSWER_KEY_RE = re.compile(r"^Answer Key$")


def is_footer(block):
    x0, y0, x1, y1, text, *_ = block
    t = text.strip()
    if not t.isdigit():
        return False
    return 755.0 <= y0 <= 780.0 and 295.0 <= x0 <= 305.0


def is_watermark(block):
    x0, y0, x1, y1, text, *_ = block
    return WATERMARK_TEXT in text


def clean_block_text(text):
    # collapse wrapped internal newlines within one block/paragraph to spaces
    return re.sub(r"\s*\n\s*", " ", text.strip()).strip()


def find_chapter_title_pages(doc):
    titles = []  # list of (page_index0, title_text, first_span_y)
    for i in range(doc.page_count):
        d = doc[i].get_text("dict")
        spans_txt = []
        y0 = None
        for b in d["blocks"]:
            if "lines" not in b:
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    if s["font"] == "Arial-BoldMT" and abs(s["size"] - 20.0) < 0.15:
                        spans_txt.append(s["text"])
                        if y0 is None:
                            y0 = s["bbox"][1]
        if spans_txt:
            titles.append((i, " ".join(spans_txt).strip(), y0))
    return titles


def chapter_page_ranges(titles, total_pages):
    ranges = []
    for idx, (page0, title, _) in enumerate(titles):
        start = page0
        end = (titles[idx + 1][0] - 1) if idx + 1 < len(titles) else (total_pages - 1)
        ranges.append((start, end, title))
    return ranges


def iter_content_blocks(doc, start_page0, end_page0):
    """Yield (page0, block) for all non-watermark/footer/image blocks in range, in order."""
    for p in range(start_page0, end_page0 + 1):
        page = doc[p]
        blocks = page.get_text("blocks")
        # sort defensively by (y0, x0) to guarantee top-to-bottom, left-to-right order
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))
        for b in blocks:
            if b[6] != 0:  # not a text block (image block) -> skip, handled in stage 4
                continue
            if is_watermark(b) or is_footer(b):
                continue
            yield p, b


def parse_chapter(doc, chno, start_page0, end_page0, title):
    """State machine over ordered content blocks -> questions, answer_key, solutions."""
    questions = []  # {no, page, stem, options: [4 strings]}
    solutions = []  # {no, page, parts: [{text, bbox, page}]}
    answer_key = {}  # qno(int) -> letter(lower)
    # Flat, page/y-ordered list of every content block tagged with its owner
    # (question or solution) — this is what build_bank.py uses to place
    # images into the right spot (and, for vector-table images, to know
    # which garbled text blocks to drop). Covers both question-section and
    # solution-section blocks, unlike `solutions[i]["parts"]` alone.
    content_blocks = []

    cur_q = None  # dict being built: no, page, stem_parts (list of {text,bbox,page}), options(dict letter->{text,bbox,page})
    cur_sol = None  # dict: no, page, parts

    def flush_question():
        nonlocal cur_q
        if cur_q is not None:
            opts = [cur_q["options"].get(l, {}).get("text", "") for l in "abcd"]
            questions.append(
                {
                    "no": cur_q["no"],
                    "page": cur_q["page"] + 1,
                    "stem": clean_block_text(" ".join(p["text"] for p in cur_q["stem_parts"])),
                    "options": [clean_block_text(o) for o in opts],
                }
            )
            cur_q = None

    def flush_solution():
        nonlocal cur_sol
        if cur_sol is not None:
            solutions.append(cur_sol)
            cur_sol = None

    for page0, b in iter_content_blocks(doc, start_page0, end_page0):
        x0, y0, x1, y1, text, *_ = b
        raw = text.rstrip("\n")

        m_q = TITLE_RE.match(raw)
        m_sol = SOL_RE.match(raw)
        m_opt = OPT_RE.match(raw)
        m_ak = AK_ROW_RE.match(raw)

        if m_q:
            flush_question()
            cur_q = {"no": int(m_q.group(1)), "page": page0, "stem_parts": [], "options": {}}
            continue

        if m_sol:
            flush_question()  # the question section is over once solutions start
            flush_solution()
            cur_sol = {"no": int(m_sol.group(1)), "page": page0 + 1, "parts": []}
            continue

        if m_ak:
            flush_question()  # the question section is over once the answer key starts
            qno = int(m_ak.group(1))
            letter = m_ak.group(2).lower()
            answer_key[qno] = letter
            continue

        if DETAILED_EXPL_RE.match(raw) or ANSWER_KEY_RE.match(raw):
            flush_question()
            continue  # section header markers, not content

        if raw.strip() == title.strip() and page0 == start_page0:
            continue  # the chapter title block (belt-and-suspenders; falls through anyway)

        if "Question No." in raw and "Correct Option" in raw:
            continue  # answer-key table header block

        # dispatch to whichever block is currently open
        if cur_q is not None and m_opt:
            letter = m_opt.group(1)
            entry = {"text": clean_block_text(m_opt.group(2)), "bbox": [x0, y0, x1, y1], "page": page0 + 1}
            cur_q["options"][letter] = entry
            content_blocks.append({"owner": "question", "no": cur_q["no"], "role": f"option_{letter}", **entry})
            continue

        if cur_q is not None and not cur_q["options"]:
            # still accumulating the stem (before any option seen)
            entry = {"text": clean_block_text(raw), "bbox": [x0, y0, x1, y1], "page": page0 + 1}
            cur_q["stem_parts"].append(entry)
            content_blocks.append({"owner": "question", "no": cur_q["no"], "role": "stem", **entry})
            continue

        # Note: options are never split across multiple blocks in this PDF —
        # get_text("blocks") already merges each option's wrapped lines into
        # one block (verified: exactly 1256 blocks match each of a)/b)/c)/d)
        # across the whole document) — so no continuation-merge is needed
        # here. A block reaching this point while cur_q still has options
        # open would be an anomaly; it falls through to be ignored (or
        # attached to a solution below) rather than silently corrupting the
        # last option's text.

        if cur_sol is not None:
            entry = {"text": clean_block_text(raw), "bbox": [x0, y0, x1, y1], "page": page0 + 1}
            cur_sol["parts"].append(entry)
            content_blocks.append({"owner": "solution", "no": cur_sol["no"], "role": "explanation", **entry})
            continue

        # unrecognized block outside any open question/solution (e.g. stray header) -> ignore

    flush_question()
    flush_solution()

    return {
        "no": chno,
        "title": title,
        "pages": [start_page0 + 1, end_page0 + 1],
        "questions": questions,
        "answer_key": answer_key,
        "solutions": solutions,
        "content_blocks": content_blocks,
    }


def main():
    doc = fitz.open(str(REPAIRED_PATH))
    titles = find_chapter_title_pages(doc)
    print(f"found {len(titles)} chapter title pages")
    assert len(titles) == 54, f"expected 54 chapter titles, found {len(titles)}"

    ranges = chapter_page_ranges(titles, doc.page_count)

    chapters = []
    total_q = 0
    bad = []
    for idx, (start0, end0, title) in enumerate(ranges, start=1):
        ch = parse_chapter(doc, idx, start0, end0, title)
        nq = len(ch["questions"])
        nsol = len(ch["solutions"])
        nak = len(ch["answer_key"])
        maxq = max([q["no"] for q in ch["questions"]], default=0)
        ok = nq == nsol == nak == maxq and nq > 0
        total_q += nq
        status = "OK" if ok else "MISMATCH"
        if not ok:
            bad.append((idx, title, nq, nsol, nak, maxq))
        print(f"ch{idx:02d} p{start0+1}-{end0+1} '{title}': Q={nq} Sol={nsol} AK={nak} maxQ={maxq} [{status}]")
        chapters.append(ch)

    out = {"chapters": chapters}
    out_path = WORK / "structure.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    print(f"TOTAL questions: {total_q}")

    if bad:
        print(f"GATE FAILED: {len(bad)} chapters mismatched:")
        for b in bad:
            print("  ", b)
        raise SystemExit(1)

    assert total_q == 1256, f"GATE FAILED: expected 1256 total questions, got {total_q}"
    print("GATE PASSED: per-chapter #Q==#Sol==#AK==maxQ for all 54 chapters; total = 1256")


if __name__ == "__main__":
    main()
