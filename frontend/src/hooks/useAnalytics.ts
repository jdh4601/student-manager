import { useQuery } from '@tanstack/react-query';
import {
  getClassDistribution,
  getStudentOverview,
  getTeacherDashboard,
} from '../api/analytics';

export const ANALYTICS_QUERY_KEYS = {
  teacherDashboard: (semesterId?: string) =>
    ['analytics', 'teacher-dashboard', semesterId ?? null] as const,
  classDistribution: (classId: string, subjectId: string, semesterId?: string) =>
    [
      'analytics',
      'class-distribution',
      classId,
      subjectId,
      semesterId ?? null,
    ] as const,
  studentOverview: (studentId: string, semesterId?: string) =>
    ['analytics', 'student-overview', studentId, semesterId ?? null] as const,
};

export function useTeacherDashboard(semesterId?: string) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.teacherDashboard(semesterId),
    queryFn: () => getTeacherDashboard(semesterId),
  });
}

export function useClassDistribution(
  classId: string | undefined,
  subjectId: string | undefined,
  semesterId?: string,
) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.classDistribution(
      classId ?? '',
      subjectId ?? '',
      semesterId,
    ),
    queryFn: () => getClassDistribution(classId!, subjectId!, semesterId),
    enabled: Boolean(classId && subjectId),
  });
}

export function useStudentOverview(
  studentId: string | undefined,
  semesterId?: string,
) {
  return useQuery({
    queryKey: ANALYTICS_QUERY_KEYS.studentOverview(studentId ?? '', semesterId),
    queryFn: () => getStudentOverview(studentId!, semesterId),
    enabled: Boolean(studentId),
  });
}
