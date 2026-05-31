import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  useCounselings,
  useCreateCounseling,
  useUpdateCounseling,
  useDeleteCounseling,
} from '../hooks/useCounselings';
import { useStudents } from '../hooks/useStudents';
import StudentSelector from '../components/ui/StudentSelector';
import ClassSelector from '../components/classes/ClassSelector';
import type { Counseling } from '../types';
import CounselingDetailModal from '../components/counselings/CounselingDetailModal';
import { useAuthStore } from '../stores/authStore';
import { Card, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const fieldClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-clay-soft focus:outline-none focus:ring-2 focus:ring-clay-wash';
const labelClass = 'text-sm font-medium text-ink-soft';

interface CounselingFormState {
  student_id: string;
  date: string;
  content: string;
  next_plan: string;
  is_shared: boolean;
}

const EMPTY_FORM: CounselingFormState = {
  student_id: '',
  date: new Date().toISOString().slice(0, 10),
  content: '',
  next_plan: '',
  is_shared: true,
};

export default function CounselingPage() {
  const [searchParams] = useSearchParams();
  const linkedStudentId = searchParams.get('studentId') ?? undefined;
  const createCs = useCreateCounseling();
  const updateCs = useUpdateCounseling();
  const deleteCs = useDeleteCounseling();
  const { data: allStudents } = useStudents();
  const me = useAuthStore((s) => s.user);

  const [form, setForm] = useState<CounselingFormState>(EMPTY_FORM);
  const [classId, setClassId] = useState<string>(() => {
    try {
      return localStorage.getItem('selectedClassId') ?? '';
    } catch {
      return '';
    }
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [filterClassId, setFilterClassId] = useState<string>('');
  const [studentSearch, setStudentSearch] = useState<string>('');
  const [teacherSearch, setTeacherSearch] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const { data: filterStudents } = useStudents(filterClassId || undefined);
  const [selectedCounselingId, setSelectedCounselingId] = useState<string | null>(null);
  const { data: counselings, isLoading } = useCounselings({
    student_id: linkedStudentId,
    student_name: linkedStudentId ? undefined : studentSearch || undefined,
    teacher_name: teacherSearch || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    include_shared: true,
  });

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setShowForm(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.student_id) {
      toast.error('학생을 선택해주세요.');
      return;
    }
    if (!form.content.trim()) {
      toast.error('상담 내용을 입력해주세요.');
      return;
    }
    try {
      if (editingId) {
        await updateCs.mutateAsync({ id: editingId, body: form });
        toast.success('상담 기록이 수정되었습니다.');
      } else {
        await createCs.mutateAsync(form);
        toast.success('상담 기록이 저장되었습니다.');
      }
      resetForm();
    } catch {
      toast.error('저장에 실패했습니다. 다시 시도해주세요.');
    }
  };

  const handleEdit = (cs: Counseling) => {
    setForm({
      student_id: cs.student_id,
      date: cs.date,
      content: cs.content,
      next_plan: cs.next_plan ?? '',
      is_shared: cs.is_shared,
    });
    setEditingId(cs.id);
    setShowForm(true);
  };

  function getStudentName(studentId: string): string {
    return counselings?.find((item) => item.student_id === studentId)?.student_name
      ?? allStudents?.find((s) => s.id === studentId)?.name
      ?? '알 수 없음';
  }

  const handleDelete = async (id: string) => {
    if (!confirm('상담 기록을 삭제하시겠습니까?')) return;
    try {
      await deleteCs.mutateAsync(id);
      toast.success('상담 기록이 삭제되었습니다.');
    } catch (e: any) {
      const code = e?.response?.data?.code;
      const msg = code === 'FORBIDDEN' ? '삭제 권한이 없습니다.' : '삭제에 실패했습니다.';
      console.error('Counseling delete failed', e?.response?.status, code, e?.response?.data);
      toast.error(msg);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">상담 기록</h1>
          <p className="mt-1 text-sm text-ink-soft">학생 상담 내역을 기록하고 검색하세요.</p>
        </div>
        <Button variant="primary" size="md" onClick={() => setShowForm((v) => !v)}>
          {showForm ? '닫기' : '+ 상담 기록 추가'}
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader title={editingId ? '상담 기록 수정' : '상담 기록 추가'} />
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1">
                <label className={labelClass}>학급</label>
                <ClassSelector
                  value={classId}
                  onChange={(id) => {
                    setClassId(id);
                    if (id) try { localStorage.setItem('selectedClassId', id); } catch {}
                    setForm((prev) => ({ ...prev, student_id: '' }));
                  }}
                  disabled={!!editingId}
                  required
                />
              </div>
              <div className="space-y-1">
                <label className={labelClass}>학생</label>
                <StudentSelector
                  value={form.student_id}
                  onChange={(id) => setForm({ ...form, student_id: id })}
                  classId={classId || undefined}
                  disabled={!!editingId || !classId}
                  required
                />
              </div>
              <div className="space-y-1">
                <label className={labelClass}>상담 날짜</label>
                <input
                  type="date"
                  className={fieldClass}
                  value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })}
                  required
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className={labelClass}>상담 내용</label>
              <textarea
                className={`${fieldClass} h-24`}
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                required
              />
            </div>
            <div className="space-y-1">
              <label className={labelClass}>다음 상담 계획</label>
              <textarea
                className={`${fieldClass} h-16`}
                value={form.next_plan}
                onChange={(e) => setForm({ ...form, next_plan: e.target.value })}
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                className="h-4 w-4 accent-clay"
                checked={form.is_shared}
                onChange={(e) => setForm({ ...form, is_shared: e.target.checked })}
              />
              교사 간 공유
            </label>
            <div className="flex gap-2">
              <Button type="submit" variant="primary">
                {editingId ? '수정' : '저장'}
              </Button>
              <Button type="button" variant="ghost" onClick={resetForm}>
                취소
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* 필터/리스트: 작성 중에는 숨김 */}
      {!showForm && (
      <>
      <Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-5 md:items-end">
          <div className="space-y-1">
            <label className={labelClass} htmlFor="counseling-class-filter">학급 필터</label>
            <ClassSelector
              value={filterClassId}
              onChange={(id) => {
                setFilterClassId(id);
              }}
            />
          </div>
          <div className="space-y-1">
            <label className={labelClass} htmlFor="counseling-student-search">학생 이름 검색</label>
            <input
              id="counseling-student-search"
              type="text"
              placeholder="이름으로 검색"
              className={fieldClass}
              value={studentSearch}
              onChange={(e) => setStudentSearch(e.target.value)}
              disabled={!!linkedStudentId}
            />
          </div>
          <div className="space-y-1">
            <label className={labelClass} htmlFor="counseling-teacher-search">작성 교사</label>
            <input
              id="counseling-teacher-search"
              type="text"
              placeholder="교사 이름"
              className={fieldClass}
              value={teacherSearch}
              onChange={(e) => setTeacherSearch(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className={labelClass} htmlFor="counseling-start-date">시작일</label>
            <input
              id="counseling-start-date"
              type="date"
              className={fieldClass}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className={labelClass} htmlFor="counseling-end-date">종료일</label>
            <input
              id="counseling-end-date"
              type="date"
              className={fieldClass}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          {(filterClassId || studentSearch || teacherSearch || startDate || endDate) && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => { setFilterClassId(''); setStudentSearch(''); setTeacherSearch(''); setStartDate(''); setEndDate(''); }}
            >
              필터 초기화
            </Button>
          )}
        </div>
      </Card>

      {isLoading ? (
        <Card className="text-sm text-ink-soft">불러오는 중...</Card>
      ) : (counselings ?? []).length === 0 ? (
        <Card className="text-sm text-ink-soft">상담 기록이 없습니다.</Card>
      ) : (
        <div className="space-y-3">
          {(() => {
            let list = counselings ?? [];
            // 1) Class filter narrows by students of the class
            if (filterClassId && filterStudents) {
              const ids = new Set((filterStudents ?? []).map((s) => s.id));
              list = list.filter((cs) => ids.has(cs.student_id));
            }
            return list;
          })().map((cs) => (
            <Card
              key={cs.id}
              className="cursor-pointer space-y-1 transition-shadow hover:shadow-card-hover"
              onClick={() => setSelectedCounselingId(cs.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-ink">{cs.student_name ?? getStudentName(cs.student_id)}</span>
                  <span className="text-xs text-muted">{cs.date}</span>
                  <span className="text-xs text-muted">작성: {cs.teacher_name ?? '알 수 없음'}</span>
                </div>
                {cs.is_shared && <Badge variant="positive">공유됨</Badge>}
              </div>
              <p className="text-sm text-ink">{cs.content}</p>
              {cs.next_plan && (
                <p className="text-xs text-ink-soft">다음 계획: {cs.next_plan}</p>
              )}
            </Card>
          ))}
        </div>
      )}
      </>
      )}

      {selectedCounselingId && (
        (() => {
          const cs = (counselings ?? []).find((x) => x.id === selectedCounselingId);
          if (!cs) return null;
          return (
            <CounselingDetailModal
              counseling={cs}
              studentName={getStudentName(cs.student_id)}
              canEdit={cs.teacher_id === (me?.id || '')}
              onEdit={(c) => {
                setSelectedCounselingId(null);
                handleEdit(c);
              }}
              onDelete={(id) => {
                setSelectedCounselingId(null);
                handleDelete(id);
              }}
              onClose={() => setSelectedCounselingId(null)}
            />
          );
        })()
      )}
    </div>
  );
}
