// Builds a reply by combining fixed templates with the vendor's confirmed facts. No free generation.
import type { IntentId, Lang as GuestLang } from '../engine';
import type { Enquiry } from '../db';
import type { TourFacts } from './facts';
import { fmt, type Lang } from './format';
import { FRAME, REPLIES, type DraftCtx } from './templates';

const NO_ASKED = { vegetarian: false, kids: false, wheelchair: false, card: false };

export function draftCtx(e: Enquiry, facts: TourFacts): DraftCtx {
  return {
    facts,
    date: e.decision.date ? new Date(e.decision.date) : undefined,
    groupSize: e.decision.groupSize,
    open: e.decision.open,
    asked: e.asked ?? NO_ASKED,
  };
}

/** The vendor's own pick wins; otherwise what the engine was confident about. */
export function intentsFor(e: Enquiry): IntentId[] {
  return e.decision.intents ?? (e.understanding?.status === 'confident' ? e.understanding.accepted : []);
}

/** Language the guest gets the reply in. English when the engine couldn't tell. */
export function guestLang(e: Enquiry): GuestLang {
  const l = e.understanding?.lang;
  return l && l !== 'unknown' ? l : 'en';
}

/** Default yes/no: open if it's a tour day and the group fits. */
export function defaultOpen(date: Date | undefined, groupSize: number | undefined, facts: TourFacts): boolean | undefined {
  if (!date) return undefined;
  return facts.days.includes(date.getDay() as TourFacts['days'][number]) && (groupSize === undefined || groupSize <= facts.maxGroup);
}

export function composeReply(intents: IntentId[], ctx: DraftCtx, lang: Lang, opts: { callYou?: boolean } = {}): string {
  const frame = FRAME[lang];
  const f = fmt(lang);
  const c = { ...ctx, withBooking: intents.includes('booking') && !!ctx.date && !!ctx.open };
  const body = opts.callYou ? frame.callYou : intents.map((i) => REPLIES[i][lang](c, f)).join(' ');
  return [frame.hello, body, frame.signoff(ctx.facts.vendorName), frame.footer(ctx.facts.vendorName)].join('\n\n');
}
