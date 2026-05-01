import { useMemo } from 'react';
import { CurrentUser, useCurrentUserState } from './useCurrentUser';

/**
 * Returns permission checks along with the current user loading state.
 */
export function usePermissionState(): {
  hasPermission: (permission: string) => boolean;
  loading: boolean;
  currentUser: CurrentUser | null;
} {
  const { currentUser, loading } = useCurrentUserState();

  const hasPermission = useMemo(() => {
    if (!currentUser) return (_permission: string) => false;
    const permSet = new Set(currentUser.permissions);
    return (permission: string) => permSet.has(permission);
  }, [currentUser]);

  return { hasPermission, loading, currentUser };
}

/**
 * Returns a function that checks whether the current user has a given permission.
 * Returns false for all permissions while the user profile is still loading.
 */
export function usePermissions(): (permission: string) => boolean {
  const { hasPermission } = usePermissionState();
  return hasPermission;
}
