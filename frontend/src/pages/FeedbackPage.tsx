import { useState } from 'react';
import {
  useCreateFeedback,
  useDeleteFeedback,
  useFeedbacks,
  useUpdateFeedback,
} from '../hooks/useFeedbacks';
import type { Feedback } from '../types';

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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setShowForm(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.student_id.trim() || !form.content.trim()) return;
    if (editingId) {
      await updateFb.mutateAsync({ id: editingId, body: form });
    } else {
      await createFb.mutateAsync(form);
    }
    resetForm();
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">피드백 관리</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="px-3 py-1 bg-indigo-600 text-white rounded text-sm"
        >
          {showForm ? '닫기' : '+ 피드백 작성'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="border rounded p-4 space-y-3 bg-gray-50">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm text-gray-600">학생 ID</label>
              <input
                className="border w-full p-1 text-sm"
                value={form.student_id}
                onChange={(e) => setForm({ ...form, student_id: e.target.value })}
                placeholder="학생 UUID"
                required
              />
            </div>
            <div>
              <label className="text-sm text-gray-600">카테고리</label>
              <select
                className="border w-full p-1 text-sm"
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
          <div>
            <label className="text-sm text-gray-600">내용</label>
            <textarea
              className="border w-full p-1 text-sm h-24"
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              required
            />
          </div>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={form.is_visible_to_student}
                onChange={(e) => setForm({ ...form, is_visible_to_student: e.target.checked })}
              />
              학생 공개
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={form.is_visible_to_parent}
                onChange={(e) => setForm({ ...form, is_visible_to_parent: e.target.checked })}
              />
              학부모 공개
            </label>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-3 py-1 bg-indigo-600 text-white rounded text-sm">
              {editingId ? '수정' : '저장'}
            </button>
            <button
              type="button"
              onClick={resetForm}
              className="px-3 py-1 bg-gray-300 rounded text-sm"
            >
              취소
            </button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div>불러오는 중...</div>
      ) : (feedbacks ?? []).length === 0 ? (
        <div className="text-gray-500 text-sm">피드백이 없습니다.</div>
      ) : (
        <div className="space-y-2">
          {(feedbacks ?? []).map((fb) => (
            <div key={fb.id} className="border rounded p-3 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">
                  {CATEGORY_LABEL[fb.category]}
                </span>
                <div className="flex gap-2 text-xs">
                  {fb.is_visible_to_student && <span className="text-green-600">학생공개</span>}
                  {fb.is_visible_to_parent && <span className="text-blue-600">학부모공개</span>}
                </div>
              </div>
              <p className="text-sm">{fb.content}</p>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => handleEdit(fb)}
                  className="text-xs text-indigo-600 hover:underline"
                >
                  수정
                </button>
                <button
                  onClick={() => handleDelete(fb.id)}
                  className="text-xs text-red-500 hover:underline"
                >
                  삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
