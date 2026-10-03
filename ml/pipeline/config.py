"""Model choices and thresholds. Thresholds are rough until the eval tunes them."""
import os
from pathlib import Path

ML = Path(__file__).resolve().parent.parent
MODELS_DIR = ML / '.cache' / 'pipeline-models'

# Physical cores; hyper-threads don't help these models.
CPU_THREADS = max(1, (os.cpu_count() or 2) // 2)

# Speech to text: a Whisper small fine-tuned on Malayalam, converted to CTranslate2 int8.
# Candidates are compared on FLEURS ml in eval; vanilla whisper-small is the baseline.
ASR_CANDIDATES = [
    'vrclc/Whisper-small-Malayalam',
    'kavyamanohar/whisper-small-malayalam',
    'openai/whisper-small',
]
ASR_MODEL = 'vrclc/Whisper-small-Malayalam'
ASR_LANGUAGE = 'ml'
# Whisper decodes at most 224 tokens per window; Malayalam needs ~16 tokens/s of speech.
ASR_CHUNK_SECONDS = 10

# Translation: one NLLB model covers Malayalam → English and English → German.
NLLB_MODEL = 'facebook/nllb-200-distilled-600M'
NLLB_CODES = {'ml': 'mal_Mlym', 'en': 'eng_Latn', 'de': 'deu_Latn'}

# Listing writer: small instruct model through llama.cpp, JSON constrained by a schema.
LLM_REPO = 'Qwen/Qwen2.5-1.5B-Instruct-GGUF'
LLM_FILE = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'

# Read-back voice.
TTS_MODEL = 'facebook/mms-tts-mal'

# "Not sure" thresholds.
MIN_ASR_CONFIDENCE = 0.55     # mean token probability across the transcript
MAX_NO_SPEECH_PROB = 0.6
MIN_MALAYALAM_SHARE = 0.6     # share of transcript letters in Malayalam script
MIN_TRANSCRIPT_CHARS = 15
# Malayalam fuses words, so English normally has MORE words than the Malayalam it came from.
MIN_EN_TO_ML_WORD_RATIO = 0.9
