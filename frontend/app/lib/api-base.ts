const DEFAULT_SERVER_API_URL = 'http://api:8000';

function getProcessEnv(): NodeJS.ProcessEnv {
  return typeof process !== 'undefined' && process.env ? process.env : {};
}

export function resolveBrowserApiUrl(_env?: NodeJS.ProcessEnv) {
  return '';
}

export function resolveServerApiUrl(env?: NodeJS.ProcessEnv) {
  return (env || getProcessEnv()).INTERNAL_API_URL || (env || getProcessEnv()).API_URL || DEFAULT_SERVER_API_URL;
}

export function getApiUrl() {
  return typeof window === 'undefined'
    ? resolveServerApiUrl()
    : resolveBrowserApiUrl();
}

export function shouldUseSecureCookies(url?: string, env?: NodeJS.ProcessEnv) {
  if (url) {
    try {
      return new URL(url).protocol === 'https:';
    } catch {
      return false;
    }
  }

  const processEnv = env || getProcessEnv();
  const configuredUrl =
    processEnv.APP_URL ||
    processEnv.NEXT_PUBLIC_APP_URL ||
    processEnv.NEXT_PUBLIC_DIRECT_API_URL ||
    processEnv.NEXT_PUBLIC_API_URL ||
    '';

  if (!configuredUrl) {
    return false;
  }

  try {
    return new URL(configuredUrl).protocol === 'https:';
  } catch {
    return false;
  }
}
