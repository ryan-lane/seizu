import { render, screen, cleanup } from '@testing-library/react';
import Logo from '../Logo';

describe('Logo', () => {
  afterEach(cleanup);

  it('renders an image with alt text', () => {
    render(<Logo />);
    const img = screen.getByAltText('Logo');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute(
      'src',
      '/static/images/logo-horizontal-with-text-white.png'
    );
    expect(img).toHaveAttribute('height', '50');
  });

  it('passes additional props to the img element', () => {
    render(<Logo data-testid="logo-img" />);
    expect(screen.getByTestId('logo-img')).toBeInTheDocument();
  });
});
