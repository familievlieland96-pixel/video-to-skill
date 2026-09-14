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

# --- whisper.cpp locations (built locally, see docstring) ---
WHISPER_CLI = Path("~/whisper.cpp/build/bin/whisper-cli").expanduser()
WHISPER_MODEL = Path("~/whisper.cpp/models/ggml-base.en.bin").expanduser()


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
        f"## Transcript (base of the skill)\n{transcript}\n\n"
        f"## Visual Analysis\n- {frames} key frames in output/frames/ "
        f"(use vision_analyze in Hermes for detail).\n\n"
        f"## Action Items\n- {prompt}\n"
        f"- Review the transcript above and distill techniques into a skill.\n",
        encoding="utf-8",
    )

    # --- skill (genuine draft, gate-checked below) ---
    skill_name = slugify(prompt)
    desc = (f"Video-derived draft: focus on {slugify(prompt, 24)}; verify against the source video before relying on it.")
    skill_path = output_dir / f"skill_{timestamp}.md"
    transcript_excerpt = transcript[:3000]
    skill_path.write_text(
        "---\n"
        f"name: {skill_name}\n"
        f'description: "{desc}"\n'
        "version: 0.1.0\n"
        "author: Bossman via video-to-skill (draft - human review required)\n"
        "license: MIT\n"
        "platforms: [linux, macos, windows]\n"
        "metadata:\n"
        "  hermes:\n"
        "    tags: [video-derived, draft, automation]\n"
        "    related_skills: [video-to-skill, hermes-agent-skill-authoring]\n"
        "---\n"
        f"# {skill_name}\n"
        "\n"
        "Draft skill generated by the video-to-skill pipeline. The **transcript below is the\n"
        "source of truth** for every claim in this skill. Nothing here was invented: review\n"
        "and edit, then update the version number before trusting it.\n"
        "\n"
        f"## Source Transcript Excerpt\n"
        f"```\n{transcript_excerpt}\n```\n"
        "\n"
        f"## When to Use\n"
        f"- Focus: {prompt}\n"
        "- Use this draft as a working structure to distill into a real skill: replace each\n"
        "  draft step below with the specific technique it illustrates, quoted or closely\n"
        "  paraphrased from the transcript excerpt above.\n"
        "\n"
        "## Procedure\n"
        "1. Read the full transcript in the accompanying `book_*.md` (same `output/` directory).\n"
        "2. For each 'edit me' step below, rewrite it from a specific passage of the\n"
        "   transcript - keep it a draft until a human has checked it.\n"
        "3. Draft steps - rewrite each from a specific transcript passage:\n"
        "   - [edit me - technique not yet extracted from the transcript]\n"
        "   - [edit me - technique not yet extracted from the transcript]\n"
        "   - [edit me - technique not yet extracted from the transcript]\n"
        "4. When done, update `version:` above and re-run the gate:\n"
        "   `python3 validate_skill.py <this file>`\n"
        "\n"
        "## Verification\n"
        "- Every bullet in Procedure traces back to a specific line of the source transcript -\n"
        "  no step was invented by the pipeline.\n"
        "- `name:` is a valid slug (no spaces or special characters).\n"
        "- The gate script exits 0 on this file (`validate_skill.py <this file>`).\n",
        encoding="utf-8",
    )
    skill_path = gate_skill_file(skill_path)

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
