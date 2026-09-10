# video-to-skill

Video to Skill pipeline - Turn any video (URL or local path) into structured text/book + auto-generated or tweaked Hermes skills. Now with last30days integration for real sentiment from the last 30 days.

**Fully runnable on Termux (Android)** — designed for Samsung Fold 5 / Termux environment with pkg installs, $HOME paths, whisper.cpp, no sudo, and Termux-specific setup. Works on Linux/macOS/Windows too.

Built as the pro addon layer for Robin Agent Plus / The Block. Leaves beginner client Robin untouched. Uses only our tools (terminal, vision_analyze, skill_manage, document-to-action-items, llm-wiki, last30days). No Microsoft.

## New: last30days Integration (added value)
After building the book from video frames/transcript, the pipeline now:
- Extracts key topics.
- Runs last30days for grounded "what people actually say" (X, Reddit, YouTube, TikTok, HN, Polymarket, web) with citations and doctor health check.
- Folds the sentiment report into the book and final generated skill.
This makes skills data-backed, trend-aware, and stronger for inventory, reviews, ads, and island business ops.

## Features
- Downloads video with yt-dlp.
- Extracts scene-aware frames with ffmpeg.
- Transcribes with whisper.cpp (or fallback).
- Analyzes frames with vision.
- Builds "the book" (timestamped summary, insights, action items + last30days sentiment).
- Auto-authors a full Hermes SKILL.md (follows hermes-agent-skill-authoring standards).
- Saves to output/ for easy loading/tweaking.

## Termux Setup (required first time)
```bash
pkg update && pkg install ffmpeg yt-dlp git python
# Build whisper.cpp if not present
cd ~ && git clone https://github.com/ggerganov/whisper.cpp && cd whisper.cpp && make
cp ~/.hermes/.env.example ~/.hermes/.env  # fill keys if needed
pip install -r requirements.txt  # minimal
```

## Quick Start
```bash
git clone https://github.com/familievlieland96-pixel/video-to-skill.git
cd video-to-skill
python video_to_skill.py "https://example.com/video.mp4" "Extract key techniques for inventory skill with sentiment"
```

Output in `output/`: book_*.md (with last30days section) + skill_*.md (ready to load with skill_view or skill_manage).

## Usage in Hermes
Load the generated skill or run via main_integration.py in robin-agent-plus with `--video-to-skill`.

See video-to-skill and last30days skills after run.

## License
MIT. Built for Tony (ykycportal) by Bossman/Hermes Agent. Part of The Block green business tools.

Run on Termux today — video + real sentiment → tweakable skills in one pipeline.
