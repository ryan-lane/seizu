import { render, screen, fireEvent } from '@testing-library/react';
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
    onMobileNavOpen: jest.fn(),
    setAuth: jest.fn(),
    setDriver: jest.fn(),
    neo4jSettings: { authMode: 'native', protocol: 'bolt', hostname: 'localhost', port: 7687 }
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders without error', () => {
    render(
      <Wrapper contextValue={{ auth: { username: 'testuser' } }}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText(/logged in as/i)).toBeInTheDocument();
  });

  it('shows the authenticated username', () => {
    render(
      <Wrapper contextValue={{ auth: { username: 'alice' } }}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    expect(screen.getByText(/alice/i)).toBeInTheDocument();
  });

  it('shows Log Out link when authMode is not auto', () => {
    render(
      <Wrapper contextValue={{ auth: { username: 'alice' } }}>
        <DashboardNavbar
          {...defaultProps}
          neo4jSettings={{ authMode: 'native', protocol: 'bolt', hostname: 'localhost', port: 7687 }}
        />
      </Wrapper>
    );
    expect(screen.getByText(/log out/i)).toBeInTheDocument();
  });

  it('hides Log Out link when authMode is auto', () => {
    render(
      <Wrapper contextValue={{ auth: { username: 'alice' } }}>
        <DashboardNavbar
          {...defaultProps}
          neo4jSettings={{ authMode: 'auto', protocol: 'bolt', hostname: 'localhost', port: 7687 }}
        />
      </Wrapper>
    );
    expect(screen.queryByText(/log out/i)).not.toBeInTheDocument();
  });

  it('calls setAuth and setDriver when Log Out is clicked', () => {
    render(
      <Wrapper contextValue={{ auth: { username: 'alice' } }}>
        <DashboardNavbar {...defaultProps} />
      </Wrapper>
    );
    fireEvent.click(screen.getByText(/log out/i));
    expect(defaultProps.setAuth).toHaveBeenCalled();
    expect(defaultProps.setDriver).toHaveBeenCalled();
  });

  it('shows refresh snackbar when configUpdate is defined', () => {
    render(
      <Wrapper contextValue={{ auth: {} }}>
        <DashboardNavbar {...defaultProps} configUpdate={{ some: 'update' } as any} />
      </Wrapper>
    );
    expect(screen.getByText('Settings have changed.')).toBeInTheDocument();
  });

  it('calls setConfig and setConfigUpdate when Refresh is clicked', () => {
    const configUpdate = { some: 'update' } as any;
    render(
      <Wrapper contextValue={{ auth: {} }}>
        <DashboardNavbar {...defaultProps} configUpdate={configUpdate} />
      </Wrapper>
    );
    fireEvent.click(screen.getByText(/refresh/i));
    expect(defaultProps.setConfig).toHaveBeenCalledWith(configUpdate);
    expect(defaultProps.setConfigUpdate).toHaveBeenCalled();
  });
});
