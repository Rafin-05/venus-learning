export type User = {
  id: number; email: string; full_name: string; role: string;
  bio?: string; expertise?: string; profile_pic?: string; is_verified: boolean; current_streak: number;
};
export type Course = {
  id: number; title: string; description: string; category: string; level: string;
  thumbnail?: string; instructor_name?: string; status?: string;
  average_rating?: number; student_count?: number; lesson_count?: number;
};

function errorText(value: unknown, prefix = ''): string {
  if (typeof value === 'string') return prefix ? `${prefix}: ${value}` : value;
  if (Array.isArray(value)) return value.map(item => errorText(item, prefix)).filter(Boolean).join('; ');
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([key, item]) =>
      errorText(item, ['detail', 'message', 'non_field_errors'].includes(key) ? prefix : key.replaceAll('_', ' '))
    ).filter(Boolean).join('; ');
  }
  return '';
}

async function csrf(): Promise<string> {
  const response = await fetch('/api/auth/csrf/', { credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) throw new Error('Could not establish a secure session. Reload and try again.');
  const payload = await response.json();
  if (typeof payload.csrfToken !== 'string' || !payload.csrfToken) {
    throw new Error('The security token is missing. Reload and try again.');
  }
  return payload.csrfToken;
}

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  if (!path.startsWith('/') || path.startsWith('//')) throw new Error('Invalid API path');
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  // Fetch a fresh token for each mutation: Django rotates it after authentication.
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers.set('X-CSRFToken', await csrf());
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...options, headers, credentials: 'same-origin', cache: 'no-store' });
  } catch {
    throw new Error('The server could not be reached. Check your connection and try again.');
  }
  if (!response.ok) {
    let detail = '';
    try { detail = errorText(await response.json()); } catch { /* Do not render server HTML errors. */ }
    throw new Error(`${response.status}: ${detail || (response.status === 429 ? 'Too many attempts. Please wait before trying again.' : 'The request could not be completed.')}`);
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json();
  // These screens render complete collections; follow pagination rather than silently
  // dropping lessons, certificates, or moderation records after the first page.
  if (method === 'GET' && payload && Array.isArray(payload.results) && payload.next) {
    const expectedPath = new URL(`/api${path}`, 'https://venus.invalid').pathname;
    const items = [...payload.results];
    let next = payload.next;
    let pages = 1;
    while (next) {
      if (++pages > 500) throw new Error('This collection is too large. Narrow the search and try again.');
      const target = new URL(next, 'https://venus.invalid');
      if (target.pathname !== expectedPath) throw new Error('The server returned an invalid pagination link.');
      const pageResponse = await fetch(`${target.pathname}${target.search}`, {headers, credentials:'same-origin', cache:'no-store'});
      if (!pageResponse.ok) throw new Error(`Could not load the complete list (${pageResponse.status}). Please try again.`);
      const page = await pageResponse.json();
      if (!Array.isArray(page.results)) throw new Error('The server returned an invalid page.');
      items.push(...page.results);
      next = page.next;
    }
    return {...payload, results:items, next:null} as T;
  }
  return payload as T;
}

export const list = (data: any): any[] => Array.isArray(data) ? data : data?.results || [];
export const all = async <T = any>(path: string): Promise<T[]> => list(await api(path)) as T[];
export const post = <T = any>(path: string, body: unknown) => api<T>(path, { method: 'POST', body: JSON.stringify(body) });
export const patch = <T = any>(path: string, body: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
