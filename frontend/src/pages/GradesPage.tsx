import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getStudent } from '../api/students';
import { listSemesters } from '../api/semesters';
import { listSubjects } from '../api/classes';
import { useGrades, useUpsertGrade } from '../hooks/useGrades';
import GradeTable from '../components/grades/GradeTable';
import GradeRadarChart from '../components/grades/RadarChart';
import type { Semester, Subject } from '../types';

type Tab = 'table' | 'chart';

export default function GradesPage() {
  const { studentId } = useParams();
  const [semesterId, setSemesterId] = useState<string>('');
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [tab, setTab] = useState<Tab>('table');
  const { data: grades } = useGrades(studentId || '', semesterId || undefined);
  const upsert = useUpsertGrade(studentId || '', semesterId || undefined);

  useEffect(() => {
    (async () => {
      if (!studentId) return;
      setLoading(true);
      try {
        const [s, sems] = await Promise.all([getStudent(studentId), listSemesters()]);
        setSemesters(sems);
        const sid = sems[0]?.id || '';
        setSemesterId((prev) => prev || sid);
        const subjs = await listSubjects(s.class_id);
        setSubjects(subjs);
      } finally {
        setLoading(false);
      }
    })();
  }, [studentId]);

  const handleUpsert = async (args: { gradeId?: string; subject_id: string; score: number }) => {
    if (!studentId || !semesterId) return;
    await upsert.mutateAsync({
      gradeId: args.gradeId,
      student_id: studentId,
      subject_id: args.subject_id,
      semester_id: semesterId,
      score: args.score,
    });
  };

  if (!studentId) return <div>잘못된 접근입니다.</div>;
  if (loading) return <div>불러오는 중...</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">성적 관리</h1>

      <div className="flex gap-2 items-center">
        <label className="text-sm text-gray-600">학기</label>
        <select
          className="border p-1"
          value={semesterId}
          onChange={(e) => setSemesterId(e.target.value)}
        >
          {semesters.map((sm) => (
            <option key={sm.id} value={sm.id}>{`${sm.year}년 ${sm.term}학기`}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setTab('table')}
          className={`px-4 py-1 rounded text-sm ${tab === 'table' ? 'bg-indigo-600 text-white' : 'bg-gray-200'}`}
        >
          성적표
        </button>
        <button
          onClick={() => setTab('chart')}
          className={`px-4 py-1 rounded text-sm ${tab === 'chart' ? 'bg-indigo-600 text-white' : 'bg-gray-200'}`}
        >
          레이더 차트
        </button>
      </div>

      {tab === 'table' ? (
        <GradeTable
          subjects={subjects}
          grades={grades || []}
          semesterId={semesterId}
          studentId={studentId}
          onUpsert={handleUpsert}
        />
      ) : (
        <GradeRadarChart subjects={subjects} grades={grades || []} />
      )}
    </div>
  );
}
