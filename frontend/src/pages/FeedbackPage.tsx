import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import {
  useCreateFeedback,
  useDeleteFeedback,
  useFeedbacks,
  useUpdateFeedback,
} from '../hooks/useFeedbacks';
import StudentSelector from '../components/ui/StudentSelector';
import ClassSelector from '../components/classes/ClassSelector';
import { useStudents } from '../hooks/useStudents';
import type { Feedback, StudentSummary } from '../types';
import FeedbackHistoryModal from '../components/feedbacks/FeedbackHistoryModal';
import { Card, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import {
  TableCard,
  tableHeadClass,
  tableBodyClass,
  tableRowClass,
  thClass,
  tdClass,
} from '../components/ui/Table';

const fieldClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-clay-soft focus:outline-none focus:ring-2 focus:ring-clay-wash';
const labelClass = 'text-sm font-medium text-ink-soft';

const CATEGORIES: Feedback['category'][] = ['grade', 'behavior', 'attendance', 'attitude'];
const CATEGORY_LABEL: Record<Feedback['category'], string> = {
  grade: '성적',
  behavior: '행동',
  attendance: '출결',
  attitude: '태도',
};

interface FeedbackFormState {
  student_id: string;
  category: Feedback['category'];
  content: string;
  is_visible_to_student: boolean;
  is_visible_to_parent: boolean;
}

const EMPTY_FORM: FeedbackFormState = {
  student_id: '',
  category: 'grade',
  content: '',
  is_visible_to_student: false,
  is_visible_to_parent: false,
};

export default function FeedbackPage() {
  const { data: feedbacks, isLoading } = useFeedbacks();
  const createFb = useCreateFeedback();
  const updateFb = useUpdateFeedback();
  const deleteFb = useDeleteFeedback();

  const [form, setForm] = useState<FeedbackFormState>(EMPTY_FORM);
  const [classId, setClassId] = useState<string>(() => {
    try {
      return localStorage.getItem('selectedClassId') ?? '';
    } catch {
      return '';
    }
  });
  const { data: students } = useStudents(classId || undefined);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

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
      toast.error('내용을 입력해주세요.');
      return;
    }
    try {
      if (editingId) {
        await updateFb.mutateAsync({ id: editingId, body: form });
        toast.success('피드백이 수정되었습니다.');
      } else {
        await createFb.mutateAsync(form);
        toast.success('피드백이 저장되었습니다.');
      }
      resetForm();
    } catch {
      toast.error('저장에 실패했습니다. 다시 시도해주세요.');
    }
  };

  const handleEdit = (fb: Feedback) => {
    setForm({
      student_id: fb.student_id,
      category: fb.category,
      content: fb.content,
      is_visible_to_student: fb.is_visible_to_student,
      is_visible_to_parent: fb.is_visible_to_parent,
    });
    setEditingId(fb.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('삭제하시겠습니까?')) return;
    await deleteFb.mutateAsync(id);
  };

  function pickLatestBy<T extends { created_at: string; student_id: string }>(
    items: T[],
  ): Record<string, T | undefined> {
    const map: Record<string, T | undefined> = {};
    for (const item of items) {
      const prev = map[item.student_id];
      if (!prev || prev.created_at < item.created_at) map[item.student_id] = item;
    }
    return map;
  }

  const latestFeedbackByStudent = useMemo(
    () => pickLatestBy<Feedback>(feedbacks ?? []),
    [feedbacks],
  );
  const sortedStudents: StudentSummary[] = useMemo(() => {
    return (students ?? []).slice().sort((a, b) => a.student_number - b.student_number);
  }, [students]);
  // Show only students who currently have at least one feedback
  const studentsWithFeedback: StudentSummary[] = useMemo(() => {
    const idsWithFb = new Set((feedbacks ?? []).map((f) => f.student_id));
    return sortedStudents.filter((s) => idsWithFb.has(s.id));
  }, [sortedStudents, feedbacks]);

  const [historyStudentId, setHistoryStudentId] = useState<string | null>(null);

  function formatDate(dateStr?: string) {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toISOString().slice(0, 10);
    } catch {
      return dateStr;
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">피드백 관리</h1>
          <p className="mt-1 text-sm text-ink-soft">학급을 선택해 학생별 피드백을 작성·관리하세요.</p>
        </div>
        {classId && (
          <Button variant="primary" size="md" onClick={() => setShowForm((v) => !v)}>
            {showForm ? '닫기' : '+ 피드백 작성'}
          </Button>
        )}
      </div>

      {/* 학급 선택 (대시보드 및 폼 공용 상태) */}
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <span className={labelClass}>학급 선택</span>
          <ClassSelector
            value={classId}
            onChange={(id) => {
              setClassId(id);
              if (id) localStorage.setItem('selectedClassId', id);
              setForm((prev) => ({ ...prev, student_id: '' }));
              if (!id) {
                setShowForm(false);
                setEditingId(null);
              }
            }}
            disabled={!!editingId}
          />
        </div>
      </Card>

      {showForm && (
        <Card>
          <CardHeader title={editingId ? '피드백 수정' : '피드백 작성'} />
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                <label className={labelClass}>카테고리</label>
                <select
                  className={fieldClass}
                  value={form.category}
                  onChange={(e) =>
                    setForm({ ...form, category: e.target.value as Feedback['category'] })
                  }
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {CATEGORY_LABEL[c]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="space-y-1">
              <label className={labelClass}>내용</label>
              <textarea
                className={`${fieldClass} h-24`}
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                required
              />
            </div>
            <div className="flex gap-4 text-sm text-ink">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-clay"
                  checked={form.is_visible_to_student}
                  onChange={(e) => setForm({ ...form, is_visible_to_student: e.target.checked })}
                />
                학생 공개
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-clay"
                  checked={form.is_visible_to_parent}
                  onChange={(e) => setForm({ ...form, is_visible_to_parent: e.target.checked })}
                />
                학부모 공개
              </label>
            </div>
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

      {/* 학급 선택 시 학생 리스트 (번호/이름/최근 피드백 일자/피드백 내용/수정/삭제) */}
      {!classId ? (
        <Card className="text-sm text-ink-soft">학급을 먼저 선택하세요.</Card>
      ) : !students ? (
        <Card className="text-sm text-ink-soft">불러오는 중...</Card>
      ) : students.length === 0 ? (
        <Card className="text-sm text-ink-soft">학생이 없습니다.</Card>
      ) : studentsWithFeedback.length === 0 ? (
        <Card className="text-sm text-ink-soft">피드백이 없습니다.</Card>
      ) : (
        <TableCard>
          <table className="w-full text-sm">
            <thead className={tableHeadClass}>
              <tr>
                <th className={thClass}>번호</th>
                <th className={`${thClass} text-left`}>이름</th>
                <th className={thClass}>최근 피드백 일자</th>
                <th className={thClass}>피드백 내용</th>
                <th className={thClass}>삭제</th>
              </tr>
            </thead>
            <tbody className={tableBodyClass}>
              {studentsWithFeedback.map((s) => {
                const fb = latestFeedbackByStudent[s.id];
                return (
                  <tr key={s.id} className={tableRowClass}>
                    <td className={`${tdClass} text-muted`}>{s.student_number}</td>
                    <td className={`${tdClass} text-left`}>{s.name}</td>
                    <td className={tdClass}>{formatDate(fb?.created_at)}</td>
                    <td className={tdClass}>
                      {fb ? (
                        <Button type="button" variant="ghost" onClick={() => setHistoryStudentId(s.id)}>
                          내용 보기
                        </Button>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td className={tdClass}>
                      <Button
                        type="button"
                        variant="danger"
                        disabled={!fb}
                        onClick={() => fb && handleDelete(fb.id)}
                      >
                        삭제
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableCard>
      )}

      {historyStudentId && (
        <FeedbackHistoryModal
          studentLabel={(() => {
            const st = (students ?? []).find((x) => x.id === historyStudentId);
            return st ? `${st.student_number}번 ${st.name}` : '학생';
          })()}
          items={(feedbacks ?? []).filter((x) => x.student_id === historyStudentId)}
          onEdit={(fb) => {
            handleEdit(fb);
            setHistoryStudentId(null);
          }}
          onClose={() => setHistoryStudentId(null)}
        />
      )}
    </div>
  );
}
