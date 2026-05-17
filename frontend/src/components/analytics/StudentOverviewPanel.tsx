import { useStudentOverview } from '../../hooks/useAnalytics';

interface Props {
  studentId?: string;
  semesterId?: string;
}

function fmt(v: number | null, decimals = 1): string {
  return v == null ? '—' : v.toFixed(decimals);
}

function pct(v: number | null): string {
  return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

export default function StudentOverviewPanel({ studentId, semesterId }: Props) {
  const { data, isLoading, error } = useStudentOverview(studentId, semesterId);

  if (!studentId) {
    return (
      <p className="text-sm text-gray-400" data-testid="overview-placeholder">
        학생을 선택해 상세 지표를 확인하세요.
      </p>
    );
  }
  if (isLoading) return <p className="text-sm text-gray-500">학생 분석 불러오는 중...</p>;
  if (error) {
    return (
      <p className="text-sm text-red-600" role="alert">
        학생 분석 데이터를 가져올 수 없습니다.
      </p>
    );
  }
  if (!data || (!data.overall && data.subjects.length === 0)) {
    return (
      <p className="text-sm text-gray-400">
        아직 분석 데이터가 없습니다. 성적·출결·피드백 입력 후 1분 이내 반영됩니다.
      </p>
    );
  }

  return (
    <div className="space-y-3" data-testid="overview-panel">
      {data.overall && (
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-sm">
          <Stat label="평균" value={fmt(data.overall.avg_score)} />
          <Stat label="총점" value={fmt(data.overall.total_score)} />
          <Stat label="과목 수" value={String(data.overall.subject_count)} />
          <Stat label="출석률" value={pct(data.overall.attendance_present_rate)} />
          <Stat label="피드백" value={String(data.overall.feedback_count)} />
        </dl>
      )}

      {data.subjects.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-2 py-1 text-left">과목</th>
                <th className="px-2 py-1 text-right">평균</th>
                <th className="px-2 py-1 text-right">최고</th>
                <th className="px-2 py-1 text-right">최저</th>
                <th className="px-2 py-1 text-right">최근 등급</th>
                <th className="px-2 py-1 text-right">표본</th>
              </tr>
            </thead>
            <tbody>
              {data.subjects.map((s) => (
                <tr key={s.subject_id} className="border-t">
                  <td className="px-2 py-1">{s.name}</td>
                  <td className="px-2 py-1 text-right">{fmt(s.avg_score)}</td>
                  <td className="px-2 py-1 text-right">{fmt(s.max_score)}</td>
                  <td className="px-2 py-1 text-right">{fmt(s.min_score)}</td>
                  <td className="px-2 py-1 text-right">{s.latest_rank ?? '—'}</td>
                  <td className="px-2 py-1 text-right">{s.sample_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border rounded p-2 text-center bg-white">
      <div className="text-base font-semibold text-indigo-600">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
