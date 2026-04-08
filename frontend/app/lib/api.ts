export const getApiUrl = () => process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18000';

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
  const finalOptions: RequestInit = {
    ...options,
    credentials: 'include'
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
