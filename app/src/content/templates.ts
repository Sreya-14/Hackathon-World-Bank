// Fixed reply templates: the ONLY things the tool can say to a guest.
// The guest gets their language; the vendor previews the same reply in theirs before approving.
// STATUS: drafted with AI help. Each language must be checked by a fluent speaker
// before the demo. Flip CHECKED when that is done.
import type { IntentId } from '../engine';
import type { TourFacts } from './facts';
import type { Fmt, Lang } from './format';

export const CHECKED: Record<Lang, boolean> = { en: true, de: false, ml: false, ta: false };

export interface Asked {
  vegetarian: boolean;
  kids: boolean;
  wheelchair: boolean;
  card: boolean;
}

export interface DraftCtx {
  facts: TourFacts;
  date?: Date;
  groupSize?: number;
  /** Vendor's yes/no for availability and booking. */
  open?: boolean;
  asked: Asked;
  /** Set by composeReply: the booking part already states the group total. */
  withBooking?: boolean;
}

type Part = (c: DraftCtx, f: Fmt) => string;

const total = (c: DraftCtx, f: Fmt) => f.money(c.facts.price * (c.groupSize ?? 0), c.facts.currency);
const price = (c: DraftCtx, f: Fmt) => f.money(c.facts.price, c.facts.currency);

const INCLUDED: Record<keyof TourFacts['included'], Record<Lang, string>> = {
  coffeeTasting: { en: 'coffee tasting', de: 'eine Kaffeeverkostung', ml: 'കാപ്പി രുചിക്കൽ', ta: 'காபி சுவைத்தல்' },
  lunch: { en: 'lunch', de: 'Mittagessen', ml: 'ഉച്ചഭക്ഷണം', ta: 'மதிய உணவு' },
  guide: { en: 'a local guide', de: 'einen lokalen Guide', ml: 'പ്രാദേശിക ഗൈഡ്', ta: 'உள்ளூர் வழிகாட்டி' },
  transport: { en: 'transport', de: 'den Transport', ml: 'യാത്രാസൗകര്യം', ta: 'போக்குவரத்து' },
};

const PAYMENT: Record<keyof TourFacts['payment'], Record<Lang, string>> = {
  cash: { en: 'cash', de: 'bar', ml: 'ക്യാഷ്', ta: 'ரொக்கம்' },
  upi: { en: 'UPI', de: 'per UPI', ml: 'UPI', ta: 'UPI' },
  card: { en: 'card', de: 'mit Karte', ml: 'കാർഡ്', ta: 'கார்டு' },
};

const includedList = (c: DraftCtx, f: Fmt, lang: Lang) =>
  f.and((Object.keys(INCLUDED) as (keyof typeof INCLUDED)[]).filter((k) => c.facts.included[k]).map((k) => INCLUDED[k][lang]));
const paymentList = (c: DraftCtx, f: Fmt, lang: Lang) =>
  f.or((Object.keys(PAYMENT) as (keyof typeof PAYMENT)[]).filter((k) => c.facts.payment[k]).map((k) => PAYMENT[k][lang]));
const anyIncluded = (c: DraftCtx) => Object.values(c.facts.included).some(Boolean);
const refusesCard = (c: DraftCtx) => c.asked.card && !c.facts.payment.card;
/** If the guest asked nothing specific, answer all three. */
const topics = (a: Asked) => (a.vegetarian || a.kids || a.wheelchair ? a : { ...a, vegetarian: true, kids: true, wheelchair: true });

/** [yes, no] sentence pairs for the dietary / kids / access answers. */
const DIETARY: Record<'vegetarian' | 'kids' | 'wheelchair', Record<Lang, [string, string]>> = {
  vegetarian: {
    en: ['Yes, we can offer vegetarian food.', 'Sorry, we cannot offer vegetarian food.'],
    de: ['Ja, wir können vegetarisches Essen anbieten.', 'Leider können wir kein vegetarisches Essen anbieten.'],
    ml: ['അതെ, വെജിറ്റേറിയൻ ഭക്ഷണം ലഭ്യമാണ്.', 'ക്ഷമിക്കണം, വെജിറ്റേറിയൻ ഭക്ഷണം ലഭ്യമല്ല.'],
    ta: ['ஆம், சைவ உணவு கிடைக்கும்.', 'மன்னிக்கவும், சைவ உணவு கிடைக்காது.'],
  },
  kids: {
    en: ['Children are welcome.', 'Sorry, the tour is not suitable for children.'],
    de: ['Kinder sind herzlich willkommen.', 'Leider ist die Tour nicht für Kinder geeignet.'],
    ml: ['കുട്ടികൾക്ക് സ്വാഗതം.', 'ക്ഷമിക്കണം, ഈ ടൂർ കുട്ടികൾക്ക് അനുയോജ്യമല്ല.'],
    ta: ['குழந்தைகளுக்கு வரவேற்பு.', 'மன்னிக்கவும், இந்தச் சுற்றுலா குழந்தைகளுக்கு ஏற்றதல்ல.'],
  },
  wheelchair: {
    en: ['The tour is wheelchair accessible.', 'Sorry, the tour is not wheelchair accessible.'],
    de: ['Die Tour ist rollstuhlgerecht.', 'Leider ist die Tour nicht rollstuhlgerecht.'],
    ml: ['ടൂർ വീൽചെയറിന് അനുയോജ്യമാണ്.', 'ക്ഷമിക്കണം, ടൂർ വീൽചെയറിന് അനുയോജ്യമല്ല.'],
    ta: ['இந்தச் சுற்றுலா சக்கர நாற்காலிக்கு ஏற்றது.', 'மன்னிக்கவும், இந்தச் சுற்றுலா சக்கர நாற்காலிக்கு ஏற்றதல்ல.'],
  },
};

const dietary = (lang: Lang): Part => (c) => {
  const t = topics(c.asked);
  const yes = { vegetarian: c.facts.vegetarian, kids: c.facts.kidsWelcome, wheelchair: c.facts.wheelchair };
  return (['vegetarian', 'kids', 'wheelchair'] as const)
    .filter((k) => t[k])
    .map((k) => DIETARY[k][lang][yes[k] ? 0 : 1])
    .join(' ');
};

export const REPLIES: Record<IntentId, Record<Lang, Part>> = {
  price: {
    en: (c, f) => `Our farm tour costs ${price(c, f)} per person.` + (c.groupSize && !c.withBooking ? ` For ${c.groupSize} people that is ${total(c, f)}.` : ''),
    de: (c, f) => `Unsere Farmtour kostet ${price(c, f)} pro Person.` + (c.groupSize && !c.withBooking ? ` Für ${c.groupSize} Personen sind das ${total(c, f)}.` : ''),
    ml: (c, f) => `ഞങ്ങളുടെ ഫാം ടൂറിന് ഒരാൾക്ക് ${price(c, f)} ആണ്.` + (c.groupSize && !c.withBooking ? ` ${c.groupSize} പേർക്ക് ആകെ ${total(c, f)}.` : ''),
    ta: (c, f) => `எங்கள் பண்ணைச் சுற்றுலாவுக்கு ஒருவருக்கு ${price(c, f)}.` + (c.groupSize && !c.withBooking ? ` ${c.groupSize} பேருக்கு மொத்தம் ${total(c, f)}.` : ''),
  },

  availability: {
    en: (c, f) =>
      !c.date ? `We run tours on ${f.weekdays(c.facts.days)}, starting at ${c.facts.startTime}.`
      : c.open ? `Yes, we are open on ${f.date(c.date)}. The tour starts at ${c.facts.startTime}.`
      : `Sorry, we are not available on ${f.date(c.date)}. We run tours on ${f.weekdays(c.facts.days)}.`,
    de: (c, f) =>
      !c.date ? `Unsere Touren finden an folgenden Tagen statt: ${f.weekdays(c.facts.days)}, ab ${c.facts.startTime} Uhr.`
      : c.open ? `Ja, am ${f.date(c.date)} haben wir geöffnet. Die Tour beginnt um ${c.facts.startTime} Uhr.`
      : `Leider sind wir am ${f.date(c.date)} nicht verfügbar. Unsere Touren finden an folgenden Tagen statt: ${f.weekdays(c.facts.days)}.`,
    ml: (c, f) =>
      !c.date ? `ടൂർ ദിവസങ്ങൾ: ${f.weekdays(c.facts.days)}. ${c.facts.startTime}-ന് തുടങ്ങും.`
      : c.open ? `അതെ, ${f.date(c.date)} ടൂർ ഉണ്ട്. ${c.facts.startTime}-ന് തുടങ്ങും.`
      : `ക്ഷമിക്കണം, ${f.date(c.date)} ടൂർ ഇല്ല. ടൂർ ദിവസങ്ങൾ: ${f.weekdays(c.facts.days)}.`,
    ta: (c, f) =>
      !c.date ? `சுற்றுலா நாட்கள்: ${f.weekdays(c.facts.days)}. ${c.facts.startTime} மணிக்குத் தொடங்கும்.`
      : c.open ? `ஆம், ${f.date(c.date)} அன்று சுற்றுலா உண்டு. ${c.facts.startTime} மணிக்குத் தொடங்கும்.`
      : `மன்னிக்கவும், ${f.date(c.date)} அன்று சுற்றுலா இல்லை. சுற்றுலா நாட்கள்: ${f.weekdays(c.facts.days)}.`,
  },

  booking: {
    en: (c, f) =>
      !c.date ? `Which day would you like to come? We run tours on ${f.weekdays(c.facts.days)}.`
      : c.open ? `Your booking is confirmed ${c.groupSize ? `for ${c.groupSize} people` : 'for your group'} on ${f.date(c.date)} at ${c.facts.startTime}.` + (c.groupSize ? ` Total: ${total(c, f)}.` : '')
      : `Sorry, we cannot take this booking on ${f.date(c.date)}. We run tours on ${f.weekdays(c.facts.days)}. Please suggest another day.`,
    de: (c, f) =>
      !c.date ? `An welchem Tag möchten Sie kommen? Unsere Touren finden an folgenden Tagen statt: ${f.weekdays(c.facts.days)}.`
      : c.open ? `Ihre Buchung ist bestätigt: ${c.groupSize ? `${c.groupSize} Personen` : 'Ihre Gruppe'} am ${f.date(c.date)} um ${c.facts.startTime} Uhr.` + (c.groupSize ? ` Gesamtpreis: ${total(c, f)}.` : '')
      : `Leider können wir diese Buchung am ${f.date(c.date)} nicht annehmen. Unsere Touren finden an folgenden Tagen statt: ${f.weekdays(c.facts.days)}. Bitte nennen Sie uns einen anderen Tag.`,
    ml: (c, f) =>
      !c.date ? `ഏത് ദിവസമാണ് നിങ്ങൾ വരാൻ ആഗ്രഹിക്കുന്നത്? ടൂർ ദിവസങ്ങൾ: ${f.weekdays(c.facts.days)}.`
      : c.open ? `നിങ്ങളുടെ ബുക്കിംഗ് സ്ഥിരീകരിച്ചു: ${c.groupSize ? `${c.groupSize} പേർ` : 'നിങ്ങളുടെ സംഘം'}, ${f.date(c.date)}, ${c.facts.startTime}.` + (c.groupSize ? ` ആകെ: ${total(c, f)}.` : '')
      : `ക്ഷമിക്കണം, ${f.date(c.date)} ബുക്കിംഗ് സ്വീകരിക്കാൻ കഴിയില്ല. ടൂർ ദിവസങ്ങൾ: ${f.weekdays(c.facts.days)}. ദയവായി മറ്റൊരു ദിവസം അറിയിക്കൂ.`,
    ta: (c, f) =>
      !c.date ? `நீங்கள் எந்த நாளில் வர விரும்புகிறீர்கள்? சுற்றுலா நாட்கள்: ${f.weekdays(c.facts.days)}.`
      : c.open ? `உங்கள் முன்பதிவு உறுதி செய்யப்பட்டது: ${c.groupSize ? `${c.groupSize} பேர்` : 'உங்கள் குழு'}, ${f.date(c.date)}, ${c.facts.startTime}.` + (c.groupSize ? ` மொத்தம்: ${total(c, f)}.` : '')
      : `மன்னிக்கவும், ${f.date(c.date)} அன்று முன்பதிவை ஏற்க முடியாது. சுற்றுலா நாட்கள்: ${f.weekdays(c.facts.days)}. தயவுசெய்து வேறு ஒரு நாளைத் தெரிவிக்கவும்.`,
  },

  directions: {
    en: (c) => `We meet at ${c.facts.meetingPoint}.` + (c.facts.mapsLink ? ` Map: ${c.facts.mapsLink}` : ''),
    de: (c) => `Treffpunkt: ${c.facts.meetingPoint}.` + (c.facts.mapsLink ? ` Karte: ${c.facts.mapsLink}` : ''),
    ml: (c) => `കൂടിക്കാഴ്ച സ്ഥലം: ${c.facts.meetingPoint}.` + (c.facts.mapsLink ? ` മാപ്പ്: ${c.facts.mapsLink}` : ''),
    ta: (c) => `சந்திப்பு இடம்: ${c.facts.meetingPoint}.` + (c.facts.mapsLink ? ` வரைபடம்: ${c.facts.mapsLink}` : ''),
  },

  included: {
    en: (c, f) => `The tour lasts about ${f.num(c.facts.durationHours)} hours` + (anyIncluded(c) ? ` and includes ${includedList(c, f, 'en')}.` : '.'),
    de: (c, f) => `Die Tour dauert etwa ${f.num(c.facts.durationHours)} Stunden` + (anyIncluded(c) ? ` und beinhaltet ${includedList(c, f, 'de')}.` : '.'),
    ml: (c, f) => `ടൂർ ഏകദേശം ${f.num(c.facts.durationHours)} മണിക്കൂർ നീളും.` + (anyIncluded(c) ? ` ഇതിൽ ${includedList(c, f, 'ml')} ഉൾപ്പെടുന്നു.` : ''),
    ta: (c, f) => `சுற்றுலா சுமார் ${f.num(c.facts.durationHours)} மணி நேரம் நடக்கும்.` + (anyIncluded(c) ? ` இதில் ${includedList(c, f, 'ta')} அடங்கும்.` : ''),
  },

  dietary_kids_access: { en: dietary('en'), de: dietary('de'), ml: dietary('ml'), ta: dietary('ta') },

  payment: {
    en: (c, f) => `You can pay by ${paymentList(c, f, 'en')}.` + (refusesCard(c) ? ' We cannot accept cards.' : ''),
    de: (c, f) => `Sie können ${paymentList(c, f, 'de')} bezahlen.` + (refusesCard(c) ? ' Kartenzahlung ist leider nicht möglich.' : ''),
    ml: (c, f) => `${paymentList(c, f, 'ml')} വഴി പണമടയ്ക്കാം.` + (refusesCard(c) ? ' കാർഡ് സ്വീകരിക്കുന്നില്ല.' : ''),
    ta: (c, f) => `${paymentList(c, f, 'ta')} மூலம் பணம் செலுத்தலாம்.` + (refusesCard(c) ? ' கார்டு ஏற்றுக்கொள்ளப்படாது.' : ''),
  },
};

export const FRAME: Record<Lang, { hello: string; callYou: string; signoff: (vendor: string) => string; footer: (vendor: string) => string }> = {
  en: {
    hello: 'Hello, thank you for your message!',
    callYou: 'I will call you soon to answer your question.',
    signoff: (v) => `Best wishes, ${v}`,
    footer: (v) => `(This reply was prepared with a translation tool and approved by ${v}.)`,
  },
  de: {
    hello: 'Hallo, vielen Dank für Ihre Nachricht!',
    callYou: 'Ich rufe Sie bald an, um Ihre Frage zu beantworten.',
    signoff: (v) => `Viele Grüße, ${v}`,
    footer: (v) => `(Diese Antwort wurde mit einem Übersetzungstool erstellt und von ${v} freigegeben.)`,
  },
  ml: {
    hello: 'നമസ്കാരം, നിങ്ങളുടെ സന്ദേശത്തിന് നന്ദി!',
    callYou: 'നിങ്ങളുടെ ചോദ്യത്തിന് മറുപടി നൽകാൻ ഞാൻ ഉടൻ വിളിക്കാം.',
    signoff: (v) => `ആശംസകളോടെ, ${v}`,
    footer: (v) => `(ഈ മറുപടി ഒരു വിവർത്തന ഉപകരണം ഉപയോഗിച്ച് തയ്യാറാക്കി ${v} അംഗീകരിച്ചതാണ്.)`,
  },
  ta: {
    hello: 'வணக்கம், உங்கள் செய்திக்கு நன்றி!',
    callYou: 'உங்கள் கேள்விக்குப் பதிலளிக்க விரைவில் அழைக்கிறேன்.',
    signoff: (v) => `அன்புடன், ${v}`,
    footer: (v) => `(இந்தப் பதில் மொழிபெயர்ப்புக் கருவியின் உதவியுடன் தயாரிக்கப்பட்டு ${v} அவர்களால் அங்கீகரிக்கப்பட்டது.)`,
  },
};
