import { expandMarkdocVariables } from '../MarkdocVariableNode';

describe('expandMarkdocVariables', () => {
  it('replaces {% $name %} with a span carrying data-markdoc-var', () => {
    const out = expandMarkdocVariables('Hello {% $org %}!');
    expect(out).toBe('Hello <span data-markdoc-var="org"></span>!');
  });

  it('replaces multiple variables in one pass', () => {
    const out = expandMarkdocVariables('{% $a %} and {% $b %}');
    expect(out).toBe('<span data-markdoc-var="a"></span> and <span data-markdoc-var="b"></span>');
  });

  it('tolerates whitespace around the variable name', () => {
    expect(expandMarkdocVariables('{%  $foo  %}')).toBe('<span data-markdoc-var="foo"></span>');
  });

  it('leaves text without a variable untouched', () => {
    expect(expandMarkdocVariables('Plain text')).toBe('Plain text');
  });

  it('leaves legacy {{name}} placeholders untouched (they will not substitute)', () => {
    expect(expandMarkdocVariables('Hello {{name}}')).toBe('Hello {{name}}');
  });
});
