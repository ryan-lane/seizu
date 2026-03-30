import { useMemo } from 'react';
import { useCurrentUser } from './useCurrentUser';

/**
 * Returns a function that checks whether the current user has a given permission.
 * Returns false for all permissions while the user profile is still loading.
 */
export function usePermissions(): (permission: string) => boolean {
  const currentUser = useCurrentUser();

  return useMemo(() => {
    if (!currentUser) return () => false;
    const permSet = new Set(currentUser.permissions);
    return (permission: string) => permSet.has(permission);
  }, [currentUser]);
}
