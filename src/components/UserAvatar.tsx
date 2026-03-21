import BoringAvatar from 'boring-avatars';

interface UserAvatarProps {
  /** Seed value for the generated avatar — use email for stability across sessions. */
  name?: string | null;
  size?: number;
}

function UserAvatar({ name, size = 32 }: UserAvatarProps) {
  return (
    <BoringAvatar
      size={size}
      name={name ?? 'anonymous'}
      variant="pixel"
    />
  );
}

export default UserAvatar;
