#!/usr/bin/env python3
"""validate_skill.py — hard gate for generated Hermes skills.

Exit 0 -> file is clean, pipeline may continue
Exit 1 -> file is hollow, pipeline must fail
"""

import sys
import re

# Placeholder strings that mark an unfilled / hollow section.
# NOTE: no empty-string entry here. The original draft ended the list with " "
# (a single space); `" " in text` is True for almost any file, which would have
# made this gate fail *every* file. Removed.
PLACEHOLDERS = [
    "fill from transcript",
    "fill in from transcript",
    "todo",
    "tbd",
    "placeholder",
    "to be distilled",
]

# Section headings the pipeline is expected to populate.
TRANSCRIPT = "transcript"
AUTHORED = ["when to use", "procedure", "verification"]


def section_body(text: str, name: str) -> str:
    """Return the body of the FIRST '## <...>' heading that CONTAINS `name`
    (case-insensitive), up to the next '## ' heading or EOF. Returns '' if absent.

    Matching "contains" (not "equals") is deliberate: the pipeline writes the
    transcript block under a heading like `## Source Transcript Excerpt`, so a
    strict `## transcript` match would miss it. This is also more forgiving for
    hand-authored skills.

    (The original draft used ``r"##\\s*transcript\\s*\\n(.+?)(?=\\n|\\Z)"`` which,
    with a lazy ``.+?`` and a newline lookahead, captured only the FIRST character
    of the section — so the "too short" test compared against ~1 char. This helper
    captures the whole section body instead.)
    """
    pat = re.compile(r"^##\s+[^\n]*?" + re.escape(name) + r"[^\n]*$", re.M | re.I)
    m = pat.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return (rest[:nxt.start()] if nxt else rest).strip()


def main():
    if len(sys.argv) < 2:
        print("usage: validate_skill.py <skill.md>")
        return 2

    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"FAIL: cannot read file: {e}")
        return 1

    # 1. No placeholder strings in the AUTHORED sections (When to Use / Procedure /
    #    Verification). We deliberately do NOT scan the verbatim Transcript block:
    #    a real transcript can legitimately contain the word "todo", and this gate
    #    must not false-trip on the source material.
    authored = "\n".join(section_body(text, s) for s in AUTHORED)
    low = authored.lower()
    for p in PLACEHOLDERS:
        if p in low:
            print(f"FAIL: placeholder found in authored sections: {p!r}")
            return 1

    # 2. Transcript section must be populated (real text, not just a heading).
    if len(section_body(text, TRANSCRIPT)) < 200:
        print("FAIL: transcript section missing or too short")
        return 1

    # 3. Procedure must contain real steps, not a stub.
    if len(section_body(text, "procedure")) < 100:
        print("FAIL: procedure section missing or too short")
        return 1

    # 4. Verification section must exist and be non-empty.
    if len(section_body(text, "verification")) < 50:
        print("FAIL: verification section missing or too short")
        return 1

    print("PASS: skill file is clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
