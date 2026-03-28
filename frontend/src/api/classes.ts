import apiClient from './client';
import type { ClassSummary, Subject } from '../types';

export async function listClasses(): Promise<ClassSummary[]> {
  const { data } = await apiClient.get<ClassSummary[]>('/classes');
  return data;
}

export async function listSubjects(classId: string): Promise<Subject[]> {
  const { data } = await apiClient.get<Subject[]>(`/classes/${classId}/subjects`);
  return data;
}

export async function createClass(body: { name: string; grade: number; year: number }): Promise<ClassSummary> {
  const { data } = await apiClient.post<ClassSummary>('/classes', body);
  return data;
}
