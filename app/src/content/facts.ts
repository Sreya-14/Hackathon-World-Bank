// The vendor's tour facts: the only source a reply can draw from.
// Everything is a number, a weekday or a yes/no so every reply can be pre-translated.
// The two free-text fields (meeting point, map link) are inserted into replies as written.

export type Weekday = 0 | 1 | 2 | 3 | 4 | 5 | 6; // 0 = Sunday, as in Date.getDay()
export type Currency = 'INR' | 'EUR' | 'USD';
export const CURRENCIES: Currency[] = ['INR', 'EUR', 'USD'];

export interface TourFacts {
  vendorName: string; // signs every reply
  price: number; // per person
  currency: Currency;
  days: Weekday[];
  startTime: string; // "HH:MM"
  durationHours: number;
  maxGroup: number;
  meetingPoint: string; // a landmark name, e.g. "Cooperative office, Main Road"
  mapsLink: string;
  included: { coffeeTasting: boolean; lunch: boolean; guide: boolean; transport: boolean };
  vegetarian: boolean;
  kidsWelcome: boolean;
  wheelchair: boolean;
  payment: { cash: boolean; upi: boolean; card: boolean };
}

export const DEFAULT_FACTS: TourFacts = {
  vendorName: '',
  price: 0,
  currency: 'INR',
  days: [],
  startTime: '09:00',
  durationHours: 3,
  maxGroup: 8,
  meetingPoint: '',
  mapsLink: '',
  included: { coffeeTasting: true, lunch: false, guide: true, transport: false },
  vegetarian: true,
  kidsWelcome: true,
  wheelchair: false,
  payment: { cash: true, upi: true, card: false },
};

/** Fields a reply cannot be drafted without. Empty array = ready. */
export function missingFacts(f: TourFacts): (keyof TourFacts)[] {
  const missing: (keyof TourFacts)[] = [];
  if (!f.vendorName.trim()) missing.push('vendorName');
  if (!(f.price > 0)) missing.push('price');
  if (f.days.length === 0) missing.push('days');
  if (!/^\d{2}:\d{2}$/.test(f.startTime)) missing.push('startTime');
  if (!(f.durationHours > 0)) missing.push('durationHours');
  if (!f.meetingPoint.trim()) missing.push('meetingPoint');
  if (!Object.values(f.payment).some(Boolean)) missing.push('payment');
  return missing;
}
