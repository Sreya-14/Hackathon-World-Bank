"""Model choices and thresholds. Thresholds are rough until the eval tunes them."""
import os
from pathlib import Path

ML = Path(__file__).resolve().parent.parent
# Models and test data (~5 GB). Keep them out of synced folders such as OneDrive:
# set LANTERN_CACHE_DIR, e.g. C:/Users/<you>/lantern-ml/cache
CACHE_DIR = Path(os.getenv('LANTERN_CACHE_DIR', str(ML / '.cache')))
MODELS_DIR = CACHE_DIR / 'pipeline-models'

# Physical cores; hyper-threads don't help these models.
CPU_THREADS = max(1, (os.cpu_count() or 2) // 2)

# Speech to text: Whisper fine-tuned on Malayalam, converted to CTranslate2 int8.
# On real phone voice notes, medium got 7%/12% character errors vs small's 19%/26% (and
# small's errors became "potato tree", "fortress" in the listing), at ~2× the time.
# LANTERN_ASR_MODEL=vrclc/Whisper-small-Malayalam is the faster fallback.
ASR_CANDIDATES = [
    'thennal/whisper-medium-ml',
    'vrclc/Whisper-small-Malayalam',
    'kavyamanohar/whisper-small-malayalam',
    'openai/whisper-small',
]
ASR_MODEL = os.getenv('LANTERN_ASR_MODEL', 'thennal/whisper-medium-ml')
ASR_LANGUAGE = 'ml'
# Windows split at pauses; longer ones send the decoder into repetition loops (see asr.py).
ASR_CHUNK_SECONDS = 10

# Translation: one NLLB model covers Malayalam → English and English → German.
NLLB_MODEL = 'facebook/nllb-200-distilled-600M'
NLLB_CODES = {'ml': 'mal_Mlym', 'en': 'eng_Latn', 'de': 'deu_Latn'}

# Listing writer: small instruct model through llama.cpp, JSON constrained by a schema.
LLM_REPO = 'Qwen/Qwen2.5-1.5B-Instruct-GGUF'
LLM_FILE = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'

# Read-back voice.
TTS_MODEL = 'facebook/mms-tts-mal'
# English voice for the bot's prompt clips in the demo setting (server PROMPT_VOICE=en).
TTS_MODEL_EN = 'facebook/mms-tts-eng'

# "Not sure" thresholds.
MIN_ASR_CONFIDENCE = 0.55     # mean token probability across the transcript
MAX_NO_SPEECH_PROB = 0.6
MIN_MALAYALAM_SHARE = 0.6     # share of transcript letters in Malayalam script
MIN_TRANSCRIPT_CHARS = 15
# Malayalam fuses words, so English normally has MORE words than the Malayalam it came from.
MIN_EN_TO_ML_WORD_RATIO = 0.9
