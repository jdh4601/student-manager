import axios from 'axios';

// Normalize API base URL to always be absolute-or-rooted and without trailing slash
function normalizeBaseURL(input: string | undefined) {
  const raw = input && input.trim().length > 0 ? input.trim() : '/api/v1';
  // If it's an absolute URL (http/https), leave scheme as-is but strip trailing slash
  if (/^https?:\/\//i.test(raw)) {
    return raw.endsWith('/') ? raw.slice(0, -1) : raw;
  }
  // Ensure leading slash for relative roots like 'api/v1'
  const withLeading = raw.startsWith('/') ? raw : `/${raw}`;
  return withLeading.endsWith('/') ? withLeading.slice(0, -1) : withLeading;
}

const apiClient = axios.create({
  baseURL: normalizeBaseURL(import.meta.env.VITE_API_BASE),
  withCredentials: true,
});

// Lazy import to avoid circular deps
const getAuthStore = async () => await import('../stores/authStore');

apiClient.interceptors.request.use(async (config) => {
  const { useAuthStore } = await getAuthStore();
  const token = useAuthStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    const url: string | undefined = error.config?.url;
    // Do not attempt refresh for auth endpoints themselves to avoid loops
    const isAuthEndpoint = url?.includes('/auth/refresh') || url?.includes('/auth/login');
    if (error.response?.status === 401 && !error.config.__isRetryRequest && !isAuthEndpoint) {
      error.config.__isRetryRequest = true;
      try {
        const { data } = await axios.post(
          `${apiClient.defaults.baseURL}/auth/refresh`,
          {},
          { withCredentials: true },
        );
        const { useAuthStore } = await getAuthStore();
        useAuthStore.getState().setAccessToken(data.access_token);
        error.config.headers['Authorization'] = `Bearer ${data.access_token}`;
        return apiClient(error.config);
      } catch {
        const { useAuthStore } = await getAuthStore();
        useAuthStore.getState().logout();
        window.location.href = '/login?reason=expired';
      }
    }
    return Promise.reject(error);
  },
);

export default apiClient;
