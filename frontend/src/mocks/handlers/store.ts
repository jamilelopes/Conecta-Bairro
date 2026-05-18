import type { User } from '../../api/types';

const ROLE_KEY = 'cb.user_role';

export const profileStore = new Map<string, User>();

const MOCK_ID = 'mock-user-001';

export function getCurrentIdentity() {
  return { userId: MOCK_ID, token: '' };
}

export function getOrCreateUser(): User | null {
  const cached = profileStore.get(MOCK_ID);
  if (cached) return cached;

  const role = (localStorage.getItem(ROLE_KEY) ?? 'client') as User['role'];
  const user: User = {
    id: MOCK_ID,
    email: 'mock@conectabairro.dev',
    name: 'Usuário Mock',
    role,
    avatarUrl: '',
    phone: '',
    createdAt: new Date().toISOString(),
  };
  profileStore.set(MOCK_ID, user);
  return user;
}
