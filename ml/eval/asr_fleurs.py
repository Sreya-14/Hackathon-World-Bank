"""Malayalam speech-to-text error rate on FLEURS (test split), per ASR candidate.

    python -m eval.asr_fleurs --n 100            # first 100 test clips, all candidates
    python -m eval.asr_fleurs --model vrclc/Whisper-small-Malayalam --n 958

FLEURS is clean read speech, so real voice notes (outdoors, phone mic) will do worse.
Data: ml/.cache/fleurs/ml_in/{test.tsv,test/*.wav} (google/fleurs, CC-BY-4.0).
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import unicodedata
from pathlib import Path

import jiwer

from pipeline import asr, config

FLEURS = config.ML / '.cache' / 'fleurs' / 'ml_in'
RESULTS = config.ML / 'eval' / 'results'


def normalise(text: str) -> str:
    """NFC, no punctuation, single spaces: compare words, not formatting.

    Not `[^\\w\\s]`: Python's \\w excludes combining marks, which would strip every
    Malayalam vowel sign and virama and shred the words.
    """
    text = unicodedata.normalize('NFC', text)
    text = ''.join(' ' if unicodedata.category(c)[0] in 'PS' else c for c in text)
    return ' '.join(text.split())


def load(n: int) -> list[tuple[Path, str]]:
    rows = []
    with open(FLEURS / 'test.tsv', encoding='utf-8') as f:
        for row in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
            wav = FLEURS / 'test' / row[1]
            if wav.exists():
                rows.append((wav, row[2]))  # row[2] is the raw transcription
    return rows[:n]


def run(model_id: str, clips: list[tuple[Path, str]]) -> dict:
    refs, hyps, confs, secs = [], [], [], []
    for wav, ref in clips:
        start = time.perf_counter()
        t = asr.transcribe(str(wav), model_id)
        secs.append(time.perf_counter() - start)
        refs.append(normalise(ref))
        hyps.append(normalise(t.text) or '<empty>')
        confs.append(t.confidence)
    return {
        'model': model_id,
        'clips': len(clips),
        'wer': round(jiwer.wer(refs, hyps), 3),
        'cer': round(jiwer.cer(refs, hyps), 3),
        'mean_confidence': round(sum(confs) / len(confs), 3),
        'median_seconds': round(sorted(secs)[len(secs) // 2], 2),
        'examples': [{'ref': r, 'hyp': h} for r, h in list(zip(refs, hyps))[:3]],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--model', action='append', help='default: every ASR candidate')
    args = ap.parse_args()

    clips = load(args.n)
    RESULTS.mkdir(parents=True, exist_ok=True)
    for model_id in args.model or config.ASR_CANDIDATES:
        res = run(model_id, clips)
        print(json.dumps(res, ensure_ascii=False, indent=2), flush=True)
        out = RESULTS / f'asr_fleurs_{model_id.replace("/", "--")}_n{len(clips)}.json'
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
