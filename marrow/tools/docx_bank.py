"""
Convert a Marrow ed8 docx question bank (Anaesthesia/ENT/Ophthalmology/Psychiatry)
into the same JSON schema used by surgery_ed8.json.

Usage:
    python3 docx_bank.py --subject psychiatry
    python3 docx_bank.py --subject ent
    python3 docx_bank.py --subject ophthalmology
    python3 docx_bank.py --subject anaesthesia
    python3 docx_bank.py --subject psychiatry --verify-only   # just re-run checks on existing output
"""
import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

import docx
from docx.document import Document as _Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

MARROW_DIR = Path(__file__).resolve().parent.parent
FILES_DIR = Path("/Users/yashvasu/Desktop/study/files")

SUBJECTS = {
    "psychiatry": dict(
        src=FILES_DIR / "Psychiatry_ed8(1).docx",
        prefix="PSY",
        title="Psychiatry",
        out=MARROW_DIR / "psychiatry_ed8.json",
        imgdir=MARROW_DIR / "images" / "psy",
    ),
    "ent": dict(
        src=FILES_DIR / "ENT_ed8.docx",
        prefix="ENT",
        title="ENT",
        out=MARROW_DIR / "ent_ed8.json",
        imgdir=MARROW_DIR / "images" / "ent",
    ),
    "ophthalmology": dict(
        src=FILES_DIR / "Ophthalmology_ed8.docx",
        prefix="OPH",
        title="Ophthalmology",
        out=MARROW_DIR / "ophthalmology_ed8.json",
        imgdir=MARROW_DIR / "images" / "oph",
    ),
    "anaesthesia": dict(
        src=FILES_DIR / "Anaesthesia_ed8(2).docx",
        prefix="ANE",
        title="Anaesthesia",
        out=MARROW_DIR / "anaesthesia_ed8.json",
        imgdir=MARROW_DIR / "images" / "ane",
    ),
    "forensic_medicine": dict(
        src=FILES_DIR / "Forensic_Medicine_ed8.docx",
        prefix="FOR",
        title="Forensic Medicine",
        out=MARROW_DIR / "forensic_medicine_ed8.json",
        imgdir=MARROW_DIR / "images" / "for",
    ),
    "pharmacology": dict(
        src=FILES_DIR / "Pharmacology_ed8.docx",
        prefix="PHA",
        title="Pharmacology",
        out=MARROW_DIR / "pharmacology_ed8.json",
        imgdir=MARROW_DIR / "images" / "pha",
    ),
    "psm": dict(
        src=FILES_DIR / "PSM_ed8.docx",
        prefix="PSM",
        title="PSM",
        out=MARROW_DIR / "psm_ed8.json",
        imgdir=MARROW_DIR / "images" / "psm",
    ),
    "biochemistry": dict(
        src=FILES_DIR / "Biochemistry_ed8.docx",
        prefix="BIO",
        title="Biochemistry",
        out=MARROW_DIR / "biochemistry_ed8.json",
        imgdir=MARROW_DIR / "images" / "bio",
    ),
    "dermatology": dict(
        src=FILES_DIR / "Dermatology_ed8_compressed_compressed.docx",
        prefix="DER",
        title="Dermatology",
        out=MARROW_DIR / "dermatology_ed8.json",
        imgdir=MARROW_DIR / "images" / "der",
    ),
    "pediatrics": dict(
        src=Path("/Users/yashvasu/Downloads/Pediatrics_ed8(1)_compressed.docx"),
        prefix="PED",
        title="Pediatrics",
        out=MARROW_DIR / "pediatrics_ed8.json",
        imgdir=MARROW_DIR / "images" / "ped",
    ),
    "microbiology": dict(
        src=Path("/Users/yashvasu/Downloads/Microbiology_ed8_compressed.docx"),
        prefix="MIC",
        title="Microbiology",
        out=MARROW_DIR / "microbiology_ed8.json",
        imgdir=MARROW_DIR / "images" / "mic",
    ),
    "medicine": dict(
        src=Path("/Users/yashvasu/Downloads/Medicine_ed8(1)_compressed.docx"),
        prefix="MED",
        title="Medicine",
        out=MARROW_DIR / "medicine_ed8.json",
        imgdir=MARROW_DIR / "images" / "med",
    ),
    "obgyn": dict(
        src=FILES_DIR / "OBGYN_ed8-compressed.docx",
        prefix="OBG",
        title="OBGYN",
        out=MARROW_DIR / "obgyn_ed8.json",
        imgdir=MARROW_DIR / "images" / "obg",
    ),
    "anatomy": dict(
        src=FILES_DIR / "Anatomy_ed8_compressed.docx",
        prefix="ANA",
        title="Anatomy",
        out=MARROW_DIR / "anatomy_ed8.json",
        imgdir=MARROW_DIR / "images" / "ana",
    ),
    "orthopaedics": dict(
        src=FILES_DIR / "Orthopaedics_ed8-compressed.docx",
        prefix="ORT",
        title="Orthopaedics",
        out=MARROW_DIR / "orthopaedics_ed8.json",
        imgdir=MARROW_DIR / "images" / "ort",
    ),
    "pathology": dict(
        src=FILES_DIR / "Pathology_ed8_compressed-compressed.docx",
        prefix="PAT",
        title="Pathology",
        out=MARROW_DIR / "pathology_ed8.json",
        imgdir=MARROW_DIR / "images" / "pat",
    ),
    "radiology": dict(
        src=FILES_DIR / "Radiology_ed8_compressed.docx",
        prefix="RAD",
        title="Radiology",
        out=MARROW_DIR / "radiology_ed8.json",
        imgdir=MARROW_DIR / "images" / "rad",
    ),
}

QUESTION_RE = re.compile(r"^Question\s+(\d+)\s*:?\s*$", re.IGNORECASE)
SOLUTION_RE = re.compile(r"^Solution\s+to\s+Question\s+(\d+)\s*:?\s*$", re.IGNORECASE)
BLIP_RE = re.compile(r'<a:blip[^>]*r:embed="(rId\d+)"')


def iter_block_items(parent):
    """Yield paragraphs and tables in document order (top-level body children only)."""
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("unsupported parent type")
    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def looks_like_options_table(table):
    """A rare layout: a question's 4 options given as table rows 'a) ...'/'b) ...' etc,
    instead of a bullet list."""
    rows = list(table.rows)
    if not rows:
        return False
    letters = []
    for r in rows:
        cells = [c.text.strip() for c in r.cells]
        if not cells:
            return False
        m = re.match(r"^([a-hA-H])\)\s*", cells[0])
        if not m:
            return False
        letters.append(m.group(1).lower())
    return letters == sorted(letters) and len(set(letters)) == len(letters)


def looks_like_answer_key_table(table):
    """Detect a Question-No/Correct-Option table by content, not just a preceding
    heading -- some chapters are missing the literal "Answer Key" heading."""
    rows = list(table.rows)
    if not rows:
        return False
    header = [c.text.strip() for c in rows[0].cells]
    has_header = bool(header) and "question" in header[0].lower()
    data_rows = rows[1:] if has_header else rows
    if has_header:
        return True
    if not data_rows:
        return False
    matches = 0
    for r in data_rows:
        cells = [c.text.strip() for c in r.cells]
        if len(cells) == 2 and re.fullmatch(r"\d+", cells[0]) and re.fullmatch(r"[a-hA-H]", cells[1]):
            matches += 1
    return matches >= max(1, int(0.7 * len(data_rows)))


def table_to_text(table):
    rows = []
    for row in table.rows:
        cells = [c.text.strip().replace("\n", " ") for c in row.cells]
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def find_images(paragraph):
    """Return list of (rid,) in document order found in this paragraph's XML."""
    xml = paragraph._p.xml
    return BLIP_RE.findall(xml)


def resolve_image(paragraph, rid):
    part = paragraph.part.related_parts[rid]
    ext = Path(part.partname).suffix.lstrip(".") or "png"
    return part.blob, ext


def parse_contents_tables(blocks):
    """Chapter number -> page, from the TOC tables preceding the first Heading 1."""
    pages = {}
    for kind, obj in blocks:
        if kind == "heading1":
            break
        if kind == "table":
            rows = list(obj.rows)
            if not rows:
                continue
            header = [c.text.strip() for c in rows[0].cells]
            if len(header) >= 3 and header[0].lower().startswith("chapter"):
                for r in rows[1:]:
                    cells = [c.text.strip() for c in r.cells]
                    if len(cells) < 3:
                        continue
                    try:
                        chno = int(cells[0])
                        page = int(cells[2])
                    except ValueError:
                        continue
                    pages[chno] = page
    return pages


def classify(obj):
    if isinstance(obj, Table):
        return ("table", obj)
    style = obj.style.name if obj.style else ""
    text = obj.text.strip()
    if style == "Heading 1":
        return ("heading1", obj)
    if style == "Heading 2":
        return ("heading2", obj)
    if style == "Heading 3":
        if QUESTION_RE.match(text):
            return ("question_marker", obj)
        if SOLUTION_RE.match(text):
            return ("solution_marker", obj)
        return ("para", obj)
    return ("para", obj)


def extract(subject_key):
    cfg = SUBJECTS[subject_key]
    print(f"Loading {cfg['src']} ...")
    doc = docx.Document(str(cfg["src"]))

    raw_blocks = list(iter_block_items(doc))
    blocks = [classify(b) for b in raw_blocks]

    chapter_pages = parse_contents_tables(blocks)

    chapters = []
    cur = None  # current chapter dict (working state)
    phase = None  # 'questions' | 'answerkey' | 'explanations'
    questions_by_no = {}
    answer_key = {}
    img_state = {}  # qno -> {"counter": int, "images": [...]}  (shared across stem+solution)
    pending_table_text_notes = 0

    def start_chapter(title):
        nonlocal cur, phase, questions_by_no, answer_key, img_state
        if cur is not None:
            finalize_chapter()
        chno = len(chapters) + 1
        cur = dict(no=chno, title=title, page=chapter_pages.get(chno))
        phase = "questions"
        questions_by_no = {}
        answer_key = {}
        img_state = {}

    def finalize_chapter():
        nonlocal cur, questions_by_no, answer_key
        qlist = []
        for qno in sorted(questions_by_no):
            q = questions_by_no[qno]
            letter = answer_key.get(qno)
            correct = ord(letter) - ord("a") if letter else None
            q["answer"] = letter
            q["correct"] = correct
            q["images"] = img_state.get(qno, {}).get("images", [])
            qlist.append(q)
        cur["questions"] = qlist
        chapters.append(cur)

    # walking state for question/solution accumulation
    active_kind = None  # 'question' | 'solution' | None
    active_no = None
    stem_parts = []
    options = []
    expl_parts = []

    def flush_active():
        nonlocal active_kind, active_no, stem_parts, options, expl_parts
        if active_kind == "question" and active_no is not None:
            stem = " ".join(s for s in stem_parts if s).strip()
            stem = re.sub(r"\s+", " ", stem)
            questions_by_no[active_no] = dict(
                no=active_no,
                stem=stem,
                options=list(options),
                explanation="",
            )
        elif active_kind == "solution" and active_no is not None:
            expl = "\n".join(e for e in expl_parts if e is not None).strip()
            q = questions_by_no.get(active_no)
            if q is not None:
                q["explanation"] = expl
        active_kind = None
        active_no = None
        stem_parts, options, expl_parts = [], [], []

    def handle_images_in_paragraph(p, target_text_list):
        if active_no is None:
            return
        rids = find_images(p)
        if not rids:
            return
        st = img_state.setdefault(active_no, {"counter": 0, "images": []})
        for rid in rids:
            try:
                blob, ext = resolve_image(p, rid)
            except KeyError:
                continue
            st["counter"] += 1
            ref = st["counter"]
            st["images"].append(dict(ref=ref, blob=blob, ext=ext))
            target_text_list.append(f"[[IMG:{ref}]]")

    waiting_answer_table = False

    i = 0
    n = len(blocks)
    while i < n:
        kind, obj = blocks[i]

        if kind == "heading1":
            flush_active()
            start_chapter(obj.text.strip())
            waiting_answer_table = False

        elif cur is None:
            pass  # front matter before first chapter (title page, global TOC)

        elif kind == "heading2":
            flush_active()
            htext = obj.text.strip().lower()
            if htext == "answer key":
                phase = "answerkey"
                waiting_answer_table = True
            elif htext == "detailed explanations":
                phase = "explanations"
                waiting_answer_table = False

        elif kind == "question_marker" and phase == "questions":
            flush_active()
            active_kind = "question"
            active_no = int(QUESTION_RE.match(obj.text.strip()).group(1))
            handle_images_in_paragraph(obj, stem_parts)

        elif kind == "solution_marker" and phase == "explanations":
            flush_active()
            active_kind = "solution"
            active_no = int(SOLUTION_RE.match(obj.text.strip()).group(1))
            handle_images_in_paragraph(obj, expl_parts)

        elif kind == "table":
            if active_kind == "question" and not options and looks_like_options_table(obj):
                for r in obj.rows:
                    cells = [c.text.strip() for c in r.cells]
                    m = re.match(r"^[a-hA-H]\)\s*(.*)$", cells[0])
                    rest = m.group(1).strip()
                    parts = [rest] + [c for c in cells[1:] if c]
                    options.append(", ".join(p for p in parts if p))
            elif len(obj.columns) == 2 and looks_like_answer_key_table(obj):
                phase = "answerkey"
                rows = list(obj.rows)
                header = [c.text.strip() for c in rows[0].cells] if rows else []
                # a continuation table (Word split it across a page break) has no
                # repeated header row, so only skip row 0 when it actually is one
                start_idx = 1 if header and "question" in header[0].lower() else 0
                for r in rows[start_idx:]:
                    cells = [c.text.strip() for c in r.cells]
                    if len(cells) < 2:
                        continue
                    try:
                        qno = int(cells[0])
                    except ValueError:
                        continue
                    m = re.search(r"[a-zA-Z]", cells[1])
                    if m:
                        answer_key[qno] = m.group(0).lower()
                waiting_answer_table = False
            else:
                # embedded clinical/comparison table inside a stem or explanation
                txt = table_to_text(obj)
                if active_kind == "question":
                    stem_parts.append(txt)
                elif active_kind == "solution":
                    expl_parts.append(txt)
                pending_table_text_notes += 1

        elif kind == "para":
            text = obj.text.strip()
            if active_kind == "question":
                lettered = re.match(r"^[a-hA-H]\)\s*(.+)$", text) if text else None
                if obj.style.name == "List Paragraph" or lettered:
                    opt_text = lettered.group(1).strip() if lettered else text
                    if opt_text:
                        options.append(opt_text)
                    handle_images_in_paragraph(obj, stem_parts)
                else:
                    if text:
                        stem_parts.append(text)
                    handle_images_in_paragraph(obj, stem_parts)
            elif active_kind == "solution":
                if text:
                    expl_parts.append(text)
                handle_images_in_paragraph(obj, expl_parts)
            # else: stray paragraph outside question/solution scope (chapter intro etc) - ignore

        i += 1

    flush_active()
    if cur is not None:
        finalize_chapter()

    return cfg, chapters


def write_images(cfg, chapters):
    imgdir = cfg["imgdir"]
    if imgdir.exists():
        shutil.rmtree(imgdir)  # avoid orphaned files from a previous run's different image count
    total = 0
    for ch in chapters:
        chdir = imgdir / f"ch{ch['no']:02d}"
        for q in ch["questions"]:
            imgs = q.get("images") or []
            final_imgs = []
            for im in imgs:
                chdir.mkdir(parents=True, exist_ok=True)
                fname = f"c{ch['no']:02d}_q{q['no']:03d}_{im['ref']}.{im['ext']}"
                fpath = chdir / fname
                fpath.write_bytes(im["blob"])
                rel = fpath.relative_to(MARROW_DIR)
                final_imgs.append(dict(ref=im["ref"], file=str(rel)))
                total += 1
            q["images"] = final_imgs
    print(f"Wrote {total} images under {imgdir}")


def build_json(cfg, chapters):
    total_q = sum(len(ch["questions"]) for ch in chapters)
    out = dict(
        source=dict(
            title=f"MARROW ED8 {cfg['title']} Comprehensive Question Bank",
            file=cfg["src"].name,
            extracted_on=datetime.date.today().isoformat(),
            chapters=len(chapters),
            questions=total_q,
        ),
        chapters=[],
    )
    for ch in chapters:
        qlist = []
        for q in ch["questions"]:
            qid = f"MRW_{cfg['prefix']}_ED8_C{ch['no']:02d}_Q{q['no']:03d}"
            qlist.append(
                dict(
                    id=qid,
                    no=q["no"],
                    stem=q["stem"],
                    options=q["options"],
                    correct=q["correct"],
                    answer=q["answer"],
                    explanation=q["explanation"],
                    images=q["images"],
                )
            )
        out["chapters"].append(
            dict(no=ch["no"], title=ch["title"], page=ch.get("page"), questions=qlist)
        )
    return out


def verify(bank, cfg):
    problems = []
    total_q = 0
    missing_answer = 0
    bad_options = 0
    bad_correct = 0
    marker_mismatch = 0
    missing_files = 0
    for ch in bank["chapters"]:
        nos = [q["no"] for q in ch["questions"]]
        if sorted(nos) != list(range(1, len(nos) + 1)):
            problems.append(f"ch{ch['no']:02d} '{ch['title']}': question numbering gaps/dupes: {sorted(nos)}")
        for q in ch["questions"]:
            total_q += 1
            opts = q["options"]
            if len(opts) < 2 or len(set(opts)) != len(opts) or any(not o for o in opts):
                bad_options += 1
                problems.append(f"{q['id']}: bad options {opts}")
            if q["correct"] is None or not (0 <= q["correct"] < len(opts)):
                bad_correct += 1
                missing_answer += 1 if q["correct"] is None else 0
                problems.append(f"{q['id']}: correct idx {q['correct']} out of range for {len(opts)} options")
            marker_refs = set(int(m) for m in re.findall(r"\[\[IMG:(\d+)\]\]", q["stem"] + " " + q["explanation"]))
            img_refs = set(im["ref"] for im in q["images"])
            if marker_refs != img_refs:
                marker_mismatch += 1
                problems.append(f"{q['id']}: marker/image ref mismatch markers={marker_refs} images={img_refs}")
            for im in q["images"]:
                if not (MARROW_DIR / im["file"]).exists():
                    missing_files += 1
                    problems.append(f"{q['id']}: missing image file {im['file']}")
    print(f"--- verify {cfg['title']} ---")
    print(f"chapters: {len(bank['chapters'])}  questions: {total_q}")
    print(f"bad option sets: {bad_options}  bad/missing correct idx: {bad_correct}  marker/image mismatches: {marker_mismatch}  missing files: {missing_files}")
    if problems:
        print(f"first {min(20, len(problems))} problems of {len(problems)}:")
        for p in problems[:20]:
            print("  -", p)
    else:
        print("RESULT: PASS - no problems found")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True, choices=list(SUBJECTS.keys()))
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()
    cfg = SUBJECTS[args.subject]

    if args.verify_only:
        bank = json.loads(cfg["out"].read_text())
        verify(bank, cfg)
        return

    cfg2, chapters = extract(args.subject)
    write_images(cfg2, chapters)
    bank = build_json(cfg2, chapters)
    cfg["out"].write_text(json.dumps(bank, indent=2, ensure_ascii=False))
    print(f"Wrote {cfg['out']}")
    verify(bank, cfg)


if __name__ == "__main__":
    main()
