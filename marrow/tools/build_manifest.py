"""
Build marrow/manifest.json: a tiny index of every *_ed8.json subject bank (title, file,
chapter/question counts) so the app's subject-list screen can show all subjects without
fetching all of them upfront -- each subject's full JSON is only fetched when opened.
"""
import json
from pathlib import Path

MARROW_DIR = Path(__file__).resolve().parent.parent


def main():
    manifest = []
    for path in sorted(MARROW_DIR.glob("*_ed8.json")):
        d = json.loads(path.read_text())
        src = d["source"]
        title = src["title"].replace("MARROW ED8 ", "").replace(" Comprehensive Question Bank", "")
        manifest.append(dict(
            key=path.stem,
            file=path.name,
            title=title,
            chapters=src["chapters"],
            questions=src["questions"],
        ))
    manifest.sort(key=lambda m: m["title"])
    out = MARROW_DIR / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Wrote {out} ({len(manifest)} subjects)")
    for m in manifest:
        print(f"  {m['title']:20} {m['chapters']:4} chapters  {m['questions']:5} questions  -> {m['file']}")


if __name__ == "__main__":
    main()
