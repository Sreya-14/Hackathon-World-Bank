// Owned by the App track. Placeholder that proves the engine contract end to end.
import { useState } from 'react';
import { getEngine, type OperatorLang, type Understanding } from './engine';

export default function App() {
  const [text, setText] = useState('Can 4 of us come Friday 10am? How much is it?');
  const [to, setTo] = useState<OperatorLang>('ml');
  const [result, setResult] = useState<Understanding | null>(null);

  async function run() {
    const engine = getEngine();
    if (!engine.ready().core) await engine.loadCore();
    setResult(await engine.understand(text, to));
  }

  return (
    <main style={{ padding: 16, fontFamily: 'system-ui' }}>
      <h1>Tour Assistant</h1>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} style={{ width: '100%' }} />
      <select value={to} onChange={(e) => setTo(e.target.value as OperatorLang)}>
        <option value="ml">Malayalam</option>
        <option value="ta">Tamil</option>
      </select>
      <button onClick={run}>Understand</button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </main>
  );
}
