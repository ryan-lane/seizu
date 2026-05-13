// Read the per-request CSP nonce that the backend injected into the served
// HTML's `<meta property="csp-nonce">` tag. Pass this to libraries that
// inject their own <style> elements at runtime (emotion cache, Tiptap editor,
// etc.) so their tags satisfy `style-src 'self' 'nonce-...'`.
export function getCspNonce(): string | undefined {
  const nonceMeta = document.querySelector('meta[property="csp-nonce"]');
  return nonceMeta?.getAttribute('content') ?? undefined;
}

const STYLE_NONCE_PATCHED_KEY = '__seizuStyleNoncePatched';

// Some component libraries create <style> tags directly instead of going
// through Emotion's cache. Stamp the backend-provided nonce onto those tags at
// creation time so the app can keep a nonce-only style-src CSP.
export function installStyleNoncePatch(nonce: string | undefined): void {
  if (typeof document === 'undefined' || !nonce) return;
  const patchedDocument = document as Document & { [STYLE_NONCE_PATCHED_KEY]?: boolean };
  if (patchedDocument[STYLE_NONCE_PATCHED_KEY]) return;

  const originalCreateElement = document.createElement.bind(document);
  document.createElement = ((tagName: string, options?: ElementCreationOptions) => {
    const element = originalCreateElement(tagName, options);
    if (tagName.toLowerCase() === 'style' && !element.getAttribute('nonce')) {
      element.setAttribute('nonce', nonce);
    }
    return element;
  }) as typeof document.createElement;

  patchedDocument[STYLE_NONCE_PATCHED_KEY] = true;
}

// react-draggable injects an unnonced <style> element on first drag for its
// transparent-selection helper. It identifies that element by id and skips
// re-injection if one already exists, so we beat it to the punch and stamp
// our nonce on the tag. CSS content mirrors the library's source — see
// node_modules/react-draggable/build/cjs/utils/domFns.js.
const REACT_DRAGGABLE_STYLE_ID = 'react-draggable-style-el';
const REACT_DRAGGABLE_CSS =
  '.react-draggable-transparent-selection *::-moz-selection {all: inherit;}\n' +
  '.react-draggable-transparent-selection *::selection {all: inherit;}\n';

export function preinjectReactDraggableStyle(nonce: string | undefined): void {
  if (typeof document === 'undefined') return;
  if (document.getElementById(REACT_DRAGGABLE_STYLE_ID)) return;
  const styleEl = document.createElement('style');
  styleEl.id = REACT_DRAGGABLE_STYLE_ID;
  if (nonce) styleEl.setAttribute('nonce', nonce);
  styleEl.textContent = REACT_DRAGGABLE_CSS;
  document.head.appendChild(styleEl);
}
