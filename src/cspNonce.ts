// Read the per-request CSP nonce that the backend injected into the served
// HTML's `<meta property="csp-nonce">` tag. Pass this to libraries that
// inject their own <style> elements at runtime (emotion cache, tss-react
// cache, Tiptap editor, etc.) so their tags satisfy
// `style-src 'self' 'nonce-...'`.
export function getCspNonce(): string | undefined {
  const nonceMeta = document.querySelector('meta[property="csp-nonce"]');
  return nonceMeta?.getAttribute('content') ?? undefined;
}
