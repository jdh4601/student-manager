import apiClient from './client';
import type { Counseling } from '../types';

export async function listCounselings(studentId?: string): Promise<Counseling[]> {
  const { data } = await apiClient.get<Counseling[]>('/counselings', {
    params: studentId ? { student_id: studentId } : {},
  });
  return data;
}

export async function createCounseling(body: {
  student_id: string;
  date: string;
  content: string;
  next_plan: string;
  is_shared: boolean;
}): Promise<Counseling> {
  const { data } = await apiClient.post<Counseling>('/counselings', body);
  return data;
}

export async function updateCounseling(
  id: string,
  body: {
    student_id: string;
    date: string;
    content: string;
    next_plan: string;
    is_shared: boolean;
  },
): Promise<Counseling> {
  const { data } = await apiClient.put<Counseling>(`/counselings/${id}`, body);
  return data;
}
