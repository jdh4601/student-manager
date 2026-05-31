import apiClient from './client';
import axios from 'axios';

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  school_id: string;
}

export interface InvitationPreview {
  email: string;
  name: string;
  role: string;
  expires_at: string;
}

export interface PasswordRecoveryResponse {
  accepted: boolean;
  delivery: string;
  preview_url?: string | null;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', { email, password });
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>('/auth/me');
  return data;
}

export async function oauthGoogleLogin(): Promise<{ authorize_url: string }> {
  const { data } = await apiClient.get<{ authorize_url: string }>('/auth/oauth/google/login');
  return data;
}

export async function oauthGoogleCallback(code: string): Promise<TokenResponse> {
  const { data } = await apiClient.get<TokenResponse>('/auth/oauth/google/callback', {
    params: { code },
  });
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function refreshSession(): Promise<{ access_token: string; token_type: string }> {
  const { data } = await axios.post(
    `${apiClient.defaults.baseURL}/auth/refresh`,
    {},
    { withCredentials: true },
  );
  return data;
}

export async function bootstrapSession(): Promise<{ token: string; user: User }> {
  const refresh = await refreshSession();
  const { useAuthStore } = await import('../stores/authStore');
  useAuthStore.getState().setAccessToken(refresh.access_token);
  const user = await getMe();
  useAuthStore.getState().setUser(user);
  return { token: refresh.access_token, user };
}

export async function getInvitation(token: string): Promise<InvitationPreview> {
  const { data } = await apiClient.get<InvitationPreview>(`/auth/invitations/${token}`);
  return data;
}

export async function acceptInvitation(token: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/invitations/accept', { token, password });
  return data;
}

export async function requestPasswordRecovery(email: string): Promise<PasswordRecoveryResponse> {
  const { data } = await apiClient.post<PasswordRecoveryResponse>('/auth/password-recovery', { email });
  return data;
}

export async function resetPassword(token: string, password: string): Promise<void> {
  await apiClient.post('/auth/password-reset', { token, password });
}
