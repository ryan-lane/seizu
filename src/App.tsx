import { useMemo, useState, useEffect } from 'react';
import { useRoutes } from 'react-router-dom';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import CssBaseline from '@mui/material/CssBaseline';
import GlobalStyles from 'src/components/GlobalStyles';
import AuthProvider from 'src/components/AuthProvider';
import shadows from 'src/theme/shadows';
import typography from 'src/theme/typography';
import { brand } from 'src/theme/brand';
import routes from 'src/routes';
import { AuthConfigContext, type AuthConfig, type OidcConfig } from 'src/authConfig.context';
import { createUserManager } from 'src/userManager';
import { CurrentUserProvider } from 'src/hooks/useCurrentUser';

function App() {
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');
  const [authConfig, setAuthConfig] = useState<AuthConfig>({
    auth_required: true,
    oidc: null,
    userManager: null
  });

  useEffect(() => {
    fetch('/api/v1/config')
      .then((r) => r.json())
      .then((data: { auth_required: boolean; oidc: OidcConfig | null }) => {
        const oidc = data.oidc ?? null;
        const userManager = (data.auth_required && oidc) ? createUserManager(oidc) : null;
        setAuthConfig({ auth_required: data.auth_required, oidc, userManager });
      })
      .catch(() => {
        // Keep default (auth_required: true) on error — safe fallback.
      });
  }, []);

  const theme = useMemo(
    () =>
      createTheme({
        palette: prefersDarkMode
          ? {
              mode: 'dark',
              primary: { main: brand.starlight, contrastText: brand.space },
              secondary: { main: brand.ember, contrastText: brand.space },
              background: { default: brand.space, paper: '#111a33' },
              text: { primary: brand.paper, secondary: '#aab8d6' },
              divider: 'rgba(143, 180, 255, 0.15)'
            }
          : {
              mode: 'light',
              primary: { main: brand.starlightDark, contrastText: '#ffffff' },
              secondary: { main: brand.emberDark, contrastText: '#ffffff' },
              background: { default: brand.paper, paper: '#ffffff' },
              text: { primary: brand.space, secondary: '#3b4a6b' },
              divider: 'rgba(58, 90, 165, 0.16)'
            },
        shadows,
        typography
      }),
    [prefersDarkMode]
  );

  const routing = useRoutes(routes);

  return (
    <AuthConfigContext.Provider value={authConfig}>
      <ThemeProvider theme={theme}>
        <GlobalStyles />
        <CssBaseline />
        <AuthProvider>
          <CurrentUserProvider>{routing}</CurrentUserProvider>
        </AuthProvider>
      </ThemeProvider>
    </AuthConfigContext.Provider>
  );
}

export default App;
