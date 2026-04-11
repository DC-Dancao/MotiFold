import { getApiUrl } from './api-base';

let refreshPromise: Promise<boolean> | null = null;

const redirectToLogin = () => {
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};

const refreshAuth = async () => {
  if (!refreshPromise) {
    const apiUrl = getApiUrl();
    refreshPromise = fetch(`${apiUrl}/auth/refresh`, {
      method: 'POST',
      credentials: 'include'
    })
      .then(async (res) => {
        if (!res.ok) {
          console.warn('Refresh auth failed with status:', res.status);
          return false;
        }
        return true;
      })
      .catch((err) => {
        console.error('Refresh auth request error:', err);
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
};

const isRefreshRequest = (url: string) => {
  try {
    return new URL(url, getApiUrl()).pathname === '/auth/refresh';
  } catch {
    return url.includes('/auth/refresh');
  }
};

export const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
  // Get current org from localStorage
  const currentOrgId = typeof window !== 'undefined'
    ? localStorage.getItem('motifold_current_org_id')
    : null;

  const headers: HeadersInit = {
    ...options.headers,
  };

  // Add X-Org-ID header if set and not an auth request
  if (currentOrgId && !url.includes('/auth/')) {
    headers['X-Org-ID'] = currentOrgId;
  }

  const finalOptions: RequestInit = {
    ...options,
    credentials: 'include',
    headers,
  };

  const response = await fetch(url, finalOptions);

  if (response.status !== 401 || isRefreshRequest(url)) {
    return response;
  }

  const refreshed = await refreshAuth();
  if (!refreshed) {
    redirectToLogin();
    return response;
  }

  const retryResponse = await fetch(url, finalOptions);
  if (retryResponse.status === 401) {
    redirectToLogin();
  }

  return retryResponse;
};
