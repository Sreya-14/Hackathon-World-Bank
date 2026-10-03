"""Protect Kerala place names from translation.

NLLB reads മൂന്നാറിൽ ("in Munnar") as മൂന്ന് ("three") and writes "a three-hour tour";
തേക്കടിയിൽ became "from the base". Replacing the name with its English spelling before
translation (മൂന്നാറിൽ → "Munnar-ൽ") makes NLLB copy it through. Malayalam inflects
the name itself, so each stem lists its forms before a case ending, longest first (ട്ട before ട്).
"""
from __future__ import annotations

import re

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

_MARKS = r'[\u0d3e-\u0d4d\u0d57\u0d62\u0d63]'  # vowel signs and virama
_PATTERNS = [(re.compile(f'{stem}([\u0d00-\u0d7f]*)'), name) for stem, name in PLACES]


def _ending(rest: str) -> str:
    """Case ending to keep after the English name: drop glides and dangling vowel signs (യിൽ → ൽ)."""
    rest = re.sub(f'^[യവ]?{_MARKS}*', '', rest)
    return f'-{rest}' if rest else ''


def protect(text: str) -> str:
    for pattern, name in _PATTERNS:
        text = pattern.sub(lambda m: name + _ending(m.group(1)), text)
    return text
