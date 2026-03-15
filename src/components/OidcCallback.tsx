import { useEffect, useRef, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthConfigContext } from 'src/authConfig.context';

function OidcCallback() {
  const navigate = useNavigate();
  const { userManager } = useContext(AuthConfigContext);
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current || !userManager) return;
    handled.current = true;

    userManager
      .signinRedirectCallback()
      .then(() => {
        navigate('/', { replace: true });
      })
      .catch((err: unknown) => {
        console.error('OIDC callback error', err);
        navigate('/', { replace: true });
      });
  }, [navigate, userManager]);

  return null;
}

export default OidcCallback;
