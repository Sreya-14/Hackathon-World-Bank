import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ingestShare } from './share';
import './styles.css';

// A share must be stored before the first render so the app opens straight on it.
ingestShare()
  .catch((err) => console.error('share ingest failed', err))
  .finally(() => {
    createRoot(document.getElementById('root')!).render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
  });
