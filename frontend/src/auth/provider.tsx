import { createContext, useEffect, useState, type ReactNode } from 'react';
import { useAuth as useClerkAuth, useUser, useSignIn, useClerk } from '@clerk/react';
import { getRole, setRole, getPendingRole, setPendingRole, clearPendingRole } from './storage';

type Identity = { userId: string };
type Claims = { email: string; name: string; picture: string } | null;

type AuthContextValue = {
  identity: Identity;
  claims: Claims;
  role: 'client' | 'professional';
  loading: boolean;
  signIn: (role: 'client' | 'professional') => Promise<void>;
  signOut: () => void;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn } = useClerkAuth();
  const { user } = useUser();
  const { signIn: clerkSignIn } = useSignIn();
  const { signOut: clerkSignOut } = useClerk();

  const [role, setRoleState] = useState<'client' | 'professional'>(() => getRole());

  useEffect(() => {
    if (!isSignedIn) return;
    const pending = getPendingRole();
    if (pending) {
      setRole(pending);
      setRoleState(pending);
      clearPendingRole();
    }
  }, [isSignedIn]);

  const signIn = async (selectedRole: 'client' | 'professional') => {
    if (!isLoaded) return;
    setPendingRole(selectedRole);
    const { error } = await clerkSignIn.sso({
      strategy: 'oauth_google',
      redirectUrl: '/auth/callback',
      redirectCallbackUrl: '/auth/callback',
    });
    if (error) console.error('[auth] SSO error:', error);
  };

  const signOut = () => void clerkSignOut();

  const identity: Identity = { userId: isSignedIn ? (user?.id ?? '') : '' };

  const claims: Claims = user
    ? {
        email: user.primaryEmailAddress?.emailAddress ?? '',
        name: user.fullName ?? '',
        picture: user.imageUrl ?? '',
      }
    : null;

  return (
    <AuthContext.Provider
      value={{ identity, claims, role, loading: !isLoaded, signIn, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}
