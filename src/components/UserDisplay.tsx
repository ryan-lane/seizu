import { useUser } from 'src/hooks/useUser';

interface UserDisplayProps {
  /** The stored created_by value — either a Snowflake user_id or a legacy email string. */
  userId: string;
}

/**
 * Resolves a user_id to a human-readable display name.
 * Falls back to email, then the raw userId (e.g. legacy email strings).
 */
function UserDisplay({ userId }: UserDisplayProps) {
  const user = useUser(userId);
  return <>{user ? (user.display_name ?? user.email) : userId}</>;
}

export default UserDisplay;
