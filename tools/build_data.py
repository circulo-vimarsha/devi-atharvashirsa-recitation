#!/usr/bin/env python3
"""Build private/text.json (the Sanskrit text, Devanagari + IAST, verse by verse and line by line)
from the akṣara app's devi data. With --recording, also private/timing.json and private/recitation.mp3
from one of the app's teaching recordings (the whole recitation is timed by tools/align.py instead).

    python3 tools/build_data.py <devi-folder> [--recording guruji-1]

<devi-folder> holds book.json and recordings.json (made by akshara/devi_book.py). Only the Sanskrit
is taken: no translation, notes or teachings from the book."""
import json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP = re.compile(r"[।॥|–०-९0-9]")

def words_of(piece):
    return [w for w in STOP.sub(" ", piece).split() if re.search("[ऀ-ॿ]", w)]

def pieces(line):
    """the line as words (numbered in the line) and the stops between them, as the page draws it"""
    out, n = [], 0
    for tok in line.split():
        for piece in re.split(r"(?=[।॥])|(?<=[।॥])", tok):
            if not piece:
                continue
            if words_of(piece):
                out.append({"w": piece, "i": n}); n += 1
            else:
                out.append({"p": piece})
    return out

def main():
    src = Path(sys.argv[1]).expanduser()
    name = sys.argv[sys.argv.index("--recording") + 1] if "--recording" in sys.argv else None
    book = json.loads((src / "book.json").read_text())
    verses = [{"n": v["n"], "lines": [{"deva": d, "iast": i, "pieces": pieces(d)}
                                      for d, i in zip(v["deva"], v["iast"])]} for v in book["verses"]]
    (ROOT / "private/text.json").write_text(json.dumps({"verses": verses}, ensure_ascii=False, indent=0))
    print(f"{len(verses)} verses")
    if name is None:
        return
    recs = json.loads((src / "recordings.json").read_text())
    rec = next(r for r in recs if r["file"].startswith(name))
    words = []
    for c in rec["clips"]:
        for k, _ in enumerate(c["words"]):
            words.append({"v": c["v"], "l": c["line"], "w": c["word"] + k,
                          "t0": c["at"][k], "t1": c["at"][k + 1]})
    words.sort(key=lambda x: x["t0"])
    timing = {"audio": "audio/recitation.mp3", "who": rec.get("who", ""), "words": words,
              "verses": sorted({w["v"] for w in words})}
    (ROOT / "private/timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=0))
    shutil.copy(src / rec["file"], ROOT / "private/recitation.mp3")
    print(f"{len(words)} timed words, verses voiced: {timing['verses']}")

if __name__ == "__main__":
    main()
