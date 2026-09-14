#!/usr/bin/env python3
"""
video-to-skill - Termux-ready pipeline (video -> text -> skill)
Converts a video (URL or local path) into a book, then a Hermes skill.
The transcript (text) is the base of the skill. Fully runnable on Termux
(Samsung Fold 5) against a locally built whisper.cpp.

Usage:
  python3 video_to_skill.py <video-url-or-path> [prompt]

Whisper setup (one-time):
  cd ~/whisper.cpp && cmake -B build -DCMAKE_BUILD_TYPE=Release \
      -DWHISPER_SDL2=OFF -DWHISPER_BUILD_TESTS=OFF -DWHISPER_COMMON_FFMPEG=ON
  cmake --build build -j
  cd models && bash download-ggml-model.sh base.en
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

# --- whisper.cpp locations (built locally, see docstring) ---
WHISPER_CLI = Path("~/whisper.cpp/build/bin/whisper-cli").expanduser()
WHISPER_MODEL = Path("~/whisper.cpp/models/ggml-base.en.bin").expanduser()

# --- Section detection patterns ---
SECTION_PATTERNS = [
    r"^(step|phase|part|section|chapter|episode|number|number\s*\d+|let's\s+\w+)\s+(.*)",
    r"^(first|second|third|fourth|next|then|after|finally|last)\b\s*(.*)",
    r"^(\d+)[\.:\)]\s*(.*)",
    r"^(-{3,}|\*{3,}|#{3,})\s*(.*)",
    r"^(##+)\s*(.*)",
]

KEYWORD_THEMES = {
    "tutorial": ["how to", "learn", "guide", "teach", "tutorial", "step by step"],
    "analysis": ["analyze", "analysis", "breakdown", "examining", "study"],
    "process": ["process", "workflow", "pipeline", "system", "method"],
    "tools": ["tool", "software", "app", "program", "code", "script"],
    "strategy": ["strategy", "approach", "technique", "method", "framework"],
    "review": ["review", "rated", "score", "pros", "cons", "verdict"],
    "news": ["news", "update", "report", "breaking", "announced"],
    "comparison": ["compare", "vs", "versus", "difference", "compared"],
    "opinion": ["opinion", "thoughts", "feel", "believe", "think"],
    "interview": ["interview", "conversing", "chatting with", "asking"],
}

IMPORTANT_SENTENCE_PATTERNS = [
    r"(?:most important|key takeaway|crucial|essential|critical|fundamental|vital)",
    r"(?:remember that|note that|keep in mind|pay attention)",
    r"(?:the main point|the key idea|the bottom line|essentially)",
    r"(?:in conclusion|to summarize|overall|ultimately|finally)",
    r"(?:if you only remember|don't forget|make sure|be sure)",
    r"(?:here's the thing|here's what matters|what's really important)",
    r"(?:pro tip|bonus tip|secret|hack|trick|shortcut)",
    r"(?:warning|caution|heads up|watch out|be careful)",
    r"(?:common mistake|avoid this|don't do this|this is wrong)",
]


def ensure_whisper():
    """Fail loudly if whisper is not set up. No silent stubs."""
    missing = []
    if not WHISPER_CLI.exists():
        missing.append("whisper-cli binary (build it: see 'Whisper setup' above)")
    if not WHISPER_MODEL.exists():
        missing.append("ggml-base.en model (download it: cd ~/whisper.cpp/models && bash download-ggml-model.sh base.en)")
    if missing:
        print("ERROR - whisper.cpp not ready:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(1)


def download_video(url: str) -> str:
    """Download a remote video with yt-dlp (Termux-safe, ffmpeg available)."""
    out = "video_download.mp4"
    cmd = ["yt-dlp", "-f", "best[height<=720]", "-o", out, url]
    print("Downloading video...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {r.stderr.strip()[:400]}")
    return out


def transcribe(video_file: str) -> str:
    """Run whisper-cli on the video (ffmpeg support is compiled in, so
    .mp4/.mkv are read directly) and return the transcript text."""
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    stem = out_dir / "transcript"
    cmd = [
        str(WHISPER_CLI),
        "-m", str(WHISPER_MODEL),
        "-t", "4",                 # 4 threads on the Fold
        "-otxt",                   # write plain-text transcript
        "-of", str(stem),
        video_file,
    ]
    print("Transcribing with whisper.cpp (this can take a few minutes)...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(f"whisper-cli failed: {r.stderr.strip()[:400]}")
    text = (out_dir / "transcript.txt").read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Whisper produced an empty transcript - check the video has audio.")
    return text


def count_frames(video_file: str) -> int:
    """Cheap visual summary: sample a few frames for later vision_analyze."""
    out_dir = Path("output/frames")
    out_dir.mkdir(parents=True, exist_ok=True)
    # wipe stale frames so the count is honest
    for old in out_dir.glob("frame_*.jpg"):
        old.unlink()
    cmd = [
        "ffmpeg", "-i", video_file,
        "-vf", "select=gt(scene\\,0.3)",
        "-vsync", "vfr", "-frame_pts", "1", "-q:v", "2",
        str(out_dir / "frame_%04d.jpg"), "-hide_banner",
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return len(list(out_dir.glob("frame_*.jpg")))


def gate_skill_file(skill_path: Path) -> Path:
    """Hard gate: run validate_skill.py on a freshly written skill file.

    Exit 0 -> clean, return the path (pipeline may continue).
    Exit 1 -> hollow / placeholder / missing section, raise so the pipeline
    fails LOUDLY instead of handing a stub to the user.
    A missing validator is treated as a failure, never silently skipped.
    """
    validator = Path(__file__).resolve().parent / "validate_skill.py"
    if not validator.exists():
        raise RuntimeError("validate_skill.py not found next to video_to_skill.py - cannot run the gate.")
    r = subprocess.run([sys.executable, str(validator), str(skill_path)],
                       capture_output=True, text=True)
    for line in r.stdout.strip().splitlines():
        print(f"[gate] {line}")
    if r.returncode != 0:
        raise RuntimeError(
            f"validate_skill.py FAILED on {skill_path.name} (exit {r.returncode}). "
            f"The generated skill is not clean. Edit it from the transcript "
            f"(remove any 'edit me' / todo / tbd / placeholder lines and fill real "
            f"content) and re-run: python3 validate_skill.py {skill_path.name}"
        )
    return skill_path


def slugify(text: str, max_len: int = 32):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "video-derived-skill"


def detect_theme(transcript: str) -> list[str]:
    """Detect what themes/topics the transcript covers."""
    text_lower = transcript.lower()
    themes = []
    for theme, keywords in KEYWORD_THEMES.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score >= 2:
            themes.append(theme)
    return themes[:3] if themes else ["general"]


def extract_sections(transcript: str) -> list[dict]:
    """Try to identify logical sections in the transcript."""
    lines = transcript.split("\n")
    sections = []
    current_section = {"title": "Introduction", "content": []}

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        matched = False
        for pattern in SECTION_PATTERNS:
            m = re.match(pattern, line_stripped, re.IGNORECASE)
            if m:
                # Save current section if it has content
                if current_section["content"]:
                    sections.append(current_section)
                # Start new section
                title = m.group(2) if m.lastindex >= 2 else m.group(1)
                # Clean up title
                title = re.sub(r"^(step|phase|part|section|chapter)\s*", "", title, flags=re.IGNORECASE).strip()
                title = re.sub(r"^\d+[.:\)]\s*", "", title).strip()
                current_section = {"title": title[:60], "content": []}
                matched = True
                break

        if not matched:
            current_section["content"].append(line_stripped)

    if current_section["content"]:
        sections.append(current_section)

    return sections if len(sections) > 1 else []


def extract_key_points(transcript: str, max_points: int = 8) -> list[str]:
    """Extract the most important sentences from the transcript."""
    sentences = re.split(r"[.!?\n]{1,3}", transcript)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

    scored = []
    for sent in sentences:
        score = 0
        sent_lower = sent.lower()
        for pattern in IMPORTANT_SENTENCE_PATTERNS:
            if re.search(pattern, sent_lower):
                score += 3
        # Bonus for length (more detail = more likely important)
        score += min(len(sent) / 100, 2)
        # Bonus for containing numbers/stats
        if re.search(r"\d+%|\d+\s*(million|billion|thousand)|#\d+", sent_lower):
            score += 2
        scored.append((score, sent))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [s for _, s in scored[:max_points]]


def extract_procedures(transcript: str, max_steps: int = 6) -> list[str]:
    """Try to extract numbered or sequential procedures."""
    lines = transcript.split("\n")
    procedures = []
    current_step = None
    step_number = 0

    for line in lines:
        line_stripped = line.strip()
        # Match numbered steps
        step_match = re.match(r"^(\d+)[\.\)]\s+(.+)", line_stripped)
        if step_match:
            if current_step and len(current_step) > 10:
                procedures.append(current_step)
            step_number = int(step_match.group(1))
            current_step = step_match.group(2).strip()
            continue

        # Match "first", "second", etc.
        ordinal_match = re.match(
            r"^(first|second|third|fourth|next|then|afterwards|finally|last)\b[,.:]\s+(.+)",
            line_stripped, re.IGNORECASE
        )
        if ordinal_match:
            if current_step and len(current_step) > 10:
                procedures.append(current_step)
            current_step = f"{ordinal_match.group(1).capitalize()}: {ordinal_match.group(2).strip()}"
            continue

        # Continuation of current step
        if current_step and len(line_stripped) > 5:
            current_step += " " + line_stripped

    if current_step and len(current_step) > 10:
        procedures.append(current_step)

    # Also look for bullet points
    bullets = [l.strip("-•*") for l in lines if re.match(r"^[\s]*[-•*]\s+", l)]
    procedures.extend(bullets)

    # Deduplicate and limit
    seen = set()
    unique = []
    for p in procedures:
        p_clean = p.strip()
        if p_clean and p_clean not in seen and len(p_clean) > 15:
            seen.add(p_clean)
            unique.append(p_clean)
            if len(unique) >= max_steps:
                break

    return unique


def generate_skill_name(transcript: str, prompt: str) -> tuple[str, str]:
    """Generate a meaningful skill name and description from transcript content."""
    # Try to extract topic from transcript
    words = re.findall(r"\b\w{4,}\b", transcript.lower())
    common = [w for w, c in Counter(words).most_common(20)
              if c >= 3 and w not in ("this", "that", "with", "from", "have", "will", "been",
                                       "they", "their", "there", "about", "would", "could",
                                       "should", "what", "when", "where", "which", "than",
                                       "then", "into", "over", "also", "just", "made",
                                       "only", "very", "much", "each", "other", "some",
                                       "more", "most", "being", "because", "before",
                                       "through", "between", "after", "these", "those")]

    # Look for the main topic
    topic_candidates = common[:5]
    skill_base = prompt if prompt else " ".join(topic_candidates[:3])

    name = slugify(skill_base)
    desc = f"Extracted from video: {slugify(skill_base, 30)}."
    if len(desc) > 59:
        desc = desc[:59]

    return name, desc


def build_skill(transcript: str, prompt: str) -> str:
    """Build a proper Hermes SKILL.md from transcript content."""
    skill_name, skill_desc = generate_skill_name(transcript, prompt)
    themes = detect_theme(transcript)
    sections = extract_sections(transcript)
    key_points = extract_key_points(transcript)
    procedures = extract_procedures(transcript)

    # Build the skill content
    lines = []
    lines.append("---")
    lines.append(f"name: {skill_name}")
    lines.append(f"description: \"{skill_desc}\"")
    lines.append("version: 0.1.0")
    lines.append("author: video-to-skill")
    lines.append("license: MIT")
    lines.append("platforms: [linux, macos, windows]")
    lines.append("metadata:")
    lines.append("  hermes:")
    lines.append("    tags: [video-derived, automation]")
    related = [f"video-to-skill-{t}" for t in themes if t != "general"]
    lines.append(f"    related_skills: [{', '.join(related)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {skill_name.replace('-', ' ').title()}")
    lines.append("")

    # Overview from transcript summary
    lines.append("## Overview")
    lines.append(f"Skill derived from video content. Themes: {', '.join(themes)}.")
    lines.append("")

    # Key takeaways
    if key_points:
        lines.append("## Key Takeaways")
        for i, point in enumerate(key_points, 1):
            # Truncate very long points
            if len(point) > 200:
                point = point[:197] + "..."
            lines.append(f"{i}. {point}")
        lines.append("")

    # Procedures/Steps
    if procedures:
        lines.append("## Procedure")
        for i, step in enumerate(procedures, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

    # When to use
    lines.append("## When to Use")
    lines.append(f"- Topics covered: {', '.join(themes)}")
    lines.append("- [Review transcript for specific use cases]")
    lines.append("")

    # Structure from sections
    if sections:
        lines.append("## Content Structure")
        for sec in sections[:5]:  # Limit to first 5 sections
            lines.append(f"- **{sec['title']}**: {' '.join(sec['content'][:2])}...")
        lines.append("")

    # Full transcript reference
    lines.append("## Full Transcript")
    lines.append("See the companion book file for complete transcript and analysis.")
    lines.append("")

    # Verification
    lines.append("## Verification")
    lines.append("- [ ] Review transcript in companion book for accuracy")
    lines.append("- [ ] Validate key points against original video")
    lines.append("- [ ] Test procedures with actual example")
    lines.append("")

    return "\n".join(lines)


def process_video(video_input: str, prompt: str) -> dict:
    ensure_whisper()

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"Processing: {video_input}")
    video_file = download_video(video_input) if video_input.startswith(("http", "https")) else video_input
    if not Path(video_file).exists():
        raise RuntimeError(f"Video not found: {video_file}")

    transcript = transcribe(video_file)          # step: video -> text
    frames = count_frames(video_file)

    # --- book ---
    book_path = output_dir / f"book_{timestamp}.md"
    book_path.write_text(
        f"# Video Book - {timestamp}\n\n"
        f"## Source\nVideo: {video_input}\nPrompt: {prompt}\n\n"
        f"## Transcript\n{transcript}\n\n"
        f"## Visual Analysis\n- {frames} key frames in output/frames/ "
        f"(use vision_analyze in Hermes for detail).\n\n"
        f"## Action Items\n- {prompt}\n"
        f"- Review the transcript above and distill techniques.\n",
        encoding="utf-8",
    )

    # --- skill (content-driven, gate-validated) ---
    skill_content = build_skill(transcript, prompt)
    skill_path = output_dir / f"skill_{timestamp}.md"
    skill_path.write_text(skill_content, encoding="utf-8")
    gate_skill_file(skill_path)

    return {
        "status": "success",
        "book": str(book_path),
        "skill": str(skill_path),
        "transcript_chars": len(transcript),
        "frames": frames,
        "gated": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="video-to-skill: video -> text -> Hermes skill (Termux)")
    parser.add_argument("video", help="Video URL or local path")
    parser.add_argument("prompt", nargs="?", default="Extract techniques into a skill",
                        help="What to focus on (also used as the skill name slug)")
    args = parser.parse_args()
    try:
        result = process_video(args.video, args.prompt)
    except RuntimeError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))
