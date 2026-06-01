import { useEffect, useMemo, useState } from 'react';
import { toast } from 'react-hot-toast';
import { listClasses, deleteClass, listSubjects } from '../api/classes';
import { useStudents } from '../hooks/useStudents';
import StudentList from '../components/students/StudentList';
import BulkInviteModal from '../components/students/BulkInviteModal';
import StudentCreateForm from '../components/students/StudentCreateForm';
import ClassCreateModal from '../components/classes/ClassCreateModal';
import type { ClassSummary } from '../types';
import { exportStudentsToCSV, exportStudentsToExcel } from '../utils/exportHelpers';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

const iconProps = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
};

const PlusIcon = () => (
  <svg {...iconProps}><path d="M12 5v14M5 12h14" /></svg>
);
const TrashIcon = () => (
  <svg {...iconProps}><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" /></svg>
);
const UserPlusIcon = () => (
  <svg {...iconProps}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M19 8v6M22 11h-6" /></svg>
);
const UsersIcon = () => (
  <svg {...iconProps}><path d="M17 21v-2a4 4 0 0 0-3-3.87M13 3.13a4 4 0 0 1 0 7.75M7 21v-2a4 4 0 0 1 4-4h0a4 4 0 0 1 4 4v2" /><circle cx="9" cy="7" r="4" /></svg>
);
const CsvIcon = () => (
  <svg {...iconProps}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h2M8 17h6" /></svg>
);
const ExcelIcon = () => (
  <svg {...iconProps}><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M9 3v18M15 3v18" /></svg>
);

export default function StudentListPage() {
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [classId, setClassId] = useState<string | undefined>(() => {
    try {
      return localStorage.getItem('selectedClassId') || undefined;
    } catch {
      return undefined;
    }
  });
  // Ensure selected classId is valid; default to first available
  useEffect(() => {
    if (classes.length === 0) return;
    const exists = classId && classes.some((c) => c.id === classId);
    if (!exists) {
      const next = classes[0]?.id;
      setClassId(next);
      try { if (next) localStorage.setItem('selectedClassId', next); } catch {}
    }
  }, [classes]);
  const effectiveClassId = useMemo(() => classId, [classId]);
  const { data: students, isLoading } = useStudents(effectiveClassId);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showClassCreate, setShowClassCreate] = useState(false);
  const [showPendingOnly, setShowPendingOnly] = useState(false);
  const [showExpiringSoonOnly, setShowExpiringSoonOnly] = useState(false);

  const currentClassLabel = useMemo(() => {
    const c = classes.find((x) => x.id === effectiveClassId);
    return c ? `${c.year}학년도 ${c.grade}학년 ${c.name}` : undefined;
  }, [classes, effectiveClassId]);

  const nextStudentNumber = useMemo(() => {
    if (!students || students.length === 0) return 1;
    return Math.max(...students.map((s) => s.student_number)) + 1;
  }, [students]);

  const filteredStudents = useMemo(() => {
    const source = students || [];
    return source.filter((student) => {
      if (showPendingOnly && student.invite_status !== 'pending') return false;
      if (showExpiringSoonOnly) {
        const expiresAt = student.invite_expires_at ? new Date(student.invite_expires_at) : null;
        const now = new Date();
        const diffDays = expiresAt ? (expiresAt.getTime() - now.getTime()) / (1000 * 60 * 60 * 24) : Infinity;
        if (student.invite_status !== 'pending' || diffDays < 0 || diffDays > 7) return false;
      }
      return true;
    });
  }, [showExpiringSoonOnly, showPendingOnly, students]);

  useEffect(() => {
    (async () => {
      try {
        const cls = await listClasses();
        setClasses(cls);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">학생 목록</h1>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2 items-center">
          <label className="text-sm font-medium text-ink-soft">학급 선택</label>
          {classes.length > 0 ? (
            <select
              className="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-clay-soft focus:outline-none focus:ring-2 focus:ring-clay-wash"
              value={effectiveClassId || ''}
              onChange={(e) => { setClassId(e.target.value); try { localStorage.setItem('selectedClassId', e.target.value); } catch {} }}
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id}>{`${c.year}학년도 ${c.grade}학년 ${c.name}`}</option>
              ))}
            </select>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted">학급이 없습니다.</span>
              <Button variant="ghost" onClick={() => setShowClassCreate(true)}>학급 만들기</Button>
            </div>
          )}
          {classes.length > 0 && (
            <Button variant="ghost" icon={<PlusIcon />} title="학급 추가" aria-label="학급 추가" onClick={() => setShowClassCreate(true)}>
              학급
            </Button>
          )}
          <Button
            variant="danger"
            icon={<TrashIcon />}
            title="학급 삭제"
            aria-label="학급 삭제"
            disabled={!effectiveClassId}
            onClick={async () => {
              if (!effectiveClassId) return;
              const target = classes.find((c) => c.id === effectiveClassId);
              const label = target ? `${target.year}학년도 ${target.grade}학년 ${target.name}` : '이 학급';
              // 데이터 존재 여부 확인 (학생/과목)
              let hasData = false;
              try {
                const subs = await listSubjects(effectiveClassId);
                hasData = (students && students.length > 0) || (subs && subs.length > 0);
              } catch {
                hasData = !!(students && students.length > 0);
              }
              const confirmMsg = hasData
                ? `${label}에 데이터가 있습니다.\n정말로 삭제하시겠습니까?\n(학생/과목/성적/상담/피드백 등이 함께 삭제됩니다)`
                : `${label}을(를) 삭제하시겠습니까?`;
              if (!confirm(confirmMsg)) return;
              try {
                await deleteClass(effectiveClassId, { force: hasData });
                const next = classes.filter((c) => c.id !== effectiveClassId);
                setClasses(next);
                setClassId(next.length > 0 ? next[0].id : undefined);
                toast.success('학급을 삭제했습니다.');
              } catch (e: any) {
                const code = e?.response?.data?.code;
                if (code === 'CLASS_NOT_EMPTY') toast.error('학생/과목이 있어 삭제할 수 없습니다.');
                else toast.error('삭제 중 오류가 발생했습니다.');
              }
            }}
          >
            삭제
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            icon={<UserPlusIcon />}
            aria-label="학생 초대"
            title="학생 초대"
            onClick={() => {
              if (!effectiveClassId) {
                toast.error('학급을 먼저 선택하세요.');
                return;
              }
              setShowCreateForm(true);
            }}
          >
            초대
          </Button>
          <Button
            variant="ghost"
            icon={<UsersIcon />}
            aria-label="여러 명 초대"
            title="여러 명 초대"
            onClick={() => {
              // Require a valid class in the current list
              if (!effectiveClassId || !classes.some((c) => c.id === effectiveClassId)) {
                toast.error('학급을 먼저 선택하세요.');
                return;
              }
              setShowUploadModal(true);
            }}
          >
            여러 명
          </Button>
          <div className="mx-1 h-6 w-px self-center bg-line" aria-hidden />
          <Button
            variant="ghost"
            icon={<CsvIcon />}
            aria-label="CSV로 내보내기"
            title="CSV로 내보내기"
            disabled={!students || students.length === 0}
            onClick={() => {
              if (students) exportStudentsToCSV(students, currentClassLabel);
            }}
          />
          <Button
            variant="ghost"
            icon={<ExcelIcon />}
            className="text-positive"
            aria-label="엑셀로 내보내기"
            title="엑셀로 내보내기"
            disabled={!students || students.length === 0}
            onClick={async () => {
              if (students) await exportStudentsToExcel(students, currentClassLabel);
            }}
          />
        </div>
      </div>
      <Card flush className="flex flex-wrap items-center gap-4 p-4">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-clay" checked={showPendingOnly} onChange={(e) => setShowPendingOnly(e.target.checked)} aria-label="대기만 보기" />
          대기만 보기
        </label>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-clay" checked={showExpiringSoonOnly} onChange={(e) => setShowExpiringSoonOnly(e.target.checked)} aria-label="7일 내 만료 예정" />
          7일 내 만료 예정
        </label>
      </Card>
      {isLoading ? (
        <Card className="text-sm text-ink-soft">불러오는 중...</Card>
      ) : students ? (
        <StudentList students={filteredStudents} />
      ) : (
        <Card className="text-sm text-ink-soft">학생이 없습니다.</Card>
      )}
      {showUploadModal && effectiveClassId && (
        <BulkInviteModal classId={effectiveClassId} onClose={() => setShowUploadModal(false)} />
      )}
      {showCreateForm && effectiveClassId && (
        <StudentCreateForm classId={effectiveClassId} nextStudentNumber={nextStudentNumber} onClose={() => setShowCreateForm(false)} />
      )}
      {showClassCreate && (
        <ClassCreateModal
          onClose={() => setShowClassCreate(false)}
          onCreated={(c) => {
            setClasses((prev) => [...prev, c]);
            setClassId(c.id);
          }}
        />
      )}
    </div>
  );
}
