import apiClient from './client';

export interface ChatRequest {
  thread_id?: string | null;
  message: string;
}

export interface StudentRef {
  id: string;
  name: string;
}

export interface ChatResponse {
  thread_id: string;
  reply: string;
  referenced_students: StudentRef[];
}

export async function postChat(body: ChatRequest): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>('/chat', body);
  return data;
}
