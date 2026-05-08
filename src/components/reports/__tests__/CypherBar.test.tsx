import { ellipsizeText, wrapAxisLabel } from '../CypherBar';

describe('CypherBar axis labels', () => {
  it('wraps long labels onto bounded lines', () => {
    expect(wrapAxisLabel('Scheduled queries')).toBe('Scheduled\nqueries');
  });

  it('keeps short labels on one line', () => {
    expect(wrapAxisLabel('Reports')).toBe('Reports');
  });

  it('ellipsizes labels that still exceed the line limit after wrapping', () => {
    expect(wrapAxisLabel('VeryLongSingleWordLabel', 8, 2, 10)).toBe('VeryLon...');
  });

  it('ellipsizes standalone text to the requested width', () => {
    expect(ellipsizeText('Dependency visibility', 12)).toBe('Dependenc...');
  });
});
