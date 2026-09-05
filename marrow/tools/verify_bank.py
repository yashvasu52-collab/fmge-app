"""
Stage 6: acceptance check for surgery_ed8.json. Run last.

Checks:
- 54 chapters, 1256 questions total; per-chapter counts internally consistent
- every question has exactly 4 non-empty, distinct options; correct in 0..3
- no U+FFFD, no control chars, no "Sold by @itachibot" anywhere in output
- decoded-English sanity: dictionary word-hit ratio per chapter above threshold
- every [[IMG:n]] marker has a matching images[] entry, and every referenced
  file exists on disk

Writes work/report.txt and prints a compact summary.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = ROOT / "surgery_ed8.json"
REPORT_PATH = ROOT / "work" / "report.txt"
DICT_PATH = Path("/usr/share/dict/words")

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
WORD_RE = re.compile(r"[A-Za-z']+")


def load_wordset():
    words = set()
    for line in DICT_PATH.read_text(errors="ignore").splitlines():
        w = line.strip().lower()
        if w:
            words.add(w)
    return words


def main():
    lines = []

    def log(s=""):
        print(s)
        lines.append(s)

    bank = json.loads(BANK_PATH.read_text())
    chapters = bank["chapters"]
    wordset = load_wordset()

    anomalies = []

    # ---- counts ----
    n_chapters = len(chapters)
    n_questions = sum(len(ch["questions"]) for ch in chapters)
    log(f"chapters: {n_chapters}  questions: {n_questions}")
    ok_counts = n_chapters == 54 and n_questions == 1256
    if not ok_counts:
        anomalies.append(f"count mismatch: expected 54/1256, got {n_chapters}/{n_questions}")

    raw_all = json.dumps(bank, ensure_ascii=False)
    has_fffd = "�" in raw_all
    has_watermark = "itachibot" in raw_all
    has_control = bool(CONTROL_RE.search(raw_all))
    log(f"U+FFFD present: {has_fffd}   watermark leak: {has_watermark}   control chars: {has_control}")
    if has_fffd:
        anomalies.append("U+FFFD found in output")
    if has_watermark:
        anomalies.append("watermark text leaked into output")
    if has_control:
        anomalies.append("control characters found in output")

    total_images_referenced = 0
    missing_files = []
    bad_markers = []
    bad_options = []
    bad_correct = []
    per_chapter_word_ratio = []

    for ch in chapters:
        chno = ch["no"]
        n_words = 0
        n_hits = 0
        for q in ch["questions"]:
            opts = q["options"]
            if len(opts) != 4 or any(not o.strip() for o in opts) or len(set(opts)) != 4:
                bad_options.append(q["id"])
            if not (0 <= q["correct"] <= 3):
                bad_correct.append(q["id"])

            # [[IMG:n]] markers can appear in the stem (vignette images, e.g.
            # "look at this X-ray") as well as in the explanation.
            markers = set(
                int(m) for m in re.findall(r"\[\[IMG:(\d+)\]\]", q["stem"] + " " + q["explanation"])
            )
            img_refs = set(im["ref"] for im in q["images"])
            if markers != img_refs:
                bad_markers.append((q["id"], sorted(markers), sorted(img_refs)))
            for im in q["images"]:
                total_images_referenced += 1
                f = ROOT / im["file"]
                if not f.exists():
                    missing_files.append((q["id"], im["file"]))

            for text in [q["stem"], *opts, q["explanation"]]:
                for w in WORD_RE.findall(text):
                    wl = w.lower()
                    if len(wl) < 3:
                        continue
                    n_words += 1
                    if wl in wordset or wl.rstrip("s") in wordset:
                        n_hits += 1
        ratio = (n_hits / n_words) if n_words else 1.0
        per_chapter_word_ratio.append((chno, ratio, n_words))
        if ratio < 0.75:
            anomalies.append(f"chapter {chno} low dictionary-word ratio: {ratio:.2f} ({n_words} words sampled)")

    log(f"total image references: {total_images_referenced}, missing files: {len(missing_files)}")
    log(f"bad option sets: {len(bad_options)}  bad correct-index: {len(bad_correct)}  marker/image mismatches: {len(bad_markers)}")

    worst = sorted(per_chapter_word_ratio, key=lambda x: x[1])[:5]
    log("lowest dictionary-word-ratio chapters: " + ", ".join(f"ch{c}={r:.2f}" for c, r, n in worst))

    if missing_files:
        anomalies.append(f"{len(missing_files)} referenced image files missing on disk")
        for qid, f in missing_files[:10]:
            log(f"  MISSING: {qid} -> {f}")
    if bad_options:
        anomalies.append(f"{len(bad_options)} questions with bad option sets")
        for qid in bad_options[:10]:
            log(f"  BAD OPTIONS: {qid}")
    if bad_correct:
        anomalies.append(f"{len(bad_correct)} questions with out-of-range correct index")
    if bad_markers:
        anomalies.append(f"{len(bad_markers)} questions with [[IMG:n]]/images[] mismatch")
        for qid, m, r in bad_markers[:10]:
            log(f"  MARKER MISMATCH: {qid} markers={m} images={r}")

    log("")
    if anomalies:
        log(f"RESULT: FAIL ({len(anomalies)} anomalies)")
        for a in anomalies:
            log(f"  - {a}")
    else:
        log("RESULT: PASS — all gates satisfied")

    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {REPORT_PATH}")

    if anomalies:
        sys.exit(1)


if __name__ == "__main__":
    main()
