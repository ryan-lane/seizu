import createCache from '@emotion/cache';
import { CacheProvider } from '@emotion/react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';

function getCspNonce(): string | undefined {
  const nonceMeta = document.querySelector('meta[property="csp-nonce"]');
  return nonceMeta?.getAttribute('content') ?? undefined;
}

const container = document.getElementById('root') as HTMLElement;
const root = createRoot(container);
const emotionCache = createCache({
  key: 'mui',
  nonce: getCspNonce()
});

root.render(
  <CacheProvider value={emotionCache}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </CacheProvider>
);
