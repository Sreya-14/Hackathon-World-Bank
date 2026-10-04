"""Protect Kerala place names and key tourism words from translation.

NLLB reads മൂന്നാറിൽ ("in Munnar") as മൂന്ന് ("three") and writes "a three-hour tour";
തേക്കടിയിൽ became "from the base"; കുരുമുളക് (pepper) came out as corn, pumpkin or cucumber.
Replacing the word with its English form before translation (മൂന്നാറിൽ → "Munnar-ൽ")
makes NLLB copy it through. Malayalam inflects the word itself, so each stem lists its
forms before a case ending, longest first (ട്ട before ട്).

Speech to text also misspells long names (മാനന്തവാടി → "മാനന്ദവാടിയേലും"), so long
terms are matched loosely too. Short words are not: കൊട്ട (basket) is as close to
കുട്ടികൾ (children) as to the misheard കോട്ട, so those must be spelled right.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# (Malayalam stem regex, English name). Extend for the operator's area.
PLACES = [
    (r'ഫോർട്ട് കൊച്ചി', 'Fort Kochi'),
    (r'മൂന്നാ(?:റ|ർ)', 'Munnar'),
    (r'തേക്കടി', 'Thekkady'),
    (r'കുമളി', 'Kumily'),
    (r'ആലപ്പുഴ', 'Alappuzha'),
    (r'കൊച്ചി', 'Kochi'),
    (r'കുമരക(?:ത്ത|ം)', 'Kumarakom'),
    (r'വയനാ(?:ട്ട|ട്)', 'Wayanad'),
    (r'തൃശ്ശൂ(?:ര|ർ)', 'Thrissur'),
    (r'കോഴിക്കോ(?:ട്ട|ട്)', 'Kozhikode'),
    (r'വർക്കല', 'Varkala'),
    (r'കോവള(?:ത്ത|ം)', 'Kovalam'),
    (r'തിരുവനന്തപുര(?:ത്ത|ം)', 'Thiruvananthapuram'),
    (r'കണ്ണൂ(?:ര|ർ)', 'Kannur'),
    (r'ഇടുക്കി', 'Idukki'),
    (r'അതിരപ്പിള്ളി', 'Athirappilly'),
    (r'വാഗമ(?:ണ്ണ|ൺ)', 'Vagamon'),
    (r'കോട്ടയ(?:ത്ത|ം)', 'Kottayam'),
    (r'പാലക്കാ(?:ട്ട|ട്)', 'Palakkad'),
    (r'എറണാകുള(?:ത്ത|ം)', 'Ernakulam'),
    # Wayanad, the demo area (the tourist map ships Wayanad tiles).
    (r'കൽപ്പറ്റ', 'Kalpetta'),
    (r'സുൽത്താൻ ബത്തേരി', 'Sulthan Bathery'),
    (r'ബത്തേരി', 'Bathery'),
    (r'മാനന്തവാടി', 'Mananthavady'),
    (r'വൈത്തിരി', 'Vythiri'),
    (r'മേപ്പാടി', 'Meppadi'),
    (r'ലക്കിടി', 'Lakkidi'),
    (r'പൂക്കോ(?:ട്ട|ട്)', 'Pookode'),
    (r'ബാണാസുര', 'Banasura'),
    (r'എടക്ക(?:ല|ൽ)', 'Edakkal'),
    (r'ചെമ്പ്ര', 'Chembra'),
    (r'കുറുവ', 'Kuruva'),
    (r'തിരുനെല്ലി', 'Thirunelli'),
    (r'മുത്തങ്ങ', 'Muthanga'),
    (r'പുൽപ്പള്ളി', 'Pulpally'),
    (r'അമ്പലവയ(?:ല|ൽ)', 'Ambalavayal'),
]

# (Malayalam stem regex, English). Farm, food and craft words NLLB gets wrong.
WORDS = [
    # Booking phrases: with no subject in Malayalam, NLLB turned "call one day before" into
    # "I should have called you a day ago". Longest first.
    (r'ഒരു ദിവസം (?:മുമ്പ്|മുൻപ്|മുൻപേ|മുമ്പേ) (?:വിളിച്ച് പറയണം|വിളിക്കണം|അറിയിക്കണം)', 'please call one day in advance'),
    (r'(?:മുൻകൂട്ടി|മുമ്പ്|മുൻപ്) (?:വിളിച്ച് പറയണം|വിളിക്കണം|അറിയിക്കണം)', 'please call in advance'),
    (r'കാപ്പിത്തോട്ട(?:ത്ത|ം)', 'coffee plantation'),
    (r'തേയിലത്തോട്ട(?:ത്ത|ം)', 'tea plantation'),
    (r'കുരുമുളക', 'pepper'),
    (r'കാപ്പി', 'coffee'),
    (r'തേയില', 'tea'),
    (r'ഏല(?:ത്ത|ം)', 'cardamom'),
    (r'തേനീച്ച', 'bees'),
    (r'തേ(?:ന|ൻ)', 'honey'),
    (r'കൊട്ട(?!ാ)', 'basket'),          # not കൊട്ടാരം (palace)
    (r'മുള(?:(?=കൊ)|(?![കച]))', 'bamboo'),  # മുളകൊണ്ട് (with bamboo), not മുളക് (chilli), മുളച്ച (sprouted)
    (r'വിളക്ക', 'lamp'),
    (r'കളിമ(?:ണ്ണ|ൺ)', 'clay'),
    (r'കൈത്തറി', 'handloom'),
    (r'സാരി', 'saree'),
    (r'ഊണ', 'meals'),
    (r'സദ്യ', 'sadya feast'),
    # Kerala dishes: NLLB turned "rice, sambar, avial, payasam" into "Chour Sammar Avial sauce".
    (r'ഉച്ചഭക്ഷണ', 'lunch'),
    (r'അത്താഴ', 'dinner'),
    (r'പ്രഭാതഭക്ഷണ', 'breakfast'),
    (r'ചോ(?:റ|ർ)', 'rice'),            # ചോറ്, or ചോർ as speech to text writes it
    (r'സാമ്പാ(?:റ|ർ)', 'sambar'),
    (r'അവിയ(?:ല|ൽ)', 'avial'),
    (r'പായസ(?:ത്ത|ം)', 'payasam (sweet pudding)'),
    (r'പുട്ട', 'puttu'),
    (r'അപ്പ(?:ത്ത|ം)', 'appam'),
    (r'ദോശ', 'dosa'),
    (r'ഇഡ്ഡലി', 'idli'),
    (r'കപ്പ(?![ലൽ])', 'tapioca'),       # not കപ്പൽ / കപ്പലിൽ (ship)
    (r'മീ(?:ന|ൻ)', 'fish'),
    (r'പലഹാര(?:ങ്ങ|ം)', 'snacks'),
]

# Long terms that speech to text misspells; matched loosely (see _fuzzy). Plain base forms.
# Checked against 344 FLEURS sentences: at 0.8 nothing everyday matches. Not here, because
# everyday words come too close: ആലപ്പുഴ (ആലിപ്പഴം, hailstone, 0.86). Not here because the
# misspelling scored too low: കുരുമുളക് (കൂരുമോളകും, 0.71).
FUZZY = ['കൽപ്പറ്റ', 'മാനന്തവാടി', 'വൈത്തിരി', 'മേപ്പാടി', 'അമ്പലവയൽ', 'പുൽപ്പള്ളി', 'തിരുനെല്ലി',
         'മൂന്നാർ', 'തേക്കടി', 'കുമരകം', 'കാപ്പിത്തോട്ടം', 'തേയിലത്തോട്ടം', 'കൈത്തറി']
FUZZY_MIN = 0.8

_MARKS = r'[\u0d3e-\u0d4d\u0d57\u0d62\u0d63]'  # vowel signs and virama
# Each term must start a word, or short ones (\u0d2e\u0d41\u0d33) would match inside longer words.
_PATTERNS = [(re.compile(f'(?<![\u0d00-\u0d7f]){stem}([\u0d00-\u0d7f]*)'), name) for stem, name in PLACES + WORDS]
_TOKEN = re.compile(r'[\u0d00-\u0d7f]+')


def _ending(rest: str) -> str:
    """Case ending to keep after the English name: drop glides and dangling vowel signs (യിൽ → ൽ)."""
    rest = re.sub(f'^[യവ]?{_MARKS}*', '', rest)
    return f'-{rest}' if rest else ''


def _fuzzy(token: str) -> str:
    """Replace a misspelled long term with its correct spelling, keeping the ending."""
    for base in FUZZY:
        if len(token) < len(base) - 1:
            continue
        # The misspelled stem can be a letter shorter or longer; keep what follows it.
        score, n = max((SequenceMatcher(None, token[:n], base).ratio(), n)
                       for n in (len(base) - 1, len(base), len(base) + 1))
        if score >= FUZZY_MIN:
            return base + token[n:]
    return token


# Malayalam fuses "all" onto the word before it: പായസം + എല്ലാം → പായസമെല്ലാം. Split it back so the
# glossary can see the word (else payasam dropped out and the translation said "all the dough").
_FUSED_ALL = re.compile(r'([\u0d00-\u0d7f]{2,})മെല്ലാം')


def protect(text: str) -> str:
    text = _FUSED_ALL.sub(r'\1ം എല്ലാം', text)
    text = _TOKEN.sub(lambda m: _fuzzy(m.group()), text)
    for pattern, name in _PATTERNS:
        text = pattern.sub(lambda m: name + _ending(m.group(1)), text)
    return text


_PLACE_PATTERNS = [(re.compile(f'(?<![\u0d00-\u0d7f]){stem}'), name) for stem, name in PLACES]


def places_in(malayalam: str) -> list[str]:
    """Known places she named, in the order she said them: the listing's "location".

    Read from the Malayalam (misspellings corrected), so translation can't garble them.
    """
    text = _TOKEN.sub(lambda m: _fuzzy(m.group()), malayalam)
    matches = sorted(((m.start(), m.end(), name) for pattern, name in _PLACE_PATTERNS for m in pattern.finditer(text)),
                     key=lambda x: (x[0], -x[1]))
    names, covered_to = [], -1
    for start, end, name in matches:
        if start < covered_to:  # "ബത്തേരി" inside "സുൽത്താൻ ബത്തേരി"
            continue
        names.append(name)
        covered_to = end
    return list(dict.fromkeys(names))
