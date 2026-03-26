import { useStudents } from '../hooks/useStudents';
import { useFeedbacks } from '../hooks/useFeedbacks';
import { useCounselings } from '../hooks/useCounselings';
import { useAuthStore } from '../stores/authStore';

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const { data: students } = useStudents();
  const { data: feedbacks } = useFeedbacks();
  const { data: counselings } = useCounselings();

  const stats = [
    { label: '담당 학생 수', value: students?.length ?? '-' },
    { label: '피드백 수', value: feedbacks?.length ?? '-' },
    { label: '상담 기록 수', value: counselings?.length ?? '-' },
  ];

  const recentFeedbacks = (feedbacks ?? []).slice(-3).reverse();
  const recentCounselings = (counselings ?? []).slice(-3).reverse();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">대시보드</h1>
      {user && <p className="text-sm text-gray-500">{user.name} 선생님, 안녕하세요.</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="border rounded p-4 text-center bg-white">
            <div className="text-2xl font-bold text-indigo-600">{s.value}</div>
            <div className="text-sm text-gray-500 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border rounded p-4 space-y-2 bg-white">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">최근 피드백</h2>
            <a href="/feedbacks" className="text-xs text-indigo-600 hover:underline">전체 보기</a>
          </div>
          {recentFeedbacks.length === 0 ? (
            <p className="text-xs text-gray-400">없음</p>
          ) : (
            recentFeedbacks.map((fb) => (
              <p key={fb.id} className="text-xs text-gray-600 truncate">
                [{fb.category}] {fb.content}
              </p>
            ))
          )}
        </div>
        <div className="border rounded p-4 space-y-2 bg-white">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">최근 상담</h2>
            <a href="/counselings" className="text-xs text-indigo-600 hover:underline">전체 보기</a>
          </div>
          {recentCounselings.length === 0 ? (
            <p className="text-xs text-gray-400">없음</p>
          ) : (
            recentCounselings.map((cs) => (
              <p key={cs.id} className="text-xs text-gray-600 truncate">
                {cs.date} — {cs.content}
              </p>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
