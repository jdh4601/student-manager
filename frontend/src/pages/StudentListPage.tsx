import { useEffect, useMemo, useState } from 'react';
import { listClasses } from '../api/classes';
import { useStudents } from '../hooks/useStudents';
import StudentList from '../components/students/StudentList';
import ExcelUploadModal from '../components/students/ExcelUploadModal';
import StudentCreateForm from '../components/students/StudentCreateForm';
import type { ClassSummary } from '../types';
import { exportStudentsToExcel } from '../utils/exportHelpers';

export default function StudentListPage() {
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [classId, setClassId] = useState<string | undefined>(undefined);
  const { data: students, isLoading } = useStudents(classId);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  const currentClassLabel = useMemo(() => {
    const c = classes.find((x) => x.id === classId);
    return c ? `${c.year}학년도 ${c.grade}학년 ${c.name}` : undefined;
  }, [classes, classId]);

  useEffect(() => {
    (async () => {
      try {
        const cls = await listClasses();
        setClasses(cls);
        if (cls.length > 0 && !classId) setClassId(cls[0].id);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">학생 목록</h1>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2 items-center">
          <label className="text-sm text-gray-600">학급 선택</label>
          <select className="border p-1" value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>{`${c.year}학년도 ${c.grade}학년 ${c.name}`}</option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <button
            className="px-3 py-1 rounded text-sm border"
            onClick={() => setShowCreateForm(true)}
            disabled={!classId}
          >
            학생 추가
          </button>
          <button
            className="px-3 py-1 rounded text-sm border"
            onClick={() => setShowUploadModal(true)}
            disabled={!classId}
          >
            엑셀로 등록
          </button>
          <button
            className="px-3 py-1 rounded text-sm border"
            disabled={!students || students.length === 0}
            onClick={async () => {
              if (students) await exportStudentsToExcel(students, currentClassLabel);
            }}
          >
            Excel로 내보내기
          </button>
        </div>
      </div>
      {isLoading ? (
        <div>불러오는 중...</div>
      ) : students ? (
        <StudentList students={students} />
      ) : (
        <div>학생이 없습니다.</div>
      )}
      {showUploadModal && classId && (
        <ExcelUploadModal classId={classId} onClose={() => setShowUploadModal(false)} />
      )}
      {showCreateForm && classId && (
        <StudentCreateForm classId={classId} onClose={() => setShowCreateForm(false)} />
      )}
    </div>
  );
}
