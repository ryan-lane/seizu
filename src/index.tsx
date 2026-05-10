import createCache from '@emotion/cache';
import { CacheProvider } from '@emotion/react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { TssCacheProvider } from 'tss-react';
import App from './App';
import { getCspNonce, preinjectReactDraggableStyle } from './cspNonce';

const cspNonce = getCspNonce();
preinjectReactDraggableStyle(cspNonce);

const container = document.getElementById('root') as HTMLElement;
const root = createRoot(container);
const emotionCache = createCache({
  key: 'mui',
  nonce: cspNonce
});
// tss-react (used internally by mui-datatables) creates its own emotion cache
// by default, which doesn't carry the CSP nonce. Provide our own nonce'd cache
// so its <style> tags satisfy `style-src 'self' 'nonce-...'`.
const tssCache = createCache({
  key: 'tss',
  nonce: cspNonce
});

root.render(
  <CacheProvider value={emotionCache}>
    <TssCacheProvider value={tssCache}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </TssCacheProvider>
  </CacheProvider>
);
