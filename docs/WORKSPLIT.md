# Work split (team of 2)

Two tracks that only meet at one file: [`app/src/engine/types.ts`](../app/src/engine/types.ts).
The App track builds against a mock engine, so it never waits on models.
At merge, the switch is `npm run dev:real` instead of `npm run dev`.

| | **Engine track** (ML + data) | **App track** (frontend + product) |
|---|---|---|
| Branch | `engine` | `app` |
| Owns | `ml/**`, `app/src/engine/real.ts`, `app/src/engine/worker.ts`, `app/src/engine/*` (new files), `app/public/models/` (gitignored) | everything else under `app/`, `docs/evidence.md`, `app/src/engine/mock.ts` |
| Never touches | UI, storage, templates | `real.ts`, `worker.ts`, `ml/` |
| Delivers | `getEngine()` that meets the contract on a phone in airplane mode, plus measured numbers | The whole workflow working on the mock, installable, offline-ready |

**Shared and frozen:** `types.ts`, `engine/index.ts`, `package.json`, `vite.config.ts`. If one of them must change, make a small commit on `main`, tell the other person, and both rebase. Don't change them on a track branch.

---

## Engine track

Done when `npm run dev:real` passes every row in the merge checklist below.

1. **Export + load test (H0–3, riskiest, do first)**
   - `ml/export_models.py`: Optimum → int8 ONNX for `Helsinki-NLP/opus-mt-en-sw`, `opus-mt-mul-en` (or use `Xenova/` builds where they exist), `all-MiniLM-L6-v2` → writes to `app/public/models/`. Print the MB per model.
   - `worker.ts`: load from `/models/`, `allowRemoteModels = false`, **local ORT wasm paths** (the default CDN breaks airplane mode).
   - Check: one English sentence → Swahili in Chrome on the Android phone, in airplane mode.
2. **`understand()` (H3–7)**
   - Language detection for en/fr/de (heuristic or `franc-min`; add it via `main` if it's a new dependency). Any other language → `unsupported_language`.
   - Pivot: fr/de → English (mul-en), then English → Swahili (en-sw).
   - Intent sorting: MiniLM embeddings vs. labelled examples, nearest-example similarity, threshold in `engine/config.ts`. `accepted` = intents above threshold; more than 2 → `mixed_intents`.
   - **Dataset:** `ml/data/enquiries.csv` with columns `text,lang,intent,split,source` (source = `team` | `synthetic`). Aim for ~300 team-written + synthetic, EN/FR/DE, including `other` negatives (MASSIVE). Build step exports the train split to `app/public/intent-examples.json`.
3. **Voice (H7–10)**
   - `speak()`: `facebook/mms-tts-swh` → WAV Blob.
   - `transcribe()`: Whisper tiny (base if memory allows), language forced to Swahili.
   - `translateFromSwahili()`: `opus-mt-sw-en` (+ en→fr/de if time allows); otherwise return `null`.
4. **Evaluation (H10–15)**, scripts in `ml/eval/` so judges can rerun them
   - Intent: accuracy, macro-F1, confidently-wrong rate, not-sure rate, confusion matrix, chosen threshold. Prefer evaluating with the same ONNX int8 model the browser uses.
   - Translation: chrF on a FLORES-200 eng→swh devtest subset, plus 3 good and 3 bad examples.
   - ASR: WER on FLEURS sw (tiny vs base) + 10 noisy team recordings.
   - Size per pack; latency from share to read-aloud (20 runs on the phone, median and worst).
   - Output: `ml/eval/results.md`, which feeds the metrics slide.
5. **Submission share:** README sections on datasets (license, size, gaps), models (license, size) and evaluation.

## App track

Done when the full demo runs on the mock: share → summary → draft → approve → outbox → booking.

1. **Shell (H0–3)**: install, routing, `/share?text=` handler + paste box, big-icon audio-first layout, "preparing" screen driven by `LoadProgress`.
2. **Content (H1–4)**: `app/src/content/`
   - `TourFacts` type (price, days, hours, duration, meeting point, included, dietary/kids/access yes/no, payment).
   - Reply templates per intent in **en, fr, de** (sent to the guest) and **sw** (what Noor reads and hears), with `{placeholders}` filled from her facts. Have a person check each translation and label any that are generated.
   - Swahili one-line summary per intent (what gets read aloud, e.g. "Mgeni anauliza bei" – "the guest is asking the price"). Read the template summary aloud rather than the raw machine translation, which is safer.
   - The footer line on every outgoing message ("prepared with a translation tool, approved by Noor").
3. **Core loop UI (H3–7)**: Dexie DB (facts, enquiries, bookings, outbox) → enquiry screen (icons, summary, labelled MT text) → draft from template → approve / edit → outbox → `sms:` / `wa.me` links. "Not sure" screen showing the reason.
   - Rules: `chrono-node` for dates, regex for group size → booking confirm/decline.
4. **Voice UI (H7–10)**: play button (`speak`), MediaRecorder → `transcribe`. **Facts setup asks one question per fact** and reads each answer back for confirmation (Swahili numbers and weekdays parsed by regex; we're not doing free-form extraction). "Not sure" voice answer → `translateFromSwahili` → labelled; if it returns `null`, send "Noor will call you".
5. **Polish (H10–13)**: booking log + reminders, outbox badge clears when back online, PIN, 90-day auto-delete, export/wipe, app icons.
6. **Evidence + submission share**: `docs/evidence.md` (UN Tourism/WDI, Enterprise Surveys, GSMA, Findex, OSM Overpass, OpenCelliD, each with source, year and country), problem statement, video script, deck.

Test the mock's edge cases before merging: a two-intent message, a three-intent message (mixed), gibberish (not sure), and a non-EN/FR/DE message (unsupported).

---

## Timeline and merge

| Hours | Engine | App |
|---|---|---|
| H0 | Pull `main` (this scaffold), branch | Pull `main`, branch |
| H0–3 | Export + phone load test | Shell + share target |
| H1–7 | `understand()` + dataset | Content + core loop on mock |
| **H7** | **Checkpoint merge** (below) | |
| H7–10 | Voice models | Voice UI |
| H10–15 | Evaluation, numbers | Polish, evidence |
| **H16** | **Final merge, feature freeze** | |
| H16+ | README data/eval sections, metrics slide | Video, deck, README rest |

**Why a checkpoint merge at H7:** the plan's milestone is "core loop offline by H7", and that needs both tracks. It also brings any contract mismatches to the surface while there's still time. With disjoint file ownership it should merge cleanly:

```bash
git checkout main && git merge engine && git merge app
```

If it isn't ready at H7, apply the plan's cut rule at H9: drop voice input and the booking log.

### Merge checklist (`npm run dev:real`, phone, airplane mode)

- [ ] App loads with no network after one online visit (models + ORT wasm cached)
- [ ] English, French and German enquiries → correct intent + Swahili text
- [ ] Ambiguous enquiry → "not sure" with a reason
- [ ] Reply approved → outbox → opens SMS/WhatsApp once back online
- [ ] Read-aloud plays (voice pack); app still works without the voice pack

## Setup

Node ≥ 20 (`app/`), Python 3.10+ (`ml/`).

```bash
cd app && npm install && npm run dev
```

The first person to run `npm install` commits `package-lock.json` to `main` before branching.
