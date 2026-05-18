import { http, HttpResponse } from 'msw';
import { getOrCreateUser, getCurrentIdentity } from './store';
import type { ProfessionalProfile, ProfessionalUpdate } from '../../api/types';

const proStore = new Map<string, ProfessionalProfile>();

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function getOrCreatePro(): ProfessionalProfile | null {
  const user = getOrCreateUser();
  if (!user || user.role !== 'professional') return null;

  const cached = proStore.get(user.id);
  if (cached) return cached;

  const profile: ProfessionalProfile = {
    id: user.id,
    userId: user.id,
    slug: slugify(user.name),
    name: user.name,
    title: '',
    description: '',
    avatarUrl: user.avatarUrl,
    phone: user.phone ?? '',
    email: user.email,
    instagram: '',
    website: '',
    registrationNumber: '',
    address: { state: '', city: '', district: '', street: '', number: '' },
    state: '',
    city: '',
    district: '',
    rating: 0,
    reviewsCount: 0,
    reviews: [],
    categories: [],
    verified: false,
    available: true,
    createdAt: user.createdAt,
  };
  proStore.set(user.id, profile);
  return profile;
}

const unauthorized = () =>
  HttpResponse.json({ code: 'UNAUTHORIZED', message: 'Not authenticated' }, { status: 401 });

const notProfessional = () =>
  HttpResponse.json({ code: 'NOT_FOUND', message: 'User is not a professional' }, { status: 404 });

export const professionalsMeHandlers = [
  http.get('*/professionals/me', () => {
    const user = getOrCreateUser();
    if (!user) return unauthorized();
    const profile = getOrCreatePro();
    if (!profile) return notProfessional();
    return HttpResponse.json(profile, { status: 200 });
  }),

  http.put('*/professionals/me', async ({ request }) => {
    const user = getOrCreateUser();
    if (!user) return unauthorized();
    const existing = getOrCreatePro();
    if (!existing) return notProfessional();

    const body = (await request.json()) as ProfessionalUpdate;
    const { categories: newCategoryIds, ...restBody } = body;
    const updatedCategories =
      newCategoryIds !== undefined
        ? newCategoryIds.map(
            (id) => existing.categories.find((c) => c.id === id) ?? { id, name: id, slug: id, icon: '' },
          )
        : existing.categories;
    const updated: ProfessionalProfile = { ...existing, ...restBody, categories: updatedCategories };
    proStore.set(user.id, updated);
    return HttpResponse.json(updated, { status: 200 });
  }),
];
