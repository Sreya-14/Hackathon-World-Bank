"""How often is the engine confidently wrong? Malayalam description → listing, scored against labels.

    python -m eval.listing_eval

Cases: eval/data/listing_cases.jsonl (synthetic, written by the team; one line each).
Runs from the Malayalam TEXT (process_transcript), so it measures everything after
speech to text; eval/asr_fleurs.py measures speech to text.

A result is CONFIDENTLY WRONG when it is ready_for_approval but should not be: wrong
category, a number the host never said, or a case that should have been "not sure".
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pipeline import config, process_transcript, warm_up
from pipeline.grounding import numbers

DATA = Path(__file__).parent / 'data' / 'listing_cases.jsonl'
RESULTS = config.ML / 'eval' / 'results'


def all_text(t) -> str:
    return ' '.join(filter(None, [t.title, t.description, t.price, t.hours, t.duration, t.meeting_point, *t.includes]))


def score(case: dict, r) -> dict:
    row = {'id': case['id'], 'expected': case['expect'], 'status': r.status, 'reasons': r.reasons,
           'transcript_en': r.transcript_en, 'seconds': round(sum(t.seconds for t in r.timings), 1)}
    if r.status != 'ready_for_approval':
        row['outcome'] = 'held (correct)' if case['expect'] == 'needs_review' else 'held (missed listing)'
        return row
    en = r.listing.text['en']
    invented = sorted(numbers(all_text(en)) - set(case['numbers']) - {0.0})
    price_field = case['price'] is not None and case['price'] in numbers(en.price or '')
    price_anywhere = case['price'] is not None and case['price'] in numbers(all_text(en))
    row.update(
        category=r.listing.category,
        category_ok=r.listing.category in case['category'],
        invented_numbers=invented,
        price_in_field=price_field,
        price_anywhere=price_anywhere if case['price'] is not None else (en.price is None),
        title=en.title, description=en.description, price=en.price, hours=en.hours, duration=en.duration,
    )
    wrong = case['expect'] == 'needs_review' or not row['category_ok'] or bool(invented)
    row['outcome'] = 'CONFIDENTLY WRONG' if wrong else 'correct'
    return row


def main() -> None:
    cases = [json.loads(line) for line in DATA.read_text(encoding='utf-8').splitlines() if line.strip()]
    warm_up()
    out_dir = tempfile.mkdtemp(prefix='listing-eval-')
    rows = []
    for case in cases:
        rows.append(score(case, process_transcript(case['ml'], out_dir=out_dir)))
        r = rows[-1]
        print(f"{r['id']:<22} {r['outcome']:<22} {r.get('category', ''):<11} invented={r.get('invented_numbers', '')} "
              f"price={r.get('price')}  ({r['seconds']}s)", flush=True)

    n = len(rows)
    ready = [r for r in rows if r['status'] == 'ready_for_approval']
    should_list = [r for r in rows if r['expected'] == 'ready']
    summary = {
        'cases': n,
        'synthetic': True,
        'confidently_wrong': sum(r['outcome'] == 'CONFIDENTLY WRONG' for r in rows),
        'correct_listings': sum(r['outcome'] == 'correct' for r in rows),
        'held_correctly': sum(r['outcome'] == 'held (correct)' for r in rows),
        'held_but_should_list': sum(r['outcome'] == 'held (missed listing)' for r in rows),
        'category_accuracy_when_listed': round(sum(r['category_ok'] for r in ready) / len(ready), 3) if ready else None,
        'price_in_price_field': f"{sum(r.get('price_in_field', False) for r in should_list)}/"
                                f"{sum(1 for c in cases if c['expect'] == 'ready' and c['price'] is not None)}",
        'median_seconds_per_listing': sorted(r['seconds'] for r in ready)[len(ready) // 2] if ready else None,
    }
    summary['confidently_wrong_rate'] = round(summary['confidently_wrong'] / n, 3)
    print(json.dumps(summary, indent=2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'listing_eval.json').write_text(
        json.dumps({'llm': config.LLM_FILE, 'summary': summary, 'cases': rows}, ensure_ascii=False, indent=2),
        encoding='utf-8')

    from pipeline.listing import _llm
    _llm().close()  # avoids a noisy llama.cpp error at interpreter exit


if __name__ == '__main__':
    main()
