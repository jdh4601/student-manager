import apiClient from './client';
import type { Attendance, SpecialNote, StudentDetail } from '../types';

export async function getStudent(id: string): Promise<StudentDetail> {
  const { data } = await apiClient.get<StudentDetail>(`/students/${id}`);
  return data;
}

export async function updateStudent(
  id: string,
  payload: Partial<Pick<StudentDetail, 'name' | 'student_number' | 'birth_date' | 'gender' | 'phone' | 'address'>>,
): Promise<StudentDetail> {
  const { data } = await apiClient.put<StudentDetail>(`/students/${id}`, payload);
  return data;
}

export async function listAttendance(studentId: string, params?: { start_date?: string; end_date?: string }): Promise<Attendance[]> {
  const { data } = await apiClient.get<Attendance[]>(`/students/${studentId}/attendance`, { params });
  return data;
}

export async function createAttendance(studentId: string, body: { date: string; status: Attendance['status']; note?: string }): Promise<Attendance> {
  const { data } = await apiClient.post<Attendance>(`/students/${studentId}/attendance`, body);
  return data;
}

export async function listSpecialNotes(studentId: string): Promise<SpecialNote[]> {
  const { data } = await apiClient.get<SpecialNote[]>(`/students/${studentId}/special-notes`);
  return data;
}

export async function createSpecialNote(studentId: string, body: { content: string }): Promise<SpecialNote> {
  const { data } = await apiClient.post<SpecialNote>(`/students/${studentId}/special-notes`, body);
  return data;
}

export async function createStudent(
  classId: string,
  body: {
    name: string;
    student_number: number;
    birth_date?: string;
    gender?: string;
    phone?: string;
    address?: string;
  },
): Promise<StudentDetail> {
  const { data } = await apiClient.post<StudentDetail>(`/classes/${classId}/students`, body);
  return data;
}
