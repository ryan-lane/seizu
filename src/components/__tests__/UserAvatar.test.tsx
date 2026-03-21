import { render } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import UserAvatar from '../UserAvatar';

const theme = createTheme();

function Wrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
}

describe('UserAvatar', () => {
  it('renders an SVG for a given name', () => {
    const { container } = render(
      <Wrapper>
        <UserAvatar name="Alice Smith" />
      </Wrapper>
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('renders an SVG when name is null', () => {
    const { container } = render(
      <Wrapper>
        <UserAvatar name={null} />
      </Wrapper>
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('renders an SVG when no props are passed', () => {
    const { container } = render(
      <Wrapper>
        <UserAvatar />
      </Wrapper>
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('respects the size prop', () => {
    const { container } = render(
      <Wrapper>
        <UserAvatar name="Alice" size={48} />
      </Wrapper>
    );
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('width')).toBe('48');
    expect(svg?.getAttribute('height')).toBe('48');
  });
});
