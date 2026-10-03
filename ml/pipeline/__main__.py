"""Run one voice note through the pipeline and print the result.

    python -m pipeline path/to/voice-note.ogg [--out-dir DIR]
"""
import argparse
import sys
import time

from . import process_voice_note, warm_up

ap = argparse.ArgumentParser()
ap.add_argument('audio')
ap.add_argument('--out-dir', default='.')
args = ap.parse_args()

start = time.perf_counter()
warm_up()
print(f'models loaded in {time.perf_counter() - start:.1f}s', file=sys.stderr)
result = process_voice_note(args.audio, out_dir=args.out_dir)
print(result.model_dump_json(indent=2))

from .listing import _llm  # noqa: E402
_llm().close()  # avoids a noisy llama.cpp error at interpreter exit
