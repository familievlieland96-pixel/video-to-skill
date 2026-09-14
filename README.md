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
5. Auto-authors a **draft** Hermes SKILL.md from the transcript (the transcript is the
   source of truth; the draft contains no invented steps, and clearly marks every
   "edit me" line that still needs a human). Saving both go to `output/`.
6. Runs the **hard gate** (`validate_skill.py`) on the generated skill. If the gate
   rejects it (hollow, placeholder, or too little transcript to distill from), the
   pipeline **fails loudly** and tells you exactly what to fix - it never hands you
   a stub dressed up as a finished skill.

If whisper.cpp is not set up, the pipeline **fails loudly** with the exact
command to run - it never silently fakes a transcript.

## The Gate (validate_skill.py)
`validate_skill.py <skill.md>` is the hard stop between "pipeline wrote a file" and
"you trust the skill":
- `exit 0` -> the file is clean (no placeholder strings, and the Transcript /
  Procedure / Verification sections are actually populated). Pipeline continues.
- `exit 1` -> the file is hollow. Pipeline fails and points you at the exact
  line to fix.

The gate is the last step of every pipeline run - it is called automatically in
`video_to_skill.py` (`gate_skill_file`), so you do not have to remember to run it.
You can also run it standalone on any skill file before you `skill_view` it.

A note on honesty: the pipeline intentionally emits a **draft**, not a finished
skill. A real skill needs you to read the transcript and fill the "edit me" steps
from specific passages - the pipeline will not fabricate those for you. The gate's
job is to make sure you can never ship a version where that step was skipped and
left invisible.

## Termux Setup on Android (one-time, ~15 minutes)

Done once per phone. Everything after that is just running the pipeline.

### 0. Prerequisites
- Termux installed (use the F-Droid build — the Play Store version is frozen and
  breaks on updates).
- Internet connection (model download is ~148 MB).

### 1. Install the toolchain
```bash
pkg update
pkg install -y build-essential cmake ffmpeg python git python-yt-dlp
```
- `build-essential` = clang + linkers (needed to compile whisper.cpp)
- `python-yt-dlp` = the `yt-dlp` command for downloading videos
- `ffmpeg` = video decoding + frame extraction

### 2. Build whisper.cpp
```bash
cd ~
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_SDL2=OFF \
      -DWHISPER_BUILD_TESTS=OFF -DWHISPER_COMMON_FFMPEG=ON
cmake --build build -j
```
If you already have `~/whisper.cpp` built, skip to step 3.
The flags matter:
- `WHISPER_SDL2=OFF` — without this the configure step fails on Termux
  (SDL2 is a GUI library Termux does not ship).
- `WHISPER_COMMON_FFMPEG=ON` — lets `whisper-cli` read .mp4/.mkv directly,
  no manual conversion to .wav.

### 3. Download the model
```bash
cd models
bash download-ggml-model.sh base.en      # ~148 MB, English, fastest good quality
```
(For non-English video use `small` or `large-v3` — same command, bigger download.)

### 4. Verify the setup works — do not skip
```bash
cd ~/whisper.cpp
./build/bin/whisper-cli -m models/ggml-base.en.bin samples/jfk.wav
```
If you see the JFK quote ("...and so my fellow Americans..."), the whole
toolchain is working. If not, stop and fix this step before running the
pipeline — the pipeline itself fails loudly and points back here if whisper
is not ready.

### Local videos on Android storage
```bash
termux-setup-storage     # once, grant access
```
Then pass the full path: `python3 video_to_skill.py /sdcard/Download/clip.mp4 "..."`

## Quick Start
```bash
cd video-to-skill
python3 video_to_skill.py "https://example.com/video.mp4" "Extract key techniques for an inventory skill"
```

Output in `output/`: `book_*.md` (transcript + frames + actions) and
`skill_*.md` (a **draft** that passed the gate - fill its "edit me" steps from the
transcript, then `skill_view` / `skill_manage` it).

## Usage in Hermes
Run the script, then load the generated skill with `skill_view` / `skill_manage`.
For real "what people say" grounding, add the separate `last30days` skill in a
Hermes session - this repo deliberately keeps video-to-text-to-skill clean and
offline, with no fabricated sentiment baked in.

## License
MIT. Built for Tony (ykycportal) by Bossman/Hermes Agent. Part of The Block tools.

Run on Termux today - video to text to skill, fully local and honest.
