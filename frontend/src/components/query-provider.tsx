import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';
import { NuqsAdapter } from 'nuqs/adapters/react';
import { ClerkProvider } from '@clerk/react';
import { initMocks } from '../mocks/init';
import { AuthProvider } from '../auth/provider';

interface QueryProviderProps {
  children: ReactNode;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,
      retry: 1,
    },
  },
});

export function QueryProvider({ children }: QueryProviderProps) {
  const mockEnabled = import.meta.env.PUBLIC_ENABLE_MOCK === 'true';
  const [ready, setReady] = useState(!mockEnabled);

  useEffect(() => {
    if (!mockEnabled) return;
    initMocks().then(() => setReady(true));
  }, [mockEnabled]);

  if (!ready) return null;

  const clerkKey = import.meta.env.PUBLIC_CLERK_PUBLISHABLE_KEY ?? '';

  return (
    <ClerkProvider publishableKey={clerkKey}>
      <NuqsAdapter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>{children}</AuthProvider>
        </QueryClientProvider>
      </NuqsAdapter>
    </ClerkProvider>
  );
}
