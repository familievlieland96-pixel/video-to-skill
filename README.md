# video-to-skill

Video to Skill pipeline - Turn any video (URL or local path) into structured text
(book) + a generated Hermes skill. **The transcript is the base of the skill.**

**Fully runnable on Termux (Android)** — designed for Samsung Fold 5 / Termux
environment with pkg installs, $HOME paths, no sudo. Works on Linux/macOS too.

Built as the pro addon layer for Robin Agent Plus / The Block. Leaves beginner
client Robin untouched. Uses only our tools (terminal, ffmpeg, yt-dlp,
whisper.cpp, vision_analyze). No Microsoft.

## How it works
1. Downloads the video with yt-dlp (if a URL).
2. Transcribes it with **whisper.cpp** (local, offline - the real model, no stubs).
3. Samples scene-aware key frames with ffmpeg (for later vision_analyze detail).
4. Builds the **book** - source + full transcript + frame notes + action items.
5. Auto-authors a Hermes SKILL.md from the transcript (follows our skill-authoring
   standards), saving both to `output/`.

If whisper.cpp is not set up, the pipeline **fails loudly** with the exact
command to run - it never silently fakes a transcript.

## Termux Setup (one-time)
```bash
pkg install -y ffmpeg yt-dlp git python cmake
# Build whisper.cpp if not present
cd ~ && git clone https://github.com/ggerganov/whisper.cpp && cd whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_SDL2=OFF \
      -DWHISPER_BUILD_TESTS=OFF -DWHISPER_COMMON_FFMPEG=ON
cmake --build build -j
cd models && bash download-ggml-model.sh base.en
```

## Quick Start
```bash
cd video-to-skill
python3 video_to_skill.py "https://example.com/video.mp4" "Extract key techniques for an inventory skill"
```

Output in `output/`: `book_*.md` (transcript + frames + actions) and
`skill_*.md` (ready to load with skill_view or skill_manage).

## Usage in Hermes
Run the script, then load the generated skill with `skill_view` / `skill_manage`.
For real "what people say" grounding, add the separate `last30days` skill in a
Hermes session - this repo deliberately keeps video-to-text-to-skill clean and
offline, with no fabricated sentiment baked in.

## License
MIT. Built for Tony (ykycportal) by Bossman/Hermes Agent. Part of The Block tools.

Run on Termux today - video to text to skill, fully local and honest.
