import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { userManager } from 'src/userManager';

function OidcCallback() {
  const navigate = useNavigate();
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
  }, [navigate]);

  return null;
}

export default OidcCallback;
