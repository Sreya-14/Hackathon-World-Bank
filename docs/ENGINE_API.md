# Engine API: how the backend turns a voice note into a listing

The engine (`ml/pipeline/`) takes Noor's Malayalam voice note and returns a draft listing in English and German, plus a Malayalam audio read-back for her to approve. It runs on the server's CPU with small local models (~2.7 GB). No API keys and no network calls at run time.

Types: [`ml/pipeline/schema.py`](../ml/pipeline/schema.py). The tourist app's side is in [`LISTINGS_API.md`](LISTINGS_API.md).

## Setup

Keep the environment and models **outside** OneDrive/Dropbox and outside the repo: they are several GB and tens of thousands of files, which sync tools and GitHub Desktop choke on. `LANTERN_CACHE_DIR` sets where models and test data go (default `ml/.cache`).

```bash
# Windows example; on Linux/macOS use bin/ instead of Scripts/
python -m venv C:/Users/<you>/lantern-ml/venv
set LANTERN_CACHE_DIR=C:/Users/<you>/lantern-ml/cache        # PowerShell: $env:LANTERN_CACHE_DIR = "..."
C:/Users/<you>/lantern-ml/venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cpu
C:/Users/<you>/lantern-ml/venv/Scripts/pip install -r ml/requirements-pipeline.txt -r server/requirements.txt --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
cd ml
C:/Users/<you>/lantern-ml/venv/Scripts/python -m pipeline.models      # download + convert models (~2.7 GB, once)
C:/Users/<you>/lantern-ml/venv/Scripts/python -m pipeline voice.ogg   # one voice note → result as JSON
```

Evaluation (results go to `ml/eval/results/`):

```bash
python -m eval.asr_fleurs --model vrclc/Whisper-small-Malayalam --n 150   # speech-to-text error rate (FLEURS Malayalam)
python -m eval.listing_eval                                              # confidently-wrong rate on labelled descriptions
python -m eval.malayalam_checklist                                       # regenerate docs/MALAYALAM_CHECK.md
```

## Calling it

```python
from pipeline import warm_up, process_voice_note, process_transcript

warm_up()                                    # at server start: loads every model once (~20 s)
result = process_voice_note('/tmp/note.ogg', out_dir='/srv/media')   # any audio PyAV reads, incl. WhatsApp .ogg/.opus
result = process_transcript('…Malayalam text…')                       # same, skipping speech to text (typed fallback)
result.model_dump()                          # plain dict / JSON
```

- One call at a time: the models use every CPU core. Put voice notes in a queue and process them in order.
- It takes 2–3 minutes for an 18 s voice note on a laptop CPU (speech to text 80–120 s with the default Whisper-medium, then ~60 s for the rest). WhatsApp is asynchronous, so send a short "got it, preparing your listing" clip first. `LANTERN_ASR_MODEL=vrclc/Whisper-small-Malayalam` halves the speech-to-text time but mishears much more on real voices (see `ml/eval/results.md`).

## What comes back

| Field | Meaning |
|---|---|
| `status` | `ready_for_approval` or `needs_review` |
| `reasons` | Why it needs review (below). Empty when ready. |
| `transcript` / `transcript_en` | What she said, in Malayalam and machine-translated English. Store these for the partner who reviews. |
| `listing.category` | `food`, `craft`, `textile`, `tour`, `experience` or `other` (same list as the app). |
| `listing.text.en` / `.de` | `title`, `description`, `price`, `hours`, `duration`, `includes`, `meeting_point`. Facts are `null` unless she said them. |
| `listing.machine_translated` | Languages produced by translation (`["de"]`), to label in the app if wanted. |
| `readback_text` / `readback_wav` | The Malayalam she hears, and the WAV path. WhatsApp plays voice notes as OGG/Opus, so convert: `ffmpeg -i readback.wav -c:a libopus readback.ogg`. |
| `timings` | Seconds per stage, for the metrics slide. |

### `needs_review`: what the bot should do

Nothing is published. Play her the "I'm not sure I understood, please say it again" clip, and keep the result for a partner to check.

| Reason | Meaning |
|---|---|
| `no_speech` | Silence or noise only |
| `wrong_language` | The transcript isn't Malayalam |
| `unclear_audio` | Low speech-to-text confidence |
| `unclear_translation` | The English is much shorter than what she said, so content was lost |
| `empty_listing` | Too little said to make a listing |
| `invalid_listing` | The listing writer failed twice |
| `ungrounded_fact` | A number in the listing (price, time…) that she never said |

## Mapping to the tourist app's listing (`LISTINGS_API.md`)

| App field | From the engine |
|---|---|
| `category` | `listing.category` |
| `title` | `{ "en": listing.text.en.title, "de": listing.text.de.title }` |
| `description` | `{ "en": listing.text.en.description, "de": listing.text.de.description }` |
| `price` | `listing.text.en.price` (`null` → the app shows "Ask the host") |
| `hours` | `listing.text.en.hours` |

Location, privacy, photo, check-ins, `verified` and `met_count` come from the bot, not the engine.

## Known limits (say these in the video)

- Speech to text: ~10% character error rate on FLEURS Malayalam (clean read speech). Outdoor voice notes will do worse.
- Place names outside the list in `ml/pipeline/places.py` can be mistranslated (Edakkal → "gravel cave"). Add the operator's area to that list.
- The translator (NLLB-200) and the read-back voice (MMS-TTS) are both licensed CC-BY-NC-4.0: fine for this entry, but a commercial version needs different models. The speech-to-text fine-tune and Qwen2.5 are Apache-2.0.
- Translation errors pass through ("Kerala meals served" → "Kerala will be handed over to my house"). Numbers are checked automatically; other invented details are not, which is why the host approves the Malayalam read-back.
- Measured results (speech-to-text error rate, confidently-wrong rate, speed): [`ml/eval/results.md`](../ml/eval/results.md).
