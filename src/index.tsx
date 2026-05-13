import createCache from '@emotion/cache';
import { CacheProvider } from '@emotion/react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { getCspNonce, installStyleNoncePatch, preinjectReactDraggableStyle } from './cspNonce';

const cspNonce = getCspNonce();
installStyleNoncePatch(cspNonce);
preinjectReactDraggableStyle(cspNonce);

const container = document.getElementById('root') as HTMLElement;
const root = createRoot(container);
const emotionCache = createCache({
  key: 'mui',
  nonce: cspNonce
});

root.render(
  <CacheProvider value={emotionCache}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </CacheProvider>
);
