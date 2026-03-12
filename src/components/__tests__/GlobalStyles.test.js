import { render } from '@testing-library/react';
import GlobalStyles from '../GlobalStyles';

describe('GlobalStyles', () => {
  it('renders without error', () => {
    expect(() => render(<GlobalStyles />)).not.toThrow();
  });
});
