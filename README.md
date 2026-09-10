# video-to-skill

Video to Skill pipeline - Turn any video (URL or local path) into structured text/book + auto-generated or tweaked Hermes skills.

**Fully runnable on Termux (Android)** — designed for Samsung Fold 5 / Termux environment with pkg installs, $HOME paths, whisper.cpp, no sudo, and Termux-specific setup. Works on Linux/macOS/Windows too.

Built as the pro addon layer for Robin Agent Plus / The Block. Leaves beginner client Robin untouched. Uses only our tools (terminal, vision_analyze, skill_manage, document-to-action-items, llm-wiki). No Microsoft.

## Features
- Downloads video with yt-dlp.
- Extracts scene-aware frames with ffmpeg.
- Transcribes with whisper.cpp (or fallback).
- Analyzes frames with vision.
- Builds "the book" (timestamped summary, insights, action items).
- Auto-authors a full Hermes SKILL.md (follows hermes-agent-skill-authoring standards: 60-char description, checkable steps, Pitfalls, Verification).
- Saves skill to ~/.hermes/skills or current dir for easy loading/tweaking.
- Integrates with robin-agent-plus, Odoo CRM logging, Bossman orchestration.

Perfect for turning product videos, reviews, tutorials, meetings, or competitor footage into living skills for inventory, fulfillment, ads, reviews, video production, and island business ops.

## Termux Setup (required first time)
```bash
pkg update && pkg install ffmpeg yt-dlp git python
# Build whisper.cpp if not present
cd ~ && git clone https://github.com/ggerganov/whisper.cpp && cd whisper.cpp && make
# Or use prebuilt if available
cp ~/.hermes/.env.example ~/.hermes/.env  # fill keys
pip install odoorpc  # if using CRM logging
```

## Quick Start
```bash
git clone https://github.com/familievlieland96-pixel/video-to-skill.git
cd video-to-skill
python video_to_skill.py "https://example.com/video.mp4" "Extract key techniques for inventory skill"
# or local file
python video_to_skill.py "~/storage/downloads/demo.mp4" "Turn review video into product skill"
```

Output: `book.md` (the structured knowledge) + `generated_skill.md` (ready to load with skill_view or skill_manage).

## Usage in Hermes
Load the generated skill or run via main_integration.py in robin-agent-plus with `--video-to-skill`.

See video-to-skill skill in ~/.hermes/skills/creative/ after first run.

## License
MIT. Built for Tony (ykycportal) by Bossman/Hermes Agent. Part of The Block green business tools.

Run on Termux today — no extra hardware needed beyond your Fold 5.
