const DEFAULT_BROWSER_API_URL = 'http://localhost:18000';
const DEFAULT_SERVER_API_URL = 'http://api:8000';

function getProcessEnv(): NodeJS.ProcessEnv {
  return typeof process !== 'undefined' && process.env ? process.env : {};
}

export function resolveBrowserApiUrl(env?: NodeJS.ProcessEnv) {
  return (env || getProcessEnv()).NEXT_PUBLIC_API_URL || DEFAULT_BROWSER_API_URL;
}

export function resolveServerApiUrl(env?: NodeJS.ProcessEnv) {
  return (env || getProcessEnv()).INTERNAL_API_URL || (env || getProcessEnv()).API_URL || DEFAULT_SERVER_API_URL;
}

export function getApiUrl() {
  return typeof window === 'undefined'
    ? resolveServerApiUrl()
    : resolveBrowserApiUrl();
}
