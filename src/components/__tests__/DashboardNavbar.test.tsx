import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { ConfigContext } from 'src/config.context';
import DashboardNavbar from '../DashboardNavbar';

const theme = createTheme();

function Wrapper({ contextValue, children }: { contextValue: any; children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <ThemeProvider theme={theme}>
        <ConfigContext.Provider value={contextValue}>
          {children}
        </ConfigContext.Provider>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('DashboardNavbar', () => {
  const defaultProps = {
    setConfigUpdate: jest.fn(),
    setConfig: jest.fn(),
    onMobileNavOpen: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(cleanup);

  it('renders without error', () => {
    const { container } = render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(container.firstChild).not.toBeNull();
  });

  it('shows refresh snackbar when configUpdate is defined', () => {
    render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} configUpdate={{ some: 'update' } as any} />
      </Wrapper>
    );
    expect(screen.getByText('Settings have changed.')).toBeInTheDocument();
  });

  it('calls setConfig and setConfigUpdate when Refresh is clicked', () => {
    const configUpdate = { some: 'update' } as any;
    render(
      <Wrapper contextValue={{}}>
        <DashboardNavbar {...defaultProps} configUpdate={configUpdate} />
      </Wrapper>
    );
    fireEvent.click(screen.getByText(/refresh/i));
    expect(defaultProps.setConfig).toHaveBeenCalledWith(configUpdate);
    expect(defaultProps.setConfigUpdate).toHaveBeenCalled();
  });
});
