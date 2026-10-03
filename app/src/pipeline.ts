// Runs new enquiries through the engine and the rules, one at a time.
import { getEngine } from './engine';
import { db, getFacts } from './db';
import { defaultOpen } from './content/draft';
import { parseAsked, parseDate, parseGroupSize } from './rules/parse';

let chain: Promise<void> = Promise.resolve();

export function processPending(): Promise<void> {
  chain = chain.then(run).catch((err) => console.error('processPending failed', err));
  return chain;
}

async function run() {
  const engine = getEngine();
  if (!engine.ready().core) return;
  const facts = await getFacts();
  const pending = await db.enquiries.where('status').equals('new').toArray();

  for (const e of pending) {
    const u = await engine.understand(e.text);
    const date = parseDate(e.text, u.lang, u.english);
    const groupSize = parseGroupSize(e.text, u.english);
    await db.enquiries.update(e.id!, {
      understanding: u,
      asked: parseAsked(e.text, u.english),
      decision: { date: date?.getTime(), groupSize, open: defaultOpen(date, groupSize, facts) },
      status: 'ready',
    });
  }
}
