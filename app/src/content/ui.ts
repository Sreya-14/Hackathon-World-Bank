// Interface text. The app is English everywhere; only guest messages and replies change language.
import type { IntentId, Lang, NotSureReason } from '../engine';
import type { DraftCtx } from './templates';
import { fmt } from './format';

const STRINGS = {
  appName: 'Tour Assistant',
  preparing: 'Preparing… one time only',
  messages: 'Messages',
  outbox: 'Outbox',
  bookings: 'Bookings',
  admin: 'Admin',
  pastePlaceholder: "Paste the guest's message here",
  add: 'Add',
  noMessages: 'No messages yet. Share one from WhatsApp or SMS.',
  setupFirst: 'Set up your tour details in Admin first',
  understanding: 'Reading the message…',
  replied: 'Replied',
  notSure: 'Not sure',
  pleaseDecide: 'Please decide yourself',
  machineTranslated: 'Machine translation, may be wrong',
  original: 'Original message',
  guestAsks: 'The guest asks',
  yourReply: 'Your reply',
  guestWillGet: 'The guest will receive',
  approve: 'Approve reply',
  dismiss: 'Dismiss',
  callYouInstead: 'Reply: "I will call you"',
  pickTopic: 'Or choose the question yourself:',
  date: 'Date',
  people: 'People',
  yesOpen: 'Yes, accept',
  noClosed: 'No, decline',
  notTourDay: 'This is not one of your tour days',
  overMax: 'Group is larger than your maximum',
  guestPhone: "Guest's phone number (optional)",
  sendVia: 'Send via',
  offlineQueued: 'No signal. It will be sent when you have signal.',
  openWhatsApp: 'Open WhatsApp',
  openSms: 'Open SMS',
  markSent: 'I sent it',
  outboxEmpty: 'Nothing waiting to send',
  sent: 'Sent',
  noBookings: 'No bookings yet',
  upcoming: 'Upcoming',
  past: 'Past',
  save: 'Save',
  saved: 'Saved',
  back: 'Back',

  // Admin
  guestLanguages: 'Guest languages',
  guestLanguagesNote:
    'Guests can write in these languages and get replies in the same language. Messages in any other language are marked "not sure".',
  tourDetails: 'Tour details',
  adminPin: 'Admin PIN',
  enterPin: 'Enter admin PIN',
  unlock: 'Unlock',
  wrongPin: 'Wrong PIN',
  setPin: 'Set a new PIN (4+ digits)',
  noPinYet: 'No PIN set. Anyone with this phone can change these settings.',
  lock: 'Lock',
  yourData: 'Your data',
  dataOnPhone: 'All data stays on this phone. Nothing is sent to a server.',
  exportData: 'Export all data',
  wipeData: 'Delete all data',
  wipeConfirm: 'Delete all messages, bookings and settings from this phone? This cannot be undone.',

  // Tour details form
  vendorName: 'Business name (signs every reply)',
  price: 'Price per person',
  days: 'Tour days',
  startTime: 'Start time',
  duration: 'Length (hours)',
  maxGroup: 'Maximum group',
  meetingPoint: 'Meeting point (a landmark name, sent to guests as written)',
  mapsLink: 'Map link (optional)',
  included: 'Included',
  coffeeTasting: 'Coffee tasting',
  lunch: 'Lunch',
  guide: 'Guide',
  transport: 'Transport',
  canOffer: 'Can you offer?',
  vegetarian: 'Vegetarian food',
  kids: 'Children welcome',
  wheelchair: 'Wheelchair access',
  payment: 'Payment',
  cash: 'Cash',
  upi: 'UPI',
  card: 'Card',
} as const;

export type StringKey = keyof typeof STRINGS;
export const t = (k: StringKey): string => STRINGS[k];

export const INTENT_UI: Record<IntentId, { icon: string; label: string }> = {
  price: { icon: '💰', label: 'Price' },
  availability: { icon: '📅', label: 'Open days' },
  booking: { icon: '📝', label: 'Booking' },
  directions: { icon: '📍', label: 'Directions' },
  included: { icon: '☕', label: "What's included" },
  dietary_kids_access: { icon: '🥗', label: 'Food, kids, access' },
  payment: { icon: '💳', label: 'Payment' },
};

export const NOT_SURE_UI: Record<NotSureReason, string> = {
  low_confidence: "I'm not sure what the guest is asking.",
  mixed_intents: 'The message asks too many different things.',
  unsupported_language: "This language isn't supported yet.",
};

export const LANG_NAME: Record<Lang | 'unknown', string> = {
  en: 'English',
  de: 'German',
  ml: 'Malayalam',
  ta: 'Tamil',
  unknown: 'Unknown language',
};

/** One short sentence per intent for the vendor. Fixed text, not machine translation. */
export function summary(intent: IntentId, c: Pick<DraftCtx, 'date' | 'groupSize' | 'asked'>): string {
  const f = fmt('en');
  const day = c.date ? f.date(c.date) : '';
  const n = c.groupSize;
  const topics = [
    c.asked.vegetarian && 'vegetarian food',
    c.asked.kids && 'children',
    c.asked.wheelchair && 'wheelchair access',
  ].filter((x): x is string => !!x);

  switch (intent) {
    case 'price':
      return 'The guest asks the price of the tour.';
    case 'availability':
      return day ? `The guest asks if you are open on ${day}.` : 'The guest asks which days you run tours.';
    case 'booking':
      return `The guest wants to book${n ? ` for ${n} people` : ''}${day ? ` on ${day}` : ''}.`;
    case 'directions':
      return 'The guest asks how to find you.';
    case 'included':
      return "The guest asks what's included and how long it takes.";
    case 'dietary_kids_access':
      return topics.length ? `The guest asks about ${f.and(topics)}.` : 'The guest asks about food, children or access.';
    case 'payment':
      return 'The guest asks how to pay.';
  }
}
