#!/usr/bin/env python3
"""meeting-scribe: faster-whisper transcription + sherpa-onnx speaker diarization.

Emits the unified speaker-tagged format (one turn per line, sorted by time):
    [mm:ss] Speaker A: <text>

Args (all positional):
    <audio_16k_mono_wav> <model> <model_cache> <lang|auto> <compute|auto>
    <num_speakers|0> <segmentation_onnx> <embedding_onnx>

num_speakers <= 0 -> auto-detect the speaker count.
The audio MUST be 16 kHz mono 16-bit WAV (the caller converts via ffmpeg first);
faster-whisper reads it fine and sherpa-onnx requires it.

This is the OPTIONAL diarization add-on. It needs, in the same venv:
faster-whisper, sherpa-onnx, numpy. The two ONNX models are public (no HF token).
Diarization is turn-level (not word-level); speaker labels are arbitrary A / B.
"""
import sys
import wave
import numpy as np
from faster_whisper import WhisperModel
import sherpa_onnx as so


def read16k(path):
    with wave.open(path) as w:
        if not (w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2):
            sys.stderr.write("diarization needs 16 kHz mono 16-bit WAV\n")
            sys.exit(2)
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def main():
    audio, model, cache, lang, compute, k, seg, emb = sys.argv[1:9]
    lang = None if lang in ("auto", "", None) else lang
    ct = "int8" if compute in ("auto", "", None) else compute
    k = int(k)

    wm = WhisperModel(model, device="auto", compute_type=ct, download_root=cache)
    segments, info = wm.transcribe(audio, language=lang)
    segs = [(s.start, s.end, s.text.strip()) for s in segments if s.text.strip()]
    sys.stderr.write("[detected] %s p=%.2f\n" % (info.language, info.language_probability))

    clustering = (so.FastClusteringConfig(num_clusters=k) if k > 0
                  else so.FastClusteringConfig(num_clusters=-1, threshold=0.5))
    cfg = so.OfflineSpeakerDiarizationConfig(
        segmentation=so.OfflineSpeakerSegmentationModelConfig(
            pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=seg)),
        embedding=so.SpeakerEmbeddingExtractorConfig(model=emb),
        clustering=clustering, min_duration_on=0.2, min_duration_off=0.3)
    if not cfg.validate():
        sys.stderr.write("sherpa-onnx diarization config invalid (check model paths)\n")
        sys.exit(3)
    sd = so.OfflineSpeakerDiarization(cfg)
    ranges = [(r.start, r.end, r.speaker) for r in sd.process(read16k(audio)).sort_by_start_time()]

    def overlap(a0, a1, b0, b1):
        return max(0.0, min(a1, b1) - max(a0, b0))

    def speaker_for(s0, s1):
        best, best_ov = None, 0.0
        for d0, d1, sp in ranges:
            ov = overlap(s0, s1, d0, d1)
            if ov > best_ov:
                best_ov, best = ov, sp
        return best if best is not None else 0

    label, nxt = {}, [0]

    def letter(sp):
        if sp not in label:
            label[sp] = chr(ord('A') + nxt[0])
            nxt[0] += 1
        return label[sp]

    for s0, s1, text in segs:
        mm, ss = divmod(int(s0), 60)
        print("[%02d:%02d] Speaker %s: %s" % (mm, ss, letter(speaker_for(s0, s1)), text))


if __name__ == "__main__":
    if len(sys.argv) < 9:
        sys.stderr.write("usage: fw_diarize.py <wav16k> <model> <cache> <lang|auto> "
                         "<compute|auto> <num_speakers|0> <seg.onnx> <emb.onnx>\n")
        sys.exit(2)
    main()
