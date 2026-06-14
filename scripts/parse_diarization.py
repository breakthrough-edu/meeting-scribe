#!/usr/bin/env python3
"""Parse whisperkit-cli --diarization stdout into a speaker-tagged transcript.

whisperkit-cli appends a block headed '---- Speaker Diarization Results ----' to
STDOUT (after the plain transcript) in NIST RTTM format, with the ortho field
abused to carry the transcript tokens:

    SPEAKER <file> <chan> <start> <dur> <transcript tokens...> <NA> <speaker> <NA> <NA>

The transcript token count varies (10..45+ tokens/line), so we parse by FIXED
ANCHORS, never by a positional split:
    tokens[0]  == 'SPEAKER'
    tokens[3]  == start seconds (float)
    tokens[4]  == duration seconds
    tokens[-3] == speaker label ('A' / 'B' / ...)   (3rd from last, always)
    transcript == tokens[5:-4]

Emits, sorted by start time:
    [mm:ss] Speaker A: <text>

Usage: python3 parse_diarization.py <whisperkit_stdout.txt>
Exit codes: 0 ok, 2 bad args, 3 no diarization block found.
"""
import sys

HEADER = "---- Speaker Diarization Results"


def parse(text):
    lines = text.splitlines()
    hdr = next((i for i, l in enumerate(lines) if l.strip().startswith(HEADER)), None)
    if hdr is None:
        return None
    segs = []
    for l in lines[hdr + 1:]:
        toks = l.split()
        if len(toks) < 9 or toks[0] != "SPEAKER":
            continue
        try:
            start = float(toks[3])
        except ValueError:
            continue
        speaker = toks[-3]
        body = " ".join(toks[5:-4]).strip()
        if body:
            segs.append((start, speaker, body))
    segs.sort(key=lambda s: s[0])
    out = []
    for start, speaker, body in segs:
        mm, ss = divmod(int(start), 60)
        out.append("[%02d:%02d] Speaker %s: %s" % (mm, ss, speaker, body))
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("usage: parse_diarization.py <whisperkit_stdout.txt>\n")
        sys.exit(2)
    result = parse(open(sys.argv[1], encoding="utf-8").read())
    if result is None:
        sys.stderr.write("no '%s ----' block found in input\n" % HEADER)
        sys.exit(3)
    print(result)
