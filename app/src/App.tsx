// Owned by the App track. Placeholder that proves the engine contract end to end.
import { useState } from 'react';
import { getEngine, type Understanding } from './engine';

export default function App() {
  const [text, setText] = useState('Can 4 of us come Friday 10am? How much is it?');
  const [result, setResult] = useState<Understanding | null>(null);

  async function run() {
    const engine = getEngine();
    if (!engine.ready().core) await engine.loadCore();
    setResult(await engine.understand(text));
  }

  return (
    <main style={{ padding: 16, fontFamily: 'system-ui' }}>
      <h1>Noor</h1>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} style={{ width: '100%' }} />
      <button onClick={run}>Understand</button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </main>
  );
}
