import { useMemo } from 'react';
import { useRoutes } from 'react-router-dom';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import CssBaseline from '@mui/material/CssBaseline';
import GlobalStyles from 'src/components/GlobalStyles';
import shadows from 'src/theme/shadows';
import typography from 'src/theme/typography';
import routes from 'src/routes';

function App() {
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');

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
    <ThemeProvider theme={theme}>
      <GlobalStyles />
      <CssBaseline />
      {routing}
    </ThemeProvider>
  );
}

export default App;
