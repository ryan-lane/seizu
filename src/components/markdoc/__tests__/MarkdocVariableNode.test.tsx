import markdownit from 'markdown-it';
import { setupMarkdocVariableMarkdownIt } from '../MarkdocVariableNode';

function renderWithRule(source: string): string {
  const md = markdownit({ html: false });
  setupMarkdocVariableMarkdownIt(md);
  return md.render(source);
}

describe('MarkdocVariable markdown-it rule', () => {
  it('renders {%$name%} as a span with data-markdoc-var', () => {
    expect(renderWithRule('Hello {%$foo%}!')).toContain('<span data-markdoc-var="foo"></span>');
  });

  it('accepts the spaced form {% $name %}', () => {
    expect(renderWithRule('{% $org %}')).toContain('<span data-markdoc-var="org"></span>');
  });

  it('handles multiple variables in a single line', () => {
    const out = renderWithRule('a={%$x%} and b={%$y%}');
    expect(out).toContain('<span data-markdoc-var="x"></span>');
    expect(out).toContain('<span data-markdoc-var="y"></span>');
  });

  it('does not match invalid identifiers', () => {
    // Uppercase / numbers leading / hyphens are not lower_snake_case.
    const out = renderWithRule('{%$Foo%} {%$1bad%} {%$has-dash%}');
    expect(out).not.toContain('data-markdoc-var=');
  });

  it('parses a variable inside link text and keeps the link as an <a>', () => {
    // markdown-it parses the link because the URL has no spaces (compact form
    // is required). The variable inside the link *text* becomes a span; the
    // variable inside the *href* stays URL-encoded literal — the production
    // renderer handles href substitution at view time.
    const out = renderWithRule('[{%$org%}](https://example.com/{%$org%})');
    expect(out).toContain('<a href="');
    expect(out).toContain('><span data-markdoc-var="org"></span></a>');
  });

  it('still escapes raw HTML when html: false (independent of our rule)', () => {
    expect(renderWithRule('<script>x</script>')).not.toContain('<script>');
  });
});
