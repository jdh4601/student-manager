import { useTeacherDashboard } from '../../hooks/useAnalytics';

interface Props {
  semesterId?: string;
}

function formatScore(v: number | null): string {
  return v == null ? '—' : v.toFixed(1);
}

function formatRate(v: number | null): string {
  return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

export default function TeacherDashboardCards({ semesterId }: Props) {
  const { data, isLoading, error } = useTeacherDashboard(semesterId);

  if (isLoading) {
    return <p className="text-sm text-gray-500">분석 데이터를 불러오는 중...</p>;
  }
  if (error) {
    return (
      <p className="text-sm text-red-600" role="alert">
        분석 데이터를 가져올 수 없습니다. 잠시 후 다시 시도해 주세요.
      </p>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-4" data-testid="analytics-dashboard-cards">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryStat label="담당 학급" value={data.classes.length} />
        <SummaryStat
          label="총 학생"
          value={data.classes.reduce((sum, c) => sum + c.student_count, 0)}
        />
        <SummaryStat label="최근 7일 피드백" value={data.recent_feedbacks_count} />
        <SummaryStat label="예정 상담" value={data.pending_counselings_count} />
      </div>

      {data.classes.length === 0 ? (
        <p className="text-sm text-gray-400">담당 학급이 없습니다.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.classes.map((c) => (
            <article
              key={c.class_id}
              className="border rounded p-4 bg-white space-y-1"
              data-testid={`class-card-${c.class_id}`}
            >
              <h3 className="font-semibold text-sm">{c.name}</h3>
              <p className="text-xs text-gray-500">학생 {c.student_count}명</p>
              <dl className="text-sm grid grid-cols-2 gap-y-1 mt-2">
                <dt className="text-gray-500">평균 점수</dt>
                <dd className="text-right">{formatScore(c.avg_score)}</dd>
                <dt className="text-gray-500">출석률</dt>
                <dd className="text-right">{formatRate(c.attendance_rate)}</dd>
              </dl>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="border rounded p-3 text-center bg-white">
      <div className="text-xl font-semibold text-indigo-600">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}
