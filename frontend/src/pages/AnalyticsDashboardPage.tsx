import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listClasses, listSubjects } from '../api/classes';
import { listStudents } from '../api/users';
import TeacherDashboardCards from '../components/analytics/TeacherDashboardCards';
import ClassDistributionChart from '../components/analytics/ClassDistributionChart';
import StudentOverviewPanel from '../components/analytics/StudentOverviewPanel';

export default function AnalyticsDashboardPage() {
  const [classId, setClassId] = useState<string>('');
  const [subjectId, setSubjectId] = useState<string>('');
  const [studentQuery, setStudentQuery] = useState<string>('');
  const [studentId, setStudentId] = useState<string>('');

  const classesQuery = useQuery({
    queryKey: ['classes'],
    queryFn: () => listClasses(),
  });
  const subjectsQuery = useQuery({
    queryKey: ['subjects', classId],
    queryFn: () => listSubjects(classId),
    enabled: Boolean(classId),
  });
  const studentsQuery = useQuery({
    queryKey: ['students', { classId: classId || undefined }],
    queryFn: () => listStudents(classId || undefined),
  });

  // Reset dependent selectors when class changes
  useEffect(() => {
    setSubjectId('');
    setStudentId('');
  }, [classId]);

  const filteredStudents = (studentsQuery.data ?? []).filter((s) =>
    studentQuery.trim() === '' ? true : s.name.includes(studentQuery.trim()),
  );

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">분석 대시보드</h1>

      <section>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">담당 학급 요약</h2>
        <TeacherDashboardCards />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">학급 점수 분포</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          <select
            className="border rounded px-2 py-1"
            value={classId}
            onChange={(e) => setClassId(e.target.value)}
            aria-label="학급 선택"
          >
            <option value="">학급 선택</option>
            {(classesQuery.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="border rounded px-2 py-1"
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            aria-label="과목 선택"
            disabled={!classId}
          >
            <option value="">과목 선택</option>
            {(subjectsQuery.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <ClassDistributionChart classId={classId} subjectId={subjectId} />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">학생 상세 분석</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          <input
            className="border rounded px-2 py-1"
            placeholder="학생 이름 검색"
            value={studentQuery}
            onChange={(e) => setStudentQuery(e.target.value)}
            aria-label="학생 이름 검색"
          />
          <select
            className="border rounded px-2 py-1"
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            aria-label="학생 선택"
          >
            <option value="">학생 선택</option>
            {filteredStudents.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.student_number}번)
              </option>
            ))}
          </select>
        </div>
        <StudentOverviewPanel studentId={studentId || undefined} />
      </section>
    </div>
  );
}
