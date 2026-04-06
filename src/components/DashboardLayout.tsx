import { useState, useEffect, ReactElement } from 'react';
import { Outlet } from 'react-router-dom';
import { CircularProgress, styled } from '@mui/material';
import { trackPromise, usePromiseTracker } from 'react-promise-tracker';
import { ConfigContext, SeizuConfig } from 'src/config.context';
import DashboardNavbar from 'src/components/DashboardNavbar';
import DashboardSidebar from 'src/components/DashboardSidebar';

function LoadingIndicator(): ReactElement | false {
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
        <CircularProgress />
      </div>
    )
  );
}

const DashboardLayoutRoot = styled('div')(({ theme }) => ({
  backgroundColor: theme.palette.background.default,
  display: 'flex',
  height: '100%',
  overflow: 'hidden',
  width: '100%'
}));

const DashboardLayoutWrapper = styled('div')(({ theme }) => ({
  display: 'flex',
  flex: '1 1 auto',
  overflow: 'hidden',
  paddingTop: 64,
  [theme.breakpoints.up('lg')]: {
    paddingLeft: 256
  }
}));

const DashboardLayoutContainer = styled('div')({
  display: 'flex',
  flex: '1 1 auto',
  overflow: 'hidden'
});

const DashboardLayoutContent = styled('div')({
  flex: '1 1 auto',
  height: '100%',
  overflow: 'auto'
});

function DashboardLayout() {
  const [isMobileNavOpen, setMobileNavOpen] = useState(false);
  const [config, setConfig] = useState<SeizuConfig | undefined>();
  const [configUpdate, setConfigUpdate] = useState<SeizuConfig | undefined>();

  const getConfig = (): Promise<Response> => {
    const requestOptions: RequestInit = {
      method: 'GET',
      headers: {
        'Content-Type': 'Application/json'
      }
    };
    return fetch('/api/v1/config', requestOptions);
  };

  useEffect(() => {
    trackPromise(
      getConfig()
        .then((res) => res.json())
        .then(
          (result: SeizuConfig) => {
            setConfig(result);
          },
          (error: unknown) => {
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
            (result: SeizuConfig) => {
              if (JSON.stringify(result) !== JSON.stringify(config)) {
                setConfigUpdate(result);
              }
            },
            (error: unknown) => {
              console.log('Configuration fetch error', error);
            }
          );
      }
    }, 60000);
    return () => clearInterval(interval);
  }, [config]);

  if (config === undefined) {
    return <LoadingIndicator />;
  }

  return (
    // eslint-disable-next-line react/jsx-no-constructed-context-values
    <ConfigContext.Provider value={{ config }}>
      <DashboardLayoutRoot>
        <DashboardNavbar
          configUpdate={configUpdate}
          setConfigUpdate={setConfigUpdate}
          setConfig={setConfig}
          onMobileNavOpen={() => setMobileNavOpen(true)}
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
    </ConfigContext.Provider>
  );
}

export default DashboardLayout;
