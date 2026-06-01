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
      <p className="text-sm text-muted" data-testid="overview-placeholder">
        학생을 선택해 상세 지표를 확인하세요.
      </p>
    );
  }
  if (isLoading) return <p className="text-sm text-ink-soft">학생 분석 불러오는 중…</p>;
  if (error) {
    return (
      <p className="text-sm text-negative" role="alert">
        학생 분석 데이터를 가져올 수 없습니다.
      </p>
    );
  }
  if (!data || (!data.overall && data.subjects.length === 0)) {
    return (
      <p className="text-sm text-muted">
        아직 분석 데이터가 없습니다. 성적·출결·피드백 입력 후 1분 이내 반영됩니다.
      </p>
    );
  }

  return (
    <div className="space-y-4" data-testid="overview-panel">
      {data.overall && (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat label="평균" value={fmt(data.overall.avg_score)} accent />
          <Stat label="총점" value={fmt(data.overall.total_score)} />
          <Stat label="과목 수" value={String(data.overall.subject_count)} />
          <Stat label="출석률" value={pct(data.overall.attendance_present_rate)} />
          <Stat label="피드백" value={String(data.overall.feedback_count)} />
        </dl>
      )}

      {data.subjects.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
                <th className="px-2 py-2 font-medium">과목</th>
                <th className="px-2 py-2 text-right font-medium">평균</th>
                <th className="px-2 py-2 text-right font-medium">최고</th>
                <th className="px-2 py-2 text-right font-medium">최저</th>
                <th className="px-2 py-2 text-right font-medium">최근 등급</th>
                <th className="px-2 py-2 text-right font-medium">표본</th>
              </tr>
            </thead>
            <tbody>
              {data.subjects.map((s) => (
                <tr key={s.subject_id} className="border-b border-line-soft last:border-0">
                  <td className="px-2 py-2 font-medium text-ink">{s.name}</td>
                  <td className="px-2 py-2 text-right tnum text-ink">{fmt(s.avg_score)}</td>
                  <td className="px-2 py-2 text-right tnum text-ink-soft">{fmt(s.max_score)}</td>
                  <td className="px-2 py-2 text-right tnum text-ink-soft">{fmt(s.min_score)}</td>
                  <td className="px-2 py-2 text-right tnum text-ink-soft">{s.latest_rank ?? '—'}</td>
                  <td className="px-2 py-2 text-right tnum text-muted">{s.sample_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div
      className={`rounded-xl border px-3 py-2.5 text-center ${
        accent ? 'border-clay-wash bg-clay-wash/50' : 'border-line bg-surface-soft/50'
      }`}
    >
      <div
        className={`font-display text-xl font-semibold tnum ${
          accent ? 'text-clay-ink' : 'text-ink'
        }`}
      >
        {value}
      </div>
      <div className="mt-0.5 text-xs text-ink-soft">{label}</div>
    </div>
  );
}
