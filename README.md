# meeting-scribe

Turn a meeting **audio file** into three artifacts, transcribing **locally** on your own machine (no cloud, no upload, no external transcription app):

1. **A corrected transcript** (light-touch cleanup, speech features and code-switching preserved)
2. **A visual canvas** -- one self-contained HTML file, the whole meeting at a glance, in a Precision Pro design with a light/dark toggle
3. **A summary** (Markdown) with a high-value **AI insights** section

It is a [Claude Code](https://claude.com/claude-code) skill. You drop an audio file into a folder, invoke the skill, and the three artifacts are written straight to your configured destination. Everything runs on-device with [Whisper](https://github.com/openai/whisper).

## Install

```bash
npx skills add breakthrough-edu/meeting-scribe
```

That is it. The first time you use the skill it runs a one-time setup that detects your platform, installs the right transcription engine, downloads the model, and writes your config. Nothing else is hard-coded.

## Requirements per platform

The skill transcribes with Whisper, but the *engine* and the *model format* differ by platform. First-run setup picks a sensible default and downloads the matching model for you. The model formats are **not interchangeable** -- each engine needs its own.

| Platform | Default engine | How it installs | Model format |
|---|---|---|---|
| **Apple Silicon mac** | `whisperkit-cli` (fastest, Apple Neural Engine) | `brew install whisperkit-cli` | CoreML folder |
| **Intel mac / Windows / Linux** | `faster-whisper` (cross-platform) | a Python venv + `pip install faster-whisper` | CTranslate2 cache |
| any (optional, power user) | `whisper.cpp` (Metal / CUDA / CPU binary, no Python) | `brew install whisper-cpp` / distro package / build | GGML `.bin` |

Common to all: **[ffmpeg](https://ffmpeg.org/)** (audio decode / resample) and roughly **1.5-3 GB of disk** for the `large-v3` model. On Apple Silicon you also need [Homebrew](https://brew.sh/); the cross-platform path needs **Python 3.9+** (and [uv](https://docs.astral.sh/uv/) is used automatically if present).

> Windows: run it under WSL, or use the `faster-whisper` engine directly.

## First-run setup asks you

- **Engine** -- it proposes the default for your platform; you can override.
- **Model** -- defaults to `large-v3` (best quality). You can pick a smaller one (`medium` / `small` / `base`) to trade quality for speed.
- **Output destination** -- a plain **folder** (default) or an **Obsidian vault** (writes via the mcp-obsidian tools).
- **Audio folders** -- a drop-zone (where you put new recordings) and an archive (where the source moves after processing).
- **Languages** -- transcription-language hint, plus the output language for the transcript / canvas / summary / replies, and an optional style register.

It then writes everything to `~/.config/meeting-transcripts/config.json` and you are ready.

## Usage

1. Drop a recording (`.wav .mp3 .m4a .flac .ogg .webm .mp4 .aac`) into your drop-zone, or hand the skill a `.txt` transcript directly.
2. Invoke the skill ("process my meeting recording", "整理这个会议", etc.).
3. It transcribes, asks one or two classification / grounding questions, then writes the three files to your destination and prints a compact summary. You review the files in place and ask for edits.

The artifacts are never echoed in full into chat -- they are generated straight into the files, which keeps it fast and token-lean.

## The canvas

The visual canvas is the differentiator. It is a single self-contained HTML document in a **Precision Pro** design language (Apple developer / Xcode aesthetic): a modular grid, monospace data, hairline rules, generous whitespace.

- **Light + dark**, with a corner toggle. It opens in the viewer's system mode and remembers your choice. The toggle is hidden when you print or export to PDF.
- **Three-lane semantic color**: blue = structural / decisions / metrics, amber = human / tension / the verbatim quote, red = risk only. Color always carries meaning, never decoration.

A complete worked example ships at [`assets/canvas-template.html`](assets/canvas-template.html) -- open it in any browser to see the design. The skill builds every canvas from that template.

## Configuration

All per-user settings live in **one external file**, `~/.config/meeting-transcripts/config.json`. Nothing is stored inside the skill, on purpose: skills installed via `npx skills` or a plugin marketplace sit in copied / git-managed locations that get overwritten on update, so settings kept inside the skill would not survive. The external config does, across every install channel and update.

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
  "vault_context_skill": null
}
```

To change any path, language, engine or model, edit that file -- not the skill.

## Output language

Output language is entirely yours to set, per artifact (`language.transcript / canvas / summary / replies`). The transcript defaults to `as-spoken`, which **preserves the spoken language(s) and code-switching exactly** (it will not translate, say, mixed Mandarin-English back into one language). The canvas and summary follow whatever you configure. The shipped worked example is in English purely as a neutral reference.

## Privacy

Everything runs on your machine. The audio, the transcript, and the artifacts never leave it. The only network access is a one-time model download from Hugging Face during setup, and loading web fonts when you open the canvas in a browser.

## Troubleshooting

- **"model not found" / garbled output** -- the model format must match the engine (CoreML folder vs CT2 cache vs GGML `.bin`). Re-run setup for the engine you actually configured.
- **faster-whisper "command not found" / import errors** -- `python_bin` must point at the venv that has `faster-whisper` installed. Setup creates this at `~/.config/meeting-transcripts/venv`.
- **whisper.cpp wants 16 kHz WAV** -- the skill pipes non-WAV through ffmpeg automatically; make sure ffmpeg is installed.
- **Slow on CPU** -- `whisperkit-cli` (Apple Silicon) uses the Neural Engine and is fastest. On CPU, `faster-whisper` with `compute_type: "int8"` is the practical default; large files transcribe in the background.

## License

MIT. See [LICENSE](LICENSE).
