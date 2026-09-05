"""
Remove the pirate-reseller watermark image ("Sold by @Itachibot...") from all marrow/*.json
banks. It's re-encoded slightly differently every time it's embedded (different JPEG/PNG bytes,
so SHA-256 alone misses most copies), but every confirmed instance across 3 subjects and 1569
samples landed on exactly one of three pixel dimensions with a mostly-blank body -- that's a much
more reliable signature than the hash. Also keeps the original hash check for the one exact-copy
cluster, as a belt-and-suspenders fallback.
"""
import hashlib
import json
import re
from pathlib import Path

from PIL import Image
import numpy as np

MARROW_DIR = Path(__file__).resolve().parent.parent
WATERMARK_HASH = "eb646420dfd108ca5f520b10bb6fe3e8a55fd062bdaabdf90153d912fd3bfc81"
WATERMARK_DIMS = {(266, 224), (264, 226), (1224, 1584)}
MIN_BLANK_FRACTION = 0.5  # safety guard against a legit diagram coincidentally matching dims

FILES = [
    "psychiatry_ed8.json", "anaesthesia_ed8.json", "ent_ed8.json", "ophthalmology_ed8.json",
    "forensic_medicine_ed8.json", "pharmacology_ed8.json", "psm_ed8.json",
    "biochemistry_ed8.json", "dermatology_ed8.json", "pediatrics_ed8.json",
    "microbiology_ed8.json", "medicine_ed8.json",
    "obgyn_ed8.json", "anatomy_ed8.json", "orthopaedics_ed8.json", "pathology_ed8.json",
    "radiology_ed8.json",
]


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_watermark(path):
    if file_hash(path) == WATERMARK_HASH:
        return True
    try:
        im = Image.open(path)
    except Exception:
        return False
    if im.size not in WATERMARK_DIMS:
        return False
    blank_frac = (np.array(im.convert("L")) > 245).mean()
    return blank_frac >= MIN_BLANK_FRACTION


def strip_markers_and_renumber(text, keep_old_to_new):
    def repl(m):
        old = int(m.group(1))
        new = keep_old_to_new.get(old)
        return f"[[IMG:{new}]]" if new else ""
    return re.sub(r"\[\[IMG:(\d+)\]\]", repl, text)


def main():
    total_removed = 0
    for fname in FILES:
        path = MARROW_DIR / fname
        d = json.loads(path.read_text())
        removed_here = 0
        for ch in d["chapters"]:
            for q in ch["questions"]:
                imgs = q["images"]
                if not imgs:
                    continue
                kept = []
                keep_old_to_new = {}
                for im in imgs:
                    fpath = MARROW_DIR / im["file"]
                    if fpath.exists() and is_watermark(fpath):
                        removed_here += 1
                        fpath.unlink()
                    else:
                        keep_old_to_new[im["ref"]] = len(kept) + 1
                        kept.append(im)
                if len(kept) != len(imgs):
                    for new_ref, im in enumerate(kept, start=1):
                        im["ref"] = new_ref
                    q["images"] = kept
                    q["stem"] = strip_markers_and_renumber(q["stem"], keep_old_to_new)
                    q["explanation"] = strip_markers_and_renumber(q["explanation"], keep_old_to_new)
        if removed_here:
            path.write_text(json.dumps(d, indent=2, ensure_ascii=False))
        print(f"{fname}: removed {removed_here} watermark image(s)")
        total_removed += removed_here
    print(f"TOTAL removed: {total_removed}")


if __name__ == "__main__":
    main()
