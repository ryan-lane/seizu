import { createContext } from 'react';

export interface AuthContextValue {
  accessToken: string | null;
  isLoading: boolean;
}

export const AuthContext = createContext<AuthContextValue>({
  accessToken: null,
  isLoading: false,
});
