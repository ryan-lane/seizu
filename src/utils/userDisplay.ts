import { CurrentUser } from 'src/hooks/useCurrentUser';

export const UNKNOWN_USER_LABEL = 'Unknown user';

export function getUserDisplayName(
  user: Pick<
    CurrentUser,
    'display_name' | 'preferred_username' | 'email'
  > | null,
): string {
  return (
    user?.display_name ||
    user?.preferred_username ||
    user?.email ||
    UNKNOWN_USER_LABEL
  );
}

export function getUserAvatarSeed(
  user: Pick<
    CurrentUser,
    'user_id' | 'display_name' | 'preferred_username' | 'email'
  > | null,
): string {
  return (
    user?.email ||
    user?.preferred_username ||
    user?.display_name ||
    user?.user_id ||
    UNKNOWN_USER_LABEL
  );
}
