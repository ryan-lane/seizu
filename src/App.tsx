import { useMemo, useState, useEffect } from 'react';
import { useRoutes } from 'react-router-dom';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import CssBaseline from '@mui/material/CssBaseline';
import GlobalStyles from 'src/components/GlobalStyles';
import AuthProvider from 'src/components/AuthProvider';
import shadows from 'src/theme/shadows';
import typography from 'src/theme/typography';
import routes from 'src/routes';
import { AuthConfigContext, type AuthConfig } from 'src/authConfig.context';

function App() {
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');
  const [authConfig, setAuthConfig] = useState<AuthConfig>({ auth_required: true });

  useEffect(() => {
    fetch('/api/v1/config')
      .then((r) => r.json())
      .then((data: { auth_required: boolean }) => {
        setAuthConfig({ auth_required: data.auth_required });
      })
      .catch(() => {
        // Keep default (auth_required: true) on error — safe fallback.
      });
  }, []);

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: prefersDarkMode ? 'dark' : 'light',
          primary: {
            contrastText: '#ffffff',
            main: '#5664d2'
          }
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
        <AuthProvider>{routing}</AuthProvider>
      </ThemeProvider>
    </AuthConfigContext.Provider>
  );
}

export default App;
