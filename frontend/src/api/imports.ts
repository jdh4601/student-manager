import apiClient from './client';

export async function uploadStudentsXlsx(classId: string, file: Blob) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<{ created: number; skipped: number; errors: any[] }>(
    '/import/students/xlsx',
    form,
    {
      params: { class_id: classId },
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
  return data;
}

export async function uploadGradesXlsx(classId: string, semesterId: string, file: Blob) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<{ created: number; skipped: number; errors: any[] }>(
    '/import/grades/xlsx',
    form,
    {
      params: { class_id: classId, semester_id: semesterId },
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
  return data;
}

export function getStudentTemplateUrl() {
  return `${apiClient.defaults.baseURL}/import/students/template`;
}

export function getGradeTemplateUrl(classId: string) {
  const u = new URL(`${apiClient.defaults.baseURL}/import/grades/template`, window.location.origin);
  u.searchParams.set('class_id', classId);
  return u.pathname + u.search; // keep relative path under same origin
}

