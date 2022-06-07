import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { experimentalStyled } from '@mui/material';
import { Neo4jProvider, createDriver } from 'use-neo4j';
import { trackPromise, usePromiseTracker } from 'react-promise-tracker';
import { ConfigContext } from 'src/config.context';
import Loader from 'react-loader-spinner';
import DashboardNavbar from 'src/components/DashboardNavbar';
import DashboardSidebar from 'src/components/DashboardSidebar';
import AuthDialog from 'src/components/AuthDialog';

function LoadingIndicator() {
  const { promiseInProgress } = usePromiseTracker();
  return (
    promiseInProgress && (
      <div
        style={{
          width: '100%',
          height: '100',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center'
        }}
      >
        <Loader type="ThreeDots" color="#2BAD60" height="100" width="100" />
      </div>
    )
  );
}

const DashboardLayoutRoot = experimentalStyled('div')(({ theme }) => ({
  backgroundColor: theme.palette.background.default,
  display: 'flex',
  height: '100%',
  overflow: 'hidden',
  width: '100%'
}));

const DashboardLayoutWrapper = experimentalStyled('div')(({ theme }) => ({
  display: 'flex',
  flex: '1 1 auto',
  overflow: 'hidden',
  paddingTop: 64,
  [theme.breakpoints.up('lg')]: {
    paddingLeft: 256
  }
}));

const DashboardLayoutContainer = experimentalStyled('div')({
  display: 'flex',
  flex: '1 1 auto',
  overflow: 'hidden'
});

const DashboardLayoutContent = experimentalStyled('div')({
  flex: '1 1 auto',
  height: '100%',
  overflow: 'auto'
});

function DashboardLayout() {
  const [isMobileNavOpen, setMobileNavOpen] = useState(false);
  const [driver, setDriver] = useState();
  const [config, setConfig] = useState();
  const [configUpdate, setConfigUpdate] = useState();
  const [auth, setAuth] = useState();
  const [neo4jSettings, setNeo4jSettings] = useState();

  const authenticate = () => {
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('_csrf_token='))
      .split('=')[1];
    const requestOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'Application/json',
        'X-CSRFToken': csrfToken
      }
    };
    return fetch('/api/v1/login', requestOptions);
  };

  const getConfig = () => {
    const requestOptions = {
      method: 'GET',
      headers: {
        'Content-Type': 'Application/json'
      }
    };
    return fetch('/api/v1/config', requestOptions);
  };

  useEffect(() => {
    trackPromise(
      authenticate()
        .then((res) => res.json())
        .then(
          (result) => {
            setNeo4jSettings({
              protocol: result.protocol,
              hostname: result.hostname,
              port: result.port,
              authMode: result.auth_mode
            });
            if (result.auth_mode === 'auto') {
              setAuth({
                username: result.username,
                password: result.password
              });
              const d = createDriver(
                result.protocol,
                result.hostname,
                result.port,
                result.username,
                result.password
              );
              setDriver(d);
            }
          },
          (error) => {
            console.log('Authentication error', error);
          }
        )
    );
  }, []);

  useEffect(() => {
    trackPromise(
      getConfig()
        .then((res) => res.json())
        .then(
          (result) => {
            setConfig(result);
          },
          (error) => {
            console.log('Configuration fetch error', error);
          }
        )
    );
  }, []);

  // Refetch the configuration on an interval, so that we can give the end-user a refresh dialog.
  useEffect(() => {
    const interval = setInterval(() => {
      // To avoid a race condition with the initial config fetch, ensure we only fetch the update if
      // the config is already set.
      if (config !== undefined) {
        getConfig()
          .then((res) => res.json())
          .then(
            (result) => {
              if (JSON.stringify(result) !== JSON.stringify(config)) {
                setConfigUpdate(result);
              }
            },
            (error) => {
              console.log('Configuration fetch error', error);
            }
          );
      }
    }, 60000);
    return () => clearInterval(interval);
  }, [config]);

  if (neo4jSettings === undefined || neo4jSettings.authMode === 'auto') {
    if (driver === undefined || config === undefined || auth === undefined) {
      return <LoadingIndicator />;
    }
  } else if (
    driver === undefined ||
    config === undefined ||
    auth === undefined
  ) {
    return (
      <AuthDialog
        setAuth={setAuth}
        neo4jSettings={neo4jSettings}
        setDriver={setDriver}
      />
    );
  }

  return (
    // eslint-disable-next-line react/jsx-no-constructed-context-values
    <ConfigContext.Provider value={{ config, auth }}>
      <Neo4jProvider driver={driver}>
        <DashboardLayoutRoot>
          <DashboardNavbar
            configUpdate={configUpdate}
            setConfigUpdate={setConfigUpdate}
            setConfig={setConfig}
            onMobileNavOpen={() => setMobileNavOpen(true)}
            setAuth={setAuth}
            setDriver={setDriver}
            neo4jSettings={neo4jSettings}
          />
          <DashboardSidebar
            onMobileClose={() => setMobileNavOpen(false)}
            openMobile={isMobileNavOpen}
          />
          <DashboardLayoutWrapper>
            <DashboardLayoutContainer>
              <DashboardLayoutContent>
                <Outlet />
              </DashboardLayoutContent>
            </DashboardLayoutContainer>
          </DashboardLayoutWrapper>
        </DashboardLayoutRoot>
      </Neo4jProvider>
    </ConfigContext.Provider>
  );
}

export default DashboardLayout;
