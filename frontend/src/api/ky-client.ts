import ky from 'ky';

declare global {
  interface Window {
    Clerk?: { session?: { getToken: () => Promise<string | null> } };
  }
}

const BASE_URL = (import.meta.env.PUBLIC_API_BASE_URL ?? '').replace(/\/$/, '');

export async function customFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const token = await window.Clerk?.session?.getToken() ?? null;
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  const response = await ky(`${BASE_URL}${url}`, {
    ...(options as Parameters<typeof ky>[1]),
    headers: { ...options?.headers, ...authHeaders },
  });
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return response.json<T>();
  }
  return response.text() as Promise<T>;
}
