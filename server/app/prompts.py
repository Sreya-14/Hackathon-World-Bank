"""Bot prompts in the vendor's language (Malayalam), each with an English gloss.

Each prompt is sent as text plus a short MMS-TTS audio clip. The Malayalam was drafted
with AI help: have a fluent speaker check it before the demo.
"""
from __future__ import annotations

PROMPTS: dict[str, tuple[str, str]] = {
    "welcome": (
        "നമസ്കാരം! ലാന്റേണിലേക്ക് സ്വാഗതം. നിങ്ങളുടെ ടൂറിന്റെയോ ഉൽപ്പന്നത്തിന്റെയോ ഒരു ഫോട്ടോയും, അതിനെക്കുറിച്ച് ഒരു വോയ്‌സ് നോട്ടും അയയ്ക്കുക. "
        "നിങ്ങൾ പറയുന്നതിൽ നിന്ന് ഞങ്ങൾ ഒരു ലിസ്റ്റിംഗ് ഉണ്ടാക്കും. നിങ്ങൾ അംഗീകരിച്ചാൽ മാത്രമേ അത് ടൂറിസ്റ്റുകളുടെ മാപ്പിൽ കാണിക്കൂ. "
        "ഒരു ടൂറിസ്റ്റ് ബന്ധപ്പെടാൻ ടാപ്പ് ചെയ്യുമ്പോൾ മാത്രമേ നിങ്ങളുടെ ഫോൺ നമ്പർ കാണിക്കൂ. എപ്പോൾ വേണമെങ്കിലും ❌ അയച്ച് ലിസ്റ്റിംഗ് മറയ്ക്കാം.",
        "Hello! Welcome to Lantern. Send a photo of your tour or product and a voice note about it. "
        "We'll make a listing from what you say; it appears on the tourist map only after you approve it. "
        "Your phone number is shown only when a tourist taps to contact you. Send ❌ any time to hide your listing.",
    ),
    "need_photo": ("നന്ദി! ഇനി ഒരു ഫോട്ടോ കൂടി അയയ്ക്കുക.", "Thanks! Now please send a photo too."),
    "need_voice": ("നന്ദി! ഇനി നിങ്ങളുടെ ടൂറിനെക്കുറിച്ച് ഒരു വോയ്‌സ് നോട്ട് അയയ്ക്കുക.", "Thanks! Now send a voice note about your tour."),
    "processing": (
        "നന്ദി! ഞാൻ നിങ്ങളുടെ ലിസ്റ്റിംഗ് തയ്യാറാക്കുകയാണ്. ഒന്നോ രണ്ടോ മിനിറ്റ് എടുത്തേക്കാം.",
        "Thanks! I'm preparing your listing. It can take a minute or two.",
    ),
    "still_processing": ("ഇപ്പോഴും തയ്യാറാക്കുകയാണ്, ഒരു നിമിഷം.", "Still working on it, one moment."),
    "retake_blurry": ("ഫോട്ടോ വ്യക്തമല്ല. ദയവായി ഒന്നുകൂടി എടുത്ത് അയയ്ക്കുക.", "The photo isn't clear. Please take it again and send it."),
    "retake_dark": ("ഫോട്ടോ വളരെ ഇരുണ്ടതാണ്. വെളിച്ചത്തിൽ ഒന്നുകൂടി എടുത്ത് അയയ്ക്കുക.", "The photo is too dark. Please retake it in better light."),
    "retake_unreadable": ("ഫോട്ടോ തുറക്കാൻ കഴിഞ്ഞില്ല. ദയവായി വീണ്ടും അയയ്ക്കുക.", "I couldn't open the photo. Please send it again."),
    "not_sure": (
        "എനിക്ക് ശരിയായി മനസ്സിലായെന്ന് ഉറപ്പില്ല. ദയവായി ഒന്നുകൂടി പറഞ്ഞ് പുതിയ വോയ്‌സ് നോട്ട് അയയ്ക്കാമോ? ഒരു പങ്കാളിക്കും ഇത് പരിശോധിക്കാം.",
        "I'm not sure I understood. Could you say it again in a new voice note? A partner can also check it.",
    ),
    "approved_need_location": (
        "നന്ദി! ഇനി നിങ്ങളുടെ ലൊക്കേഷൻ അയയ്ക്കുക. വാട്ട്‌സ്ആപ്പിൽ 📎 അമർത്തി ലൊക്കേഷൻ തിരഞ്ഞെടുക്കുക.",
        "Thank you! Now send your location (in WhatsApp: tap 📎, then Location).",
    ),
    "need_location": ("ദയവായി നിങ്ങളുടെ ലൊക്കേഷൻ അയയ്ക്കുക.", "Please send your location."),
    "privacy_choice": (
        "ടൂറിസ്റ്റുകൾ നിങ്ങളെ എത്ര കൃത്യമായി കാണണം? 1 അയച്ചാൽ കൃത്യമായ സ്ഥലം. 2 അയച്ചാൽ ഏകദേശ പ്രദേശം മാത്രം. 3 അയച്ചാൽ ഒരു കൂടിക്കാഴ്ച സ്ഥലം.",
        "How exactly should tourists see you? Send 1 for the exact spot, 2 for a rough area only, 3 for a meeting point.",
    ),
    "need_meeting_point": ("ശരി. കൂടിക്കാഴ്ച സ്ഥലത്തിന്റെ ലൊക്കേഷൻ അയയ്ക്കുക.", "OK. Send the location of the meeting point."),
    "live": (
        "നിങ്ങളുടെ ലിസ്റ്റിംഗ് ഇപ്പോൾ മാപ്പിൽ ഉണ്ട്! ദിവസവും 📍 അയച്ചാൽ നിങ്ങൾ ഇന്ന് ലഭ്യമാണെന്ന് ടൂറിസ്റ്റുകൾ അറിയും. മറയ്ക്കാൻ ❌ അയയ്ക്കുക.",
        "Your listing is now on the map! Send 📍 each day so tourists know you're available. Send ❌ to hide it.",
    ),
    "checkin": ("നന്ദി, ഇന്നത്തെ ചെക്ക്-ഇൻ രേഖപ്പെടുത്തി.", "Thanks, today's check-in is recorded."),
    "hidden": ("നിങ്ങളുടെ ലിസ്റ്റിംഗ് മറച്ചു. വീണ്ടും കാണിക്കാൻ 👍 അയയ്ക്കുക.", "Your listing is hidden. Send 👍 to show it again."),
    "shown_again": ("നിങ്ങളുടെ ലിസ്റ്റിംഗ് വീണ്ടും മാപ്പിൽ ഉണ്ട്.", "Your listing is back on the map."),
    "rerecord": ("ശരി. പുതിയ ഒരു വോയ്‌സ് നോട്ട് അയയ്ക്കുക.", "OK. Send a new voice note."),
    "approve_hint": ("ശരിയാണെങ്കിൽ 👍 അയയ്ക്കുക. മാറ്റാൻ 🔁 അല്ലെങ്കിൽ പുതിയ വോയ്‌സ് നോട്ട് അയയ്ക്കുക.", "If it's right, send 👍. To change it, send 🔁 or a new voice note."),
    "privacy_hint": ("ദയവായി 1, 2 അല്ലെങ്കിൽ 3 അയയ്ക്കുക.", "Please send 1, 2 or 3."),
    "update_received": ("പുതിയ വിവരങ്ങൾക്ക് നന്ദി. ലിസ്റ്റിംഗ് പുതുക്കുകയാണ്.", "Thanks for the update. I'm refreshing your listing."),
    "restart": ("ശരി, നമുക്ക് വീണ്ടും തുടങ്ങാം.", "OK, let's start again."),
}


def ml(key: str) -> str:
    return PROMPTS[key][0]


def en(key: str) -> str:
    return PROMPTS[key][1]
