import apiClient from './client';

export interface OverallSummary {
  avg_score: number | null;
  total_score: number | null;
  subject_count: number;
  attendance_present_rate: number | null;
  feedback_count: number;
}

export interface SubjectOverview {
  subject_id: string;
  name: string;
  avg_score: number | null;
  max_score: number | null;
  min_score: number | null;
  latest_rank: number | null;
  sample_count: number;
}

export interface StudentOverviewResponse {
  overall: OverallSummary | null;
  subjects: SubjectOverview[];
}

export interface DistributionBucket {
  range: string;
  count: number;
}

export interface ClassDistributionResponse {
  buckets: DistributionBucket[];
  total_students: number;
  mean: number | null;
  median: number | null;
}

export interface TeacherDashboardClass {
  class_id: string;
  name: string;
  student_count: number;
  avg_score: number | null;
  attendance_rate: number | null;
}

export interface TeacherDashboardResponse {
  classes: TeacherDashboardClass[];
  recent_feedbacks_count: number;
  pending_counselings_count: number;
}

export async function getTeacherDashboard(
  semesterId?: string,
): Promise<TeacherDashboardResponse> {
  const { data } = await apiClient.get<TeacherDashboardResponse>(
    '/analytics/teachers/me/dashboard',
    { params: { semester_id: semesterId } },
  );
  return data;
}

export async function getClassDistribution(
  classId: string,
  subjectId: string,
  semesterId?: string,
): Promise<ClassDistributionResponse> {
  const { data } = await apiClient.get<ClassDistributionResponse>(
    `/analytics/classes/${classId}/distribution`,
    { params: { subject_id: subjectId, semester_id: semesterId } },
  );
  return data;
}

export async function getStudentOverview(
  studentId: string,
  semesterId?: string,
): Promise<StudentOverviewResponse> {
  const { data } = await apiClient.get<StudentOverviewResponse>(
    `/analytics/students/${studentId}/overview`,
    { params: { semester_id: semesterId } },
  );
  return data;
}
