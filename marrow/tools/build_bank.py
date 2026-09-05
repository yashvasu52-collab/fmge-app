"""
Stage 5: join structure.json (questions/options/answer-key/solutions) with
the image manifest (figures + composited tiles + cropped vector tables)
into the final surgery_ed8.json bank.

Image placement: every image is assigned to the (chapter, question-no)
whose ordered content_blocks span encloses its (page, y) position — i.e.
the last content block appearing at or before the image, walking the
chapter's blocks in page/y order. This also gives the "last open block"
behaviour for images on a continuation page with no marker of its own.

For kind == "table" images, any content-block parts whose bbox falls
(mostly) inside the image's rect are the garbled vector-table text that
the image replaces — they are dropped from the explanation and a single
[[IMG:n]] marker is inserted in their place. For kind in
{"figure","figure_tile"}, no text is removed; the marker is inserted
after the nearest preceding paragraph.

Final images are copied (not moved — the _raw/ originals stay put) into
images/chNN/c{ch:02d}_q{no:03d}_sol_{ref}.png and referenced by that
relative path.
"""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
IMAGES_DIR = ROOT / "images"
BANK_PATH = ROOT / "surgery_ed8.json"

STRUCTURE_PATH = WORK / "structure.json"
MANIFEST_PATH = WORK / "images_manifest.json"


def load_manifest():
    data = json.loads(MANIFEST_PATH.read_text())
    # tolerate a couple of reasonable top-level shapes
    if isinstance(data, list):
        images = data
    else:
        images = data.get("images") or data.get("manifest") or data.get("items")
        assert images is not None, f"unrecognized manifest shape, top-level keys: {list(data.keys())}"
    norm = []
    for im in images:
        page = im.get("page") or im.get("page_number")
        if page is None and "page_index" in im:
            page = im["page_index"] + 1
        rect = im.get("rect") or im.get("bbox")
        kind = im.get("kind", "figure")
        file_ = im.get("file") or im.get("path") or im.get("output") or im.get("filename")
        xref = im.get("xref")
        assert page is not None and rect is not None and file_ is not None, f"missing fields in image entry: {im}"
        norm.append({"page": int(page), "rect": [float(v) for v in rect], "kind": kind, "file": file_, "xref": xref})
    return norm


def rects_overlap_ratio(a, b):
    """Fraction of rect a's area that overlaps rect b (0..1)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(1e-6, (ax1 - ax0) * (ay1 - ay0))
    return inter / area_a


def assign_images_to_chapter(chapter_images, content_blocks):
    """Return dict (owner,no) -> list of images, each image augmented with
    'anchor_index' = index into content_blocks of the last block at/before it."""
    # content_blocks assumed ordered by (page, y0) already (built that way in stage 3)
    keyed = []
    for cb in content_blocks:
        keyed.append((cb["page"], cb["bbox"][1]))

    def find_anchor(img):
        p, rect = img["page"], img["rect"]
        y0 = rect[1]
        best = -1
        for i, (cp, cy) in enumerate(keyed):
            if (cp, cy) <= (p, y0):
                best = i
            else:
                break
        return best

    assigned = {}
    for img in chapter_images:
        idx = find_anchor(img)
        if idx == -1:
            # image appears before any known content block (e.g. before Q1) -
            # fall back to the first block found
            if not content_blocks:
                continue
            idx = 0
        owner = content_blocks[idx]["owner"]
        no = content_blocks[idx]["no"]
        assigned.setdefault((owner, no), []).append({**img, "anchor_index": idx})
    return assigned


def build_text_with_images(parts, images, start_ref=0):
    """parts: ordered list of {text,bbox,page} for one question's stem OR one
    solution's explanation (both use the same shape). images: list of images
    anchored to that same scope (each has rect,page,kind,file,xref).
    Returns (text, images_out, next_ref) where images_out has 'ref' numbers
    starting at start_ref+1, so a caller can place stem images and
    explanation images in one continuous ref sequence for the question.
    """
    local = list(parts)  # list of dicts, will be mutated (marker sentinel inserted)
    images_out = []
    ref = start_ref

    # sort images by their (page, y0) so multiple images interleave correctly
    images_sorted = sorted(images, key=lambda im: (im["page"], im["rect"][1]))

    # We build a new sequence of "items", each either {"type":"text",...} or {"type":"img","ref":n}
    seq = [{"type": "text", **p} for p in local]

    for img in images_sorted:
        ref += 1
        img_page, img_rect = img["page"], img["rect"]

        if img["kind"] == "table":
            # remove any text items on the same page whose bbox mostly overlaps the table rect
            remove_idx = [
                i
                for i, it in enumerate(seq)
                if it["type"] == "text"
                and it["page"] == img_page
                and rects_overlap_ratio(it["bbox"], img_rect) > 0.5
            ]
        else:
            remove_idx = []

        if remove_idx:
            insert_at = min(remove_idx)
            seq = [it for i, it in enumerate(seq) if i not in remove_idx]
            # recompute insert_at after removal (count how many removed items were before insert_at)
            shift = sum(1 for i in remove_idx if i < insert_at)
            insert_at -= shift
        else:
            # find last text item at/before this image's (page, y0), insert after it
            insert_at = 0
            for i, it in enumerate(seq):
                if it["type"] != "text":
                    continue
                if (it["page"], it["bbox"][1]) <= (img_page, img_rect[1]):
                    insert_at = i + 1
                else:
                    break

        seq.insert(insert_at, {"type": "img", "ref": ref})
        images_out.append(
            {"ref": ref, "file": img["file"], "page": img_page, "rect": img_rect, "kind": img["kind"], "xref": img.get("xref")}
        )

    # render seq -> text
    chunks = []
    for it in seq:
        if it["type"] == "text":
            if it["text"].strip():
                chunks.append(it["text"].strip())
        else:
            chunks.append(f"[[IMG:{it['ref']}]]")
    text = "\n\n".join(chunks)
    return text, images_out, ref


def main():
    structure = json.loads(STRUCTURE_PATH.read_text())
    images_all = load_manifest()
    print(f"loaded {len(images_all)} images from manifest")

    chapters_out = []
    total_questions = 0
    total_images_used = 0
    stem_images_total = 0

    for ch in structure["chapters"]:
        p0, p1 = ch["pages"]
        ch_images = [im for im in images_all if p0 <= im["page"] <= p1]
        assigned = assign_images_to_chapter(ch_images, ch["content_blocks"])

        ans_key = ch["answer_key"]
        sol_by_no = {s["no"]: s for s in ch["solutions"]}
        q_by_no = {q["no"]: q for q in ch["questions"]}

        # stem parts per question no, in order (role=="stem" content_blocks) —
        # this is what lets a vignette image anchored to the *question*
        # (e.g. "look at this X-ray...") land inside the stem, between the
        # relevant paragraph and the options, instead of being misfiled
        # into the explanation.
        stem_parts_by_no = {}
        for cb in ch["content_blocks"]:
            if cb["owner"] == "question" and cb.get("role") == "stem":
                stem_parts_by_no.setdefault(cb["no"], []).append(
                    {"text": cb["text"], "bbox": cb["bbox"], "page": cb["page"]}
                )

        chdir = IMAGES_DIR / f"ch{ch['no']:02d}"
        chdir.mkdir(parents=True, exist_ok=True)

        questions_out = []
        for no in sorted(q_by_no):
            q = q_by_no[no]
            sol = sol_by_no[no]
            letter = ans_key[str(no)]
            correct = "abcd".index(letter)

            q_images = assigned.get(("question", no), [])
            sol_images = assigned.get(("solution", no), [])

            stem_parts = stem_parts_by_no.get(no) or [{"text": q["stem"], "bbox": [0, 0, 0, 0], "page": q["page"]}]
            stem_text, stem_images_out, next_ref = build_text_with_images(stem_parts, q_images, start_ref=0)
            if q_images:
                stem_images_total += len(q_images)
            explanation, expl_images_out, _ = build_text_with_images(sol["parts"], sol_images, start_ref=next_ref)

            images_out = stem_images_out + expl_images_out

            # copy files into images/chNN/ with final descriptive names
            final_images = []
            for im in images_out:
                src = ROOT / im["file"]
                ext = src.suffix or ".png"
                dst_name = f"c{ch['no']:02d}_q{no:03d}_sol_{im['ref']}{ext}"
                dst = chdir / dst_name
                if src.exists():
                    shutil.copyfile(src, dst)
                else:
                    print(f"  WARNING: source image missing on disk: {src}")
                final_images.append(
                    {
                        "ref": im["ref"],
                        "file": str(dst.relative_to(ROOT)),
                        "page": im["page"],
                        "rect": im["rect"],
                        "kind": im["kind"],
                        "xref": im.get("xref"),
                    }
                )
            total_images_used += len(final_images)

            qid = f"MRW_SUR_ED8_C{ch['no']:02d}_Q{no:03d}"
            questions_out.append(
                {
                    "id": qid,
                    "no": no,
                    "page": q["page"],
                    "stem": stem_text,
                    "options": q["options"],
                    "correct": correct,
                    "answer": letter,
                    "explanation": explanation,
                    "images": final_images,
                }
            )
            total_questions += 1

        chapters_out.append(
            {
                "no": ch["no"],
                "title": ch["title"],
                "pages": ch["pages"],
                "questions": questions_out,
            }
        )
        print(f"ch{ch['no']:02d}: {len(questions_out)} questions, images used so far: {total_images_used}")

    bank = {
        "source": {
            "title": "MARROW ED8 Surgery Comprehensive Question Bank",
            "file": "Surgery_ed8.pdf",
            "extracted_on": "2026-09-02",
            "chapters": len(chapters_out),
            "questions": total_questions,
        },
        "chapters": chapters_out,
    }
    BANK_PATH.write_text(json.dumps(bank, ensure_ascii=False, indent=1))
    print(f"wrote {BANK_PATH} ({BANK_PATH.stat().st_size} bytes)")
    print(f"total questions: {total_questions}, total images placed: {total_images_used}, images embedded in stems (vignette images): {stem_images_total}")


if __name__ == "__main__":
    main()
