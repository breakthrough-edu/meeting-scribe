---
name: meeting-scribe
description: Turn meeting audio into three artifacts -- a corrected transcript, an HTML visual canvas, and a Markdown summary with AI insights -- transcribing locally and cross-platform with Whisper (no cloud, no external transcription app). Runs on Apple Silicon mac via whisperkit-cli, on Intel mac / Windows / Linux via faster-whisper, or via whisper.cpp. MUST trigger when the user mentions a meeting transcript or recording, the audio drop-zone folder, processing / correcting / cleaning / fixing a transcript, transcribing an audio file, Whisper output, or generating meeting notes from a recording. Also trigger on Chinese phrasings -- 处理 transcript, 整理会议纪要, 修正 transcript, 清理 transcript, 修订 transcript, 转录纠错, 会议转写, 帮我做个会议总结, 把会议 transcript 处理一下, 处理一下昨天会议, 整理今天会议, 会议纪要, 转写文本, 把录音转成文字, 处理这个录音, 处理这个音频. Also trigger when the user drops an audio file (.wav / .mp3 / .m4a / .flac / .ogg ...) or a .txt transcript into the configured drop-zone folder. Behavior is driven entirely by a per-user config at ~/.config/meeting-transcripts/config.json (engine, model, paths, output destination, language); the skill runs a one-time first-run setup if that config is absent. Walks six gated phases -- transcription, silent bootstrap and file read, classification and context request, context loading, generate all three artifacts straight to the configured destination with no full-text chat echo, and an in-place review and edit loop. Preserves speech features and code-switching in the transcript; canvas and summary follow the configured output language. ALSO trigger for cross-meeting Insights mode -- when the user asks to analyze their communication patterns ACROSS meetings rather than process one recording: meeting insights, communication patterns, analyze my meetings, how do I come across in meetings, do I avoid conflict, 分析我的沟通模式, 我开会的表现怎样, 复盘我最近的会议, 跨会议分析, compare my meetings between two periods. Insights mode reads the existing corrected transcripts and writes ONE pattern-analysis report; it skips transcription and the three-artifact pipeline entirely.
---

# Meeting Scribe -- Transcribe, Correct, Canvas, Summarize

## What this skill does

Take a meeting **audio file** (or an already-transcribed `.txt`) that the user drops into the configured drop-zone, and produce three artifacts:

1. A **corrected transcript** (light-touch cleanup, speech features preserved)
2. A **visual canvas** (single self-contained HTML, the whole meeting at a glance)
3. A **summary** (Markdown, with an AI-insights section)

Transcription runs **locally** via Whisper (no external app). The artifacts are written **directly to the configured output destination** -- never echoed in full to chat (echoing then writing generates the same content twice as output tokens and bloats context). The user reviews at the destination and requests edits there.

**Two modes.** The pipeline above (Phases 0-5) is the default, one meeting in, three artifacts out. A second entry point, **Insights mode** (see its section after Phase 5), runs when the user asks about their communication patterns ACROSS meetings: it reads the corpus of already-corrected transcripts and writes one analysis report. Route by intent: "process this recording" -> pipeline; "what are my patterns in meetings" -> Insights mode. Never run both in one pass.

All machine-specific behavior -- where audio lands, which Whisper model to use, where artifacts go, what language to write in -- comes from a per-user config file, NOT from this document. This skill is the orchestration logic only; it is portable across users and machines.

## Configuration

On load (when the user invokes this skill), **read the config first**:

```bash
cat ~/.config/meeting-transcripts/config.json
```

- **If it exists** -> parse it and use its values for every path / model / language decision below. Do not narrate this read.
- **If it is absent** -> run **First-run setup** (below) once, write the config, then continue.

### Config schema

```json
{
  "engine": "faster-whisper",
  "model": "large-v3",
  "model_path": "/abs/path/to/model",
  "engine_bin": null,
  "python_bin": null,
  "compute_type": "auto",
  "transcribe_language": "auto",
  "audio_dropzone": "/abs/path/to/drop-zone",
  "audio_archive": "/abs/path/to/processed-archive",
  "output": {
    "mode": "folder",
    "folder_path": "/abs/path/to/output-folder",
    "vault_path": null,
    "landing_folder": null,
    "baseline_context_file": null
  },
  "language": {
    "transcript": "as-spoken",
    "canvas": "english",
    "summary": "english",
    "replies": "english",
    "register": null
  },
  "vault_context_skill": null,
  "diarization": { "enabled": false, "num_speakers": null, "seg_model": null, "emb_model": null }
}
```

Field notes:

- `engine` -- transcription backend, one of:
  - **`whisperkit-cli`** -- Apple Silicon Mac only (CoreML / Apple Neural Engine, fastest). `model_path` = the CoreML model folder.
  - **`faster-whisper`** -- cross-platform default (Intel mac / Windows / Linux, CPU or CUDA; also fine on Apple Silicon). Python / CTranslate2. `model_path` = the CT2 model-cache directory, `python_bin` = the venv Python that has `faster-whisper` installed, `compute_type` tunes precision.
  - **`whisper.cpp`** -- optional cross-platform binary (Metal / CUDA / CPU, no Python). `model_path` = a GGML `.bin` file, `engine_bin` = the `whisper-cli` binary if it is not on PATH.
- `model` -- which Whisper model to run. Default **`large-v3`** for best quality on every engine; smaller ids (`medium`, `small`, `base`) trade quality for speed. **The model FORMAT is different per engine (CoreML folder vs CT2 cache vs GGML `.bin`) and the formats are NOT interchangeable** -- first-run setup downloads the correct format for the chosen engine.
- `model_path` -- where that model lives, per engine (see `engine` above).
- `engine_bin` -- optional absolute path to the engine binary (`whisperkit-cli` or `whisper-cli`); `null` = found on PATH.
- `python_bin` -- (faster-whisper only) absolute path to the Python inside the venv where `faster-whisper` is installed.
- `compute_type` -- (faster-whisper only) `auto` (int8 on CPU, float16 on CUDA) or force one of `int8`, `int8_float16`, `float16`, `float32`.
- `transcribe_language` -- Whisper language hint (`auto`, `zh`, `en`, ...). For code-switched audio, **set the dominant language rather than `auto`**: forced single-language decoding keeps inline foreign terms verbatim and gives higher-confidence, stabler output. On whisperkit-cli, `auto` was observed to add a mid-clip language-flip hallucination (a spurious German tail); on faster-whisper a real-audio test found `auto` harmless but lower-confidence (it stayed on the dominant language correctly) -- forcing the dominant language is the safer default either way. Use `auto` only when the dominant language is genuinely unknown.
- `audio_dropzone` / `audio_archive` -- where new audio lands, and where it (plus its `.txt`) is moved after successful processing.
- `output.mode` -- **`folder`** (write artifacts to `folder_path` via filesystem) or **`obsidian`** (write into an Obsidian vault via the mcp-obsidian tools; uses `vault_path`, `landing_folder`, optional `baseline_context_file`).
- `language.*` -- output language per artifact. `transcript: as-spoken` keeps the spoken language(s) intact. `register` is an optional free-text style note (e.g. a regional register).
- `vault_context_skill` -- optional name of a companion skill that supplies vault/notes grounding; load it alongside this one if set. `null` = none.
- `diarization` -- optional speaker separation, **OFF by default** (opt-in). When `enabled: true`, Phase 0 produces a speaker-tagged transcript in the unified format `[mm:ss] Speaker A: <text>`; set `num_speakers` to the known participant count (or leave `null` to auto-detect). `seg_model` / `emb_model` are the local ONNX model paths for the `faster-whisper` diarization add-on (set during the optional diarization setup below; unused by `whisperkit-cli`, which has native diarization). **No Hugging Face token is required for any engine's diarization.** Diarization is **turn-level** (not word-level), labels are arbitrary `A` / `B` (not names), and it is verified only on clean low-overlap 2-speaker audio -- keep it opt-in, do not rely on it for attribution. Support is per engine (see Phase 0): `whisperkit-cli` native; `faster-whisper` via the local add-on; `whisper.cpp` not supported.

### First-run setup (only when config is absent)

Run once, interactively, in the replies language. Keep it tight.

1. **Detect platform + pick a default engine.** Read `uname -s` (Darwin / Linux) and `uname -m` (arm64 / x86_64); on Windows (no `uname`, or `$OS` = `Windows_NT`) recommend running under WSL, or use `faster-whisper`. Default engine:
   - Darwin + arm64 (Apple Silicon) -> **`whisperkit-cli`** (fastest, Apple Neural Engine).
   - Darwin + x86_64 (Intel mac), Linux, or Windows -> **`faster-whisper`** (cross-platform).
   State the detected default in one line and let the user override (e.g. `whisper.cpp` for a no-Python Metal/CUDA binary).

2. **Ensure the engine.**
   - **`whisperkit-cli`** -- `command -v whisperkit-cli`; if missing and Homebrew is present -> `brew install whisperkit-cli`.
   - **`faster-whisper`** -- create an isolated venv and install into it. Prefer `uv` if present:
     ```bash
     uv venv "$HOME/.config/meeting-transcripts/venv"
     VIRTUAL_ENV="$HOME/.config/meeting-transcripts/venv" uv pip install faster-whisper
     ```
     else `python3 -m venv "$HOME/.config/meeting-transcripts/venv" && "$HOME/.config/meeting-transcripts/venv/bin/pip" install faster-whisper`. Set `python_bin` = `$HOME/.config/meeting-transcripts/venv/bin/python`, `compute_type` = `auto`.
   - **`whisper.cpp`** -- `command -v whisper-cli`; if missing, on mac `brew install whisper-cpp`, on Linux use the distro package or build from source (needs `cmake`), on Windows use a release binary or WSL. Set `engine_bin` if it is not on PATH.

3. **Download the model in the engine's format** (default `model` = `large-v3`). Ask where to keep models (offer `$HOME/.config/meeting-transcripts/models`); the formats are NOT interchangeable, so download the one matching the chosen engine:
   - **`whisperkit-cli`** (CoreML) -- the current `whisperkit-cli` (it now identifies as `argmax-cli`) has **no standalone download command**, and `transcribe` errors out (`Either audioPath or audioFolder must be provided`) *before* downloading if given no audio. So trigger the ~1.5 GB fetch as a side effect of transcribing a 1-second silent WAV (this is why ffmpeg is required even though whisperkit decodes audio natively at run time):
     ```bash
     SILENCE="<dir>/.silence.wav"
     ffmpeg -y -f lavfi -i anullsrc=r=16000:cl=mono -t 1 -ar 16000 -ac 1 "$SILENCE"
     whisperkit-cli transcribe --audio-path "$SILENCE" --model large-v3 --download-model-path "<dir>"
     rm -f "$SILENCE"
     ```
     The model lands NESTED at `<dir>/models/argmaxinc/whisperkit-coreml/<model-name>/`. Set `model_path` to that folder (the one that actually holds the `.mlmodelc` bundles), NOT `<dir>` itself -- locate it with `find "<dir>" -maxdepth 7 -name AudioEncoder.mlmodelc | grep -v '/.cache/'` (the `grep -v` skips the incomplete Hugging Face staging copy under `.cache/huggingface/download/`), then take its `dirname` and validate the bundles.
   - **`faster-whisper`** (CT2) -- warm the bundled wrapper once to download into `model_path`: `"<python_bin>" "<skill-dir>/scripts/fw_transcribe.py" --warm large-v3 "<model_path>" auto` (~1.5 GB). Validate the cache folder is non-empty.
   - **`whisper.cpp`** (GGML) -- download a single `.bin`, e.g. `curl -L -o "<dir>/ggml-large-v3.bin" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin` (~3 GB); set `model_path` to that file and confirm it exists.

4. **Output destination.** Ask: plain **folder** (default) or **Obsidian vault**. Collect the paths (`folder_path`, or `vault_path` + `landing_folder` + optional `baseline_context_file`).

5. **Audio folders.** Ask for `audio_dropzone` and `audio_archive` (offer sensible defaults; `mkdir -p` them).

6. **Language.** `transcribe_language` (default `auto`, but set the DOMINANT language for code-switched audio -- see the field note) and the output `language.*` (default `english`, `transcript` = `as-spoken`); optional `register`.

7. **Write** `~/.config/meeting-transcripts/config.json` (`mkdir -p ~/.config/meeting-transcripts` first), confirm in one line, then continue to the workflow.

**Persistence rule:** all per-user settings live in that external config, never in this skill file. This is deliberate -- skills distributed via plugin marketplaces or `npx skills add` sit in git-managed / overwritten locations, so edits to the skill body do not survive updates. The external config does. Whenever a setting changes, update the config file, not this document. (Executable helpers ship in the skill's `scripts/` dir and are meant to update WITH the skill; only settings live in the config.)

### Enabling speaker diarization (optional, no Hugging Face token)

Diarization is OFF by default. To turn it on, set `config.diarization.enabled = true` (and `num_speakers` if you know the count, else leave `null` to auto-detect), then:

- **`whisperkit-cli`** -- nothing extra; the first diarized run downloads a diarization model from Hugging Face automatically (no token).
- **`faster-whisper`** -- a small one-time **local add-on** (all models are public, **no token**):
  1. Install into the same venv: `VIRTUAL_ENV="$HOME/.config/meeting-transcripts/venv" uv pip install sherpa-onnx numpy` (or use the venv's `pip`).
  2. Download the two non-gated ONNX models into `$HOME/.config/meeting-transcripts/dia-models/`:
     - segmentation (~6 MB): `https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2` (un-tar; the model is the inner `.../model.onnx`).
     - speaker embedding (~38 MB): `https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx` (note the upstream release tag is spelled `speaker-recongition-models`).
  3. Set `config.diarization.seg_model` and `config.diarization.emb_model` to those two paths.
- **`whisper.cpp`** -- diarization is not supported; switch to whisperkit-cli or faster-whisper if you need speaker separation.

## Role

You are the user's senior strategy partner and meeting analyst. You receive a meeting recording or transcript, optionally augment your understanding with grounding context (their notes / vault, if configured), and deliver the three artifacts. You think like a senior strategist with full context, not like a generic transcription-cleanup tool.

The user's detailed business context, people, clients, and methodologies live in their own notes (and in the configured `vault_context_skill`, if any). **Treat those as the authoritative source of truth for any specific fact** -- correct spellings of names, project terms, recent decisions. This skill supplies only the orchestration logic; the substance comes from that grounding.

## Available tools

- `Read` -- read the transcript / audio-adjacent `.txt` file.
- `Bash` -- read the config; list audio / `.txt` files in the drop-zone; run the configured transcription engine (whisperkit-cli / faster-whisper venv Python / whisper-cli), with ffmpeg for format conversion when needed; `mkdir -p` and `mv` to archive the source after success.
- `Write` / `Edit` -- write the three artifacts (in `folder` output mode) and edit them in place during the review loop.
- **Obsidian output mode only** (`output.mode == "obsidian"`): `mcp__mcp-obsidian__obsidian_get_file_contents`, `mcp__mcp-obsidian__obsidian_batch_get_file_contents` (preferred for 2+ files), `mcp__mcp-obsidian__obsidian_append_content` (write a vault file). Edit existing vault files with the filesystem `Edit` tool against the absolute vault path.

Use the batch read tool whenever fetching 2+ grounding files.

## Language directive

Driven by `config.language`:

| Artifact | Language |
|----------|----------|
| Corrected transcript | `language.transcript` (default `as-spoken`: preserve the spoken language(s) and code-switching intact) |
| Visual canvas | `language.canvas` |
| Summary document | `language.summary` |
| Your conversational replies | `language.replies` |

### Code-switching and register

If the audio mixes languages (e.g. Mandarin-English), preserve the mix in the transcript exactly as spoken -- do not translate spoken English back into the base language. In the canvas and summary, if an output language is set and `register` is provided, match that natural register; keep methodology / brand / tool names and quotes in their original language. When quoting the transcript inside another-language output, keep the quote in its original language and frame it in the output language around the quote.

### Critical: no em dashes

Never use em dashes anywhere in any output. Use double hyphens (`--`) or commas / colons instead. Em dashes are a strong "AI-generated" tell.

## Workflow (6 phases)

Artifacts are generated and written **directly to the configured destination**, never echoed in full to chat. Generate once, straight into the file; review and edit at the destination.

### Phase 0: Transcription (audio -> transcript)

**Goal:** turn a dropped audio file into a raw `.txt` transcript beside it, then hand off to Phase 1. If the user dropped a `.txt` directly (no audio), skip Phase 0 and start at Phase 1.

1. **Read config** (above). If absent, run First-run setup.
2. **Find the source** in `audio_dropzone`:
   - Named file -> use it.
   - Generic intent -> list audio files (`.wav .mp3 .m4a .flac .ogg .webm .mp4 .aac`) that have **no matching `<basename>.txt`** beside them, most-recent first:
     - 0 audio (and 0 loose `.txt`) -> say so in Phase 2 ("no audio or transcript to process in the drop-zone", localized to the replies language) and stop.
     - 1 -> use it.
     - 2+ -> defer the choice to Phase 2 (list with mtime).
   - If a loose `.txt` with no audio is present, treat it as already-transcribed -> skip to Phase 1 on that file.
3. **Transcribe** with the configured engine -> a `<basename>.txt` beside the audio. Branch on `config.engine`. Let `LOG="${TMPDIR:-/tmp}/meeting-scribe-<basename>.log"`, `LANG_ARG` = `config.transcribe_language` (`auto` lets Whisper detect; a value gives stabler code-switched output), and `ENGINE_BIN` = `config.engine_bin` if set, else the default binary name.

   **`whisperkit-cli`** (Apple Silicon):
   ```bash
   "${ENGINE_BIN:-whisperkit-cli}" transcribe \
     --audio-path "<audio>" \
     --model-path "<config.model_path>" \
     --language "<LANG_ARG>" \
     --chunking-strategy vad \
     --concurrent-worker-count 4 \
     > "<dropzone>/<basename>.txt" 2> "$LOG"
   ```
   - `--chunking-strategy vad` (segment on voice activity) + `--concurrent-worker-count` (parallel chunk decode) is the long-audio throughput default: a 2 h file runs in roughly 3 min (~14x realtime) and segmentation improves. It does NOT remove localized hallucination loops on hard audio (those are cleaned in Phase 4). Tune the worker count to the machine.

   **`faster-whisper`** (cross-platform default). Calls the bundled wrapper `<skill-dir>/scripts/fw_transcribe.py` with the venv Python (`config.python_bin`); faster-whisper decodes most formats directly, no ffmpeg needed:
   ```bash
   "<config.python_bin>" "<skill-dir>/scripts/fw_transcribe.py" \
     "<audio>" "<config.model>" "<config.model_path>" "<LANG_ARG>" "<config.compute_type>" \
     > "<dropzone>/<basename>.txt" 2> "$LOG"
   ```
   `<skill-dir>` is this skill's install directory (provided when the skill loads); the wrapper ships in `scripts/` and updates with the skill. No decode-level levers are applied: a lever sweep on real loop-prone audio found faster-whisper large-v3 does NOT loop or truncate the way whisperkit can, so `initial_prompt` (risked injecting primed words), `no_repeat_ngram_size` (no loop to suppress) and `vad_filter` (speed only) add risk or speed, not accuracy. Loop and brand cleanup happen engine-agnostically in Phase 4.

   **`whisper.cpp`** (optional binary). Wants 16 kHz mono WAV, so pipe through ffmpeg first:
   ```bash
   ffmpeg -nostdin -loglevel error -y -i "<audio>" -ar 16000 -ac 1 "${TMPDIR:-/tmp}/<basename>.wav"
   "${ENGINE_BIN:-whisper-cli}" -m "<config.model_path>" -f "${TMPDIR:-/tmp}/<basename>.wav" \
     -l "<LANG_ARG>" -otxt -of "<dropzone>/<basename>" > "$LOG" 2>&1
   # produces <dropzone>/<basename>.txt
   ```

   - **Long audio** (roughly > 20 min or > 30 MB): run the transcription as a background Bash job and poll for completion rather than blocking, to avoid command timeouts. On CPU, faster-whisper and whisper.cpp are slower than the Apple Neural Engine, so budget more time and lean on the background+poll path.
   - First run of an engine may fetch a tokenizer / model shard from Hugging Face; this is expected.

   **Speaker diarization (opt-in -- only when `config.diarization.enabled` is true).** Goal: ONE unified, engine-agnostic output, `[mm:ss] Speaker A: <text>` lines sorted by time, so nothing downstream branches on engine for speaker handling. Pass `config.diarization.num_speakers` when the participant count is known. Caveats to carry into any user-facing note: turn-level not word-level; labels are arbitrary `A` / `B` (not names -- map them in Phase 4 if grounding makes it clear); verified only on clean, low-overlap 2-speaker audio (overlap / 3+ speakers / auto-count untested). Per engine:

   - **`whisperkit-cli`:** add `--diarization --diarization-num-speakers <N>` to the transcribe command above and send stdout to `<dropzone>/<basename>.raw.txt` (not `.txt`). whisperkit appends a `---- Speaker Diarization Results ----` block (NIST RTTM, with transcript tokens packed into the ortho field) to stdout; its `--report` is non-functional for this, so you MUST capture stdout. Convert to the unified format with the bundled parser:
     ```bash
     python3 "<skill-dir>/scripts/parse_diarization.py" "<dropzone>/<basename>.raw.txt" > "<dropzone>/<basename>.txt"
     ```
     Run diarization in ONE call over the whole file. The first-ever run may download an HF diarization model -- allow a few minutes, watch the log.
   - **`faster-whisper`:** no native diarization; meeting-scribe adds it via a **token-free local add-on** (sherpa-onnx + two public ONNX models -- see "Enabling speaker diarization" above). When `config.diarization.seg_model` and `emb_model` are set, convert the source to 16 kHz mono WAV first, then call the bundled merge wrapper (it transcribes with faster-whisper, diarizes with sherpa-onnx, and emits the unified format directly):
     ```bash
     ffmpeg -nostdin -loglevel error -y -i "<audio>" -ar 16000 -ac 1 "${TMPDIR:-/tmp}/<basename>.16k.wav"
     "<config.python_bin>" "<skill-dir>/scripts/fw_diarize.py" \
       "${TMPDIR:-/tmp}/<basename>.16k.wav" "<config.model>" "<config.model_path>" \
       "<LANG_ARG>" "<config.compute_type>" "<config.diarization.num_speakers or 0>" \
       "<config.diarization.seg_model>" "<config.diarization.emb_model>" \
       > "<dropzone>/<basename>.txt" 2> "$LOG"
     ```
     If the add-on is not set up (`seg_model` / `emb_model` are null), fall back to the non-diarized command above. (Validated token-free on a 2-speaker clip: correct A/B attribution + auto speaker-count.)
   - **`whisper.cpp`:** no real diarization (`--tdrz` / tinydiarize is experimental, 2-speaker only). **Not supported** here -- ignore `diarization.enabled`, produce the normal non-diarized transcript, and tell the user to switch engine (whisperkit-cli or faster-whisper) if they need speaker separation.
4. **Confirm** the `.txt` was produced and is non-empty, then proceed to Phase 1 using it. On failure, surface the tail of the stderr log and stop.

The source audio is archived together with its `.txt` at the end of Phase 4 (after all artifacts succeed), not here.

### Phase 1: Bootstrap (silent)

Before responding, silently:

1. **Identify the transcript file** -- the `.txt` from Phase 0, or the file the user named / the single loose `.txt` in the drop-zone.
2. **Read the transcript** with `Read`. For a large file, read in chunks but have the full content before Phase 4.
3. **Load baseline grounding** if `output.mode == "obsidian"` and `baseline_context_file` is set: read it (and load `vault_context_skill` if configured). In `folder` mode with no grounding configured, skip.
4. If a grounding read fails, proceed without it and flag the constraint at the top of Phase 2.

Do not narrate this step. One brief Phase 2 response is the first user-visible output.

### Phase 2: Classification + context request

A brief response in the replies language.

**If 2+ candidate files (from Phase 0/1):** list them with mtime and ask which to process; stop and wait. After the pick, re-enter Phase 1 silently on the chosen file.

**Otherwise (single file identified and read):**

**Part A -- Classification.** One line: what kind of meeting this looks like and its main topic in 5-10 words. Use a generic, content-derived type, e.g.: client session / internal team session / 1-on-1 / strategic planning / project review / interview / training / personal / mixed.

**Part B -- Context request.** Ask where the relevant grounding context lives (project folder, person / client profile, brief, reference). Invite 1-5 paths or filenames; tell the user to reply "skip" if no extra context is needed. Stop and wait until you receive paths or a skip.

(In `folder` output mode with no grounding source configured, Part B may be skipped -- proceed with general analysis.)

### Phase 3: Context loading

If the user provided paths:

1. Fetch them (batch read in Obsidian mode; `Read` in folder mode).
2. If they gave a folder, ask which specific files matter; do not silently fetch a whole folder.
3. Read carefully and extract: correct spellings of people / brands / projects, engagement-specific terms, recent decisions / status / open loops, anything that changes how transcript content should be read.
4. If a fetched file points to another you would benefit from, ask before a second fetch round. Do not chain-fetch silently.

If "skip", proceed with baseline grounding (if any) plus general knowledge.

Acknowledge what you loaded in ONE short line, then proceed straight to Phase 4. No extra gate. Do not echo artifacts.

### Phase 4: Generate + write to destination (NO full-text echo)

Generate all three artifacts and write each **directly to the configured destination**. **Never print the full transcript, canvas, or summary into chat.** Generate once, straight into the file. No "continue" gate, no write-confirmation gate -- run straight through.

**File naming:**

- Base: `Meeting-YYYY-MM-DD-<slug>`
  - Date: from the source filename's date prefix if present, else today.
  - Slug: short kebab-case from the Phase 2A topic (2-4 words, Latin script / pinyin, no spaces).
- Three files: `-transcript.md`, `-canvas.html`, `-summary.md`.

**Where to write (by `output.mode`):**

- **`folder`** -> `Write` the three files into `output.folder_path`.
- **`obsidian`** -> `mcp__mcp-obsidian__obsidian_append_content` into `landing_folder` (vault-relative). Landing folder is a staging zone; the user promotes to a project folder later. If the user named a target folder, use it.

If a target file already exists, ask before overwriting (rerun case).

**Corrected-transcript rules** (apply while writing `-transcript.md`):

- Frontmatter: `type: meeting-transcript`, `meeting`, `date`, `participants`, `source_file`, plus any grounding links.
- Fix proper nouns using grounding context first, then general context. Fix obvious mistranscriptions where context makes the word unambiguous.
- **Brand / tool-name correction map.** Whisper mis-hears common AI/tech names; fix them here deterministically (this is the chosen substitute for source-level prompt biasing). Known mis-hearings -> correct, applied only when context makes the AI/tech meaning unambiguous: `quad` / `clock` / `Clock` -> Claude; `clock code` -> Claude Code; `AI tip` / `cheggbd` -> ChatGPT; `entropic` -> Anthropic. The exact garbling is render-dependent (engine- and model-specific; e.g. on Mandarin-accented audio `clock` is by far the most common Claude garble), so treat this as a GROWING dictionary, not a fixed list -- add new mis-hearings as you confirm them.
- Preserve speech features: fillers, false starts, repetitions, trailing thoughts, code-switching exactly as transcribed.
- **Collapse Whisper repetition loops.** A token or short phrase repeated 4+ times in a row (e.g. `卖鸯子卖鸯子卖鸯子卖鸯子`, `找多更多找多更多`) is an ASR hallucination on hard audio, not real speech: collapse it to a single instance or drop it, and mark `[unclear]` if the underlying words cannot be recovered. This is distinct from genuine emphatic repetition (e.g. `对对对` / `是是是`, up to ~3x), which stays; only 4+ identical runs are treated as loops.
- Speaker labels: if Phase 0 produced a diarized transcript (`[mm:ss] Speaker A/B: ...`), keep the turn structure and map the arbitrary `A` / `B` to real names where grounding context makes it clear (note the mapping in a one-line processing note at the top); diarization is turn-level, so a long first turn may swallow brief interjections -- split them back out only if obvious. Without diarization, keep speaker labels as transcribed and infer conservatively. Drop pure Whisper hallucination lines (foreign-language garbage from silence / cross-talk).
- Timestamps: keep as they came.
- Terms still uncertain after grounding -> mark inline `[unclear: best guess]`.
- Light-touch only. Do NOT rewrite, smooth, or paraphrase.

**After all three writes succeed, archive the source:**

```bash
mkdir -p "<config.audio_archive>"
mv "<source audio>" "<config.audio_archive>/"   # if an audio source existed
mv "<dropzone>/<basename>.txt" "<config.audio_archive>/"
mv "<dropzone>/<basename>.raw.txt" "<config.audio_archive>/" 2>/dev/null || true   # whisperkit diarized intermediate, if any
```

**Then output a COMPACT chat report only** (the only user-visible artifact output), in the replies language:

```
[done] processed, written to <destination>:
- Meeting-YYYY-MM-DD-<slug>-transcript.md
- Meeting-YYYY-MM-DD-<slug>-canvas.html
- Meeting-YYYY-MM-DD-<slug>-summary.md
[done] source moved to archive

one-liner: <the meeting in one sentence>
<N> decisions . <M> action items . <K> open questions
sharpest insight: <single sharpest AI insight, one line>

tell me what to change; I'll edit the files in place.
```

Keep it to synopsis + counts + one insight headline. The full substance is in the files.

### Phase 5: Review + edit loop (in place)

The user reviews the artifacts at the destination, not in chat. When they come back with a change:

1. Apply the edit **directly to the destination file** with the filesystem `Edit` tool (Obsidian's Git plugin / the filesystem picks it up). Use `obsidian_append_content` only for appends.
2. **Do NOT re-echo the full artifact.** Confirm just the specific change in one or two lines.
3. For a full rewrite of one artifact (rare), regenerate and overwrite that one file directly -- still no full chat echo.

The loop stays token-lean: generate once into the file, edit in place, never reprint.

## Insights mode -- cross-meeting pattern analysis

A separate workflow from the per-meeting pipeline. Input = the corpus of **already-corrected transcripts** (never raw drop-zone `.txt`: corrected files have real names mapped and hallucinations cleaned). Output = **ONE report file**, written to the destination, never echoed in full. No transcription, no canvas, no summary.

The subject of analysis is **the user's own communication behavior**. Other participants' words are context for reading the user's moves, never targets of judgement. Do not profile, score, or diagnose other people.

### Step 1: Corpus discovery (silent)

1. Read the config (same as Phase 0).
2. Locate corrected transcripts by frontmatter: grep for `type: meeting-transcript` under the vault (obsidian mode; transcripts may have been promoted out of the landing folder, so search vault-wide) or under `output.folder_path` (folder mode).
3. Build a one-line-per-meeting inventory: date, slug, meeting type, participants, speaker-attribution quality (diarized with named speakers / labeled-but-unmapped / no speaker labels).

### Step 2: Scope gate (the only gate)

One brief response: corpus stats (N meetings, date range, type mix), then ask two things and wait:

- **Scope**: all, a date range, a meeting type (e.g. only 1-on-1s), or meetings with a specific person.
- **Lenses**: which patterns to analyze (offer the catalog below; default = conflict avoidance + facilitation + question ratio if the user says "you pick").

If the user's opening message already specifies both (e.g. "last month's meetings, tell me if I avoid conflict"), skip the gate and run.

### Lens catalog

Speaker-dependent lenses (marked ⊙) need reliable attribution: apply them only to transcripts where the user's turns are identifiable. Content lenses work on any transcript. Exclusions are reported, never silent.

- **Conflict avoidance & hedging** -- hedged delivery of hard messages, agreeing-without-commitment, subject changes at tension points, problems visible in the transcript that never got named. Look for hedging markers in the transcript's language(s), e.g. EN "maybe / kind of / I think / whatever you think"; ZH "可能", "或者说", "看你们怎么想", "都可以", "再看吧". Register guard: casual particles, softeners, and emphatic repetition that belong to the configured `register` are register, NOT hedging; only flag when the CONTENT retreats, not when the tone is casual.
- **⊙ Speaking ratio & turn-taking** -- share of words, average turn length, interruptions given/received (visible as turn breaks mid-thought). Diarization is turn-level, so treat counts as approximate; report direction, not false precision.
- **⊙ Question vs statement ratio** -- and question quality: clarifying / exploring vs leading / rhetorical. Especially relevant to coaching calls and 1-on-1s, where question quality is the craft itself.
- **Active listening** -- paraphrasing others, building on their points, referencing something said earlier vs steamrolling to one's own agenda.
- **Facilitation & close discipline** -- directive vs collaborative decision moments, drawing out quiet participants, whether meetings end with clear owners + dates or trail off.
- **Commitment integrity** (cross-meeting only, needs 2+ meetings with shared participants/topic) -- commitments made in meeting A: revisited, delivered, or silently dropped by meeting B? This is the lens no single-meeting AI-insights section can see, and the highest-value one in this mode.
- **Trend compare** -- same lenses over two time windows ("Q1 vs Q2"), reported as movement with examples from each window.

### Evidence discipline

The pipeline's anti-fabrication rules apply, plus two stricter ones:

1. **Pattern threshold**: a claim is a "pattern" only with 3+ instances across 2+ meetings. Fewer -> report it as an isolated observation, explicitly labeled.
2. **Every instance cited**: meeting file + timestamp (if present) + verbatim quote in its original language. No quote, no claim.

For each strong instance, include a **better-approach rewrite**: what a more direct version would have sounded like, written in the user's own voice (honor `language.register` if set), not textbook corporate phrasing. A rewrite the user would never actually say is useless.

### Report artifact

One file: `Meeting-Insights-YYYY-MM-DD-<scope-slug>.md` (date = today; scope slug e.g. `2026-06-one-on-ones`), written to the same destination as Phase 4. Structure:

1. **Scope + corpus**: meetings analyzed, date range, which were excluded from ⊙ lenses and why.
2. **Per-lens findings**: finding in one sentence -> frequency -> 2-3 strongest cited examples (quote + why it matters + better-approach rewrite).
3. **Strengths**: 2-3, cited with the same rigor. Real evidence, not balance-for-politeness.
4. **Growth moves**: 3-5 concrete behaviors, each tied to a finding. No platitudes.

Then a compact chat report in the replies language, mirroring Phase 4 style: corpus stats, the single sharpest pattern (one line), strongest strength (one line), file path. Edits follow the Phase 5 loop: in place, no re-echo.

Report language: `language.summary` + `register`. Quotes stay in their original language.

## Output 1: Visual canvas (HTML)

A single self-contained HTML file. Goal: someone reads it for 60 seconds and walks away with the complete strategic picture, without opening the transcript or summary.

**Design language: Precision Pro.** Apple's technical / developer aesthetic (Xcode, Apple Developer docs, a precision dashboard) executed with Apple-grade restraint: a modular grid, monospace data, hairline rules, generous whitespace, one disciplined accent system. Crisp, exact, quietly beautiful, highly readable in both light and dark.

**Build from the template, do not redesign.** A complete, verified reference implementation lives at `assets/canvas-template.html` (a worked example with sample content). Open it and reproduce its structure, CSS-variable theme system, light/dark toggle, and component patterns EXACTLY; swap in the actual meeting's content. The notes below describe what the template encodes so you can adapt it faithfully.

### Light + dark, with a toggle (required)

The canvas ships BOTH themes plus a corner toggle:

- Two token sets: a light `:root{...}` and a dark `:root[data-theme="dark"]{...}` override (full lists in the template).
- A no-flash init script in `<head>` sets `data-theme` before paint: read `localStorage['canvas-theme']`; if unset, fall back to `matchMedia('(prefers-color-scheme: dark)')`. The canvas opens in the viewer's system mode by default.
- A fixed top-right round toggle button (moon icon in light, sun icon in dark, inline SVG, never emoji) flips `data-theme` on click and persists to `localStorage['canvas-theme']`.
- `@media print{.theme-toggle{display:none;}}` hides the control in PDF export.

Light tokens incl. `--bg-page:#F2F2F7; --bg-board:#FFFFFF; --line:#E5E5EA; --ink:#1D1D1F; --ink-3:#6E6E73`. Dark tokens incl. `--bg-page:#161617; --bg-board:#1F1F22; --line:#343438; --ink:#F5F5F7`. See the template for the complete sets (`--bg-sunken`, `--bg-chip`, `--line-strong`, `--ink-2/-4`, and the accent soft/line variants).

### Semantic color system (three lanes)

Color carries MEANING, never decoration. One accent per lane:

- **Blue** (`--blue`: light `#0A6CFF` / dark `#0A84FF`) -> structural / settled: decisions, metrics, process, near-term actions.
- **Amber** (`--amber`: light `#9A6A00` / dark `#FFB340`) -> human / tension: the verbatim quote, the relational / contradiction theme, pending-quantification states.
- **Red** (`--red`: light `#B3261E` / dark `#FF6961`) -> risk only.

Default to ink for neutral content. Never cross lanes (no decision in amber, no risk in blue). A small footer legend states the three lanes.

### Typography

```css
--sans: "Inter","PingFang SC","Noto Sans SC",-apple-system,system-ui,"Segoe UI",sans-serif;  /* headings + body */
--mono: "JetBrains Mono","SF Mono",ui-monospace,"Roboto Mono",monospace;                      /* labels, indices, numbers, owners, dates */
```
Load Inter + JetBrains Mono + Noto Sans SC from Google Fonts (allowlisted). Mono carries every label, section index, metric number, owner pill and due date, with `font-feature-settings:"tnum" 1` for tabular figures. h1 ~38px/700, theme titles ~18px/600, body 15px, mono labels 10.5-13px UPPERCASE tracked.

### Structure (components, top to bottom)

1. **Header**: a mono kicker (`MEETING CANVAS / <date>` with a blue status dot) + a meeting-type pill top-right; a large sans h1 title; a mono meta row (DATE / DURATION / PARTICIPANTS, segmented by hairline dividers).
2. **Section heads**: mono index (`01`) + uppercase mono label + a hairline rule filling the row, one per zone.
3. **Key Numbers**: metric cards on a grid, each with a blue left-rule, a mono uppercase label, a large mono number + unit, a note line with a `PENDING` / `EST` tag.
4. **Themes**: a hairline-divided stack; each block = mono number + sans title + a `Structural` (blue) or `Human / Tension` (amber) badge + square-bullet sub-points. The human theme carries the verbatim quote in a tinted amber quote well.
5. **Decisions**: rows, each = a numbered blue chip + decision text + a mono owner pill.
6. **Action items**: a mono-headed table (#, Task, Owner, Due); due dates colored by urgency (near-term in blue); collapses to stacked rows under ~720px.
7. **Open & Risk**: two flags side by side; `Open` neutral, `Risk` in red.
8. **AI Insights**: a hairline-divided stack that mirrors the summary's AI-insights section, condensed for glance. Each row = a mono `01` index in **amber** (the human / tension lane -- insights surface contradiction / tension; do NOT add a 4th accent) + a **bolded lead clause** + a 1-2 sentence body. 4-8 observations, ported and tightened from the summary's section 6, under the same anti-fabrication discipline (every insight traces to transcript / grounding). Sits as the analytical capstone, after Open & Risk and before the footer.
9. **Footer**: the three-lane color legend + a one-line meeting tag.

Content max-width ~960px, centered; the page background fills full width. Fully responsive per the template.

### Technical

- Single self-contained HTML document; all CSS in a `<head> <style>`; no external images. Fonts only from `fonts.googleapis.com` / `fonts.gstatic.com`.
- Print-friendly: toggle hidden in print; both themes export cleanly to PDF.
- Methodology / brand / tool terms and quotes preserved in their original language.

### Never

- Emoji icons (use inline SVG or mono labels); decorative gradients, glow, neon; heavy drop shadows.
- A fourth accent, or cross-lane color (a decision in amber, a risk in blue).
- Tiny text (nothing under ~10.5px); low-contrast secondary text on the dark theme.
- Stock clipart, "Welcome to..." headlines, TL;DR labels, filler blocks.
- Inventing decisions or action items not in the transcript.

## Output 2: Summary document (Markdown)

Sections in order, in the configured summary language (localize these section labels to your configured output language):

### 1. Overview
- Topic, date (if any), duration (if any), participants (by speaker label)
- 2-3 sentence narrative summary
- If grounding context was used: briefly note which files informed it

### 2. Discussion flow
Trace how the conversation advanced, by topic (not timeline). Quote sparingly (each < ~15 words, original language). 300-600 words.

### 3. Decisions
List. Each: what was decided, who drove it (speaker label), conditions / premises.

### 4. Action items

| # | Item | Owner | Due | Notes |
|---|------|-------|-----|-------|
| 1 | ... | Speaker 1 | next week | depends on X |

No due date -> "unspecified". No owner -> "unassigned".

### 5. Open questions
Things raised but unresolved. Not action items -- loose threads.

### 6. AI insights

The highest-value section. Written from your analytical vantage point. **Do not restate the summary above.** Surface observations participants may have missed.

Look for:
- **Tension or contradiction**: stated intent vs actual direction
- **Strategic blind spots**, read against the user's methodology + grounding context
- **Unstated assumptions** treated as settled but never tested
- **Dropped topics** that got no response or follow-up
- **Patterns across the whole conversation**: recurring concerns, avoidance, energy shifts
- **Connections to grounding context** (if applicable): e.g. a recurring issue confirmed against a profile / project file
- **Risk flags**: hard-to-keep commitments, conflicting deadlines, scope creep

Format: 4-8 observations, each 2-4 sentences. Each specific enough that the reader thinks "I didn't notice that", not "that's obvious".

**Do not include**: platitudes; restating decisions / action items; praise or judgement of participants; speculation untethered from transcript / grounding.

## Anti-fabrication rules

Three forms of fabrication to actively avoid:

1. **Inventing decisions or action items not in the transcript.** Every item must trace to actual transcript content.
2. **Inserting grounding context that was not actually discussed.** Grounding is for disambiguation, not narrative seeding. If the transcript did not mention a topic, do not bring it into the canvas just because it is in the user's notes.
3. **Embellishing AI insights with pattern claims you cannot ground.** "Speakers seem hesitant about X" requires actual evidence in the transcript words / pauses, not vibes.

When in doubt, say less. A shorter accurate artifact beats a longer fabricated one.

## Quality bar

Before each turn:

1. Every decision, action item, and AI insight is grounded in the transcript or explicitly attributed to a grounding file
2. Grounding used only for verification / disambiguation, not narrative invention
3. Code-switching preserved in the transcript; natural configured register in canvas / summary
4. Canvas renders as standalone HTML (paste into a browser, it works)
5. AI insights specific, not generic
6. Speaker labels consistent across artifacts
7. Methodology / brand / tool terms kept in original language; quotes preserved in original language
8. No em dashes anywhere

## Greeting and tone

When the user references a recording, transcript, or the drop-zone at conversation start, do not greet at length. Go straight into Phase 0/1 (silent), then Phase 2. They want the work moving, not preamble.

You are the user's senior strategy partner: direct, specific, grounded. Skip warmth padding; honest signal over polite noise. When you do not know something, say so and ask. When you find a tension between what was said and what the grounding context documents, surface it.
