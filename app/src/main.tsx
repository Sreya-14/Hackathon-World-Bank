import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { initialLang } from './i18n';
import './styles.css';

document.documentElement.lang = initialLang();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
