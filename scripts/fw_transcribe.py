#!/usr/bin/env python3
"""meeting-scribe: faster-whisper transcription wrapper.

Args:
    transcribe: <audio> <model> <model_cache> <lang|auto> <compute|auto>
    warm:       --warm <model> <model_cache> <compute|auto>

Prints the transcript (one segment per line) to stdout; faster-whisper decodes
most audio formats directly (no ffmpeg needed). Runs cross-platform on CPU
(int8) or CUDA (float16); device and compute type auto-selected.
"""
import sys
from faster_whisper import WhisperModel


def load(model, cache, compute):
    ct = "int8" if compute in ("auto", "", None) else compute
    return WhisperModel(model, device="auto", compute_type=ct, download_root=cache)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--warm":
        load(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "auto")
        print("OK", file=sys.stderr)
        sys.exit(0)
    audio, model, cache = sys.argv[1], sys.argv[2], sys.argv[3]
    lang = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "auto" else None
    compute = sys.argv[5] if len(sys.argv) > 5 else "auto"
    m = load(model, cache, compute)
    segments, info = m.transcribe(audio, language=lang)
    print("[detected] %s p=%.2f" % (info.language, info.language_probability), file=sys.stderr)
    for s in segments:
        print(s.text.strip())
