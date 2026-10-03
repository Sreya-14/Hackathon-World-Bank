# Tour Assistant — offline tourism assistant

Hack-Nation Challenge 04 (Tourism). An offline, voice-first PWA that helps a small farm-tour operator turn a foreign visitor's enquiry into a confirmed booking. Guests write in English or German; the operator reads and hears Malayalam or Tamil, and approves every message.

- `app/` — Vite + React + TS PWA; models run on-device in a Web Worker (transformers.js)
- `ml/` — model export to int8 ONNX, intent dataset, evaluation scripts
- `docs/WORKSPLIT.md` — who builds what, the engine contract, merge plan

Datasets, licenses, model sizes and measured results: to be filled in before submission.
