import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { listClasses, listSubjects } from '../api/classes';
import { listStudents } from '../api/users';
import { useTeacherDashboard } from '../hooks/useAnalytics';
import { useStudents } from '../hooks/useStudents';
import { useFeedbacks } from '../hooks/useFeedbacks';
import { useCounselings } from '../hooks/useCounselings';
import { useAuthStore } from '../stores/authStore';
import { Card, CardHeader } from '../components/ui/Card';
import { StatCard } from '../components/ui/StatCard';
import { FilterSelect } from '../components/ui/FilterSelect';
import { Badge } from '../components/ui/Badge';
import ClassDistributionChart from '../components/analytics/ClassDistributionChart';
import StudentOverviewPanel from '../components/analytics/StudentOverviewPanel';

const CATEGORY_LABEL: Record<string, string> = {
  grade: '성적',
  behavior: '행동',
  attendance: '출결',
  attitude: '태도',
};

function fmtScore(v: number | null): string {
  return v == null ? '—' : v.toFixed(1);
}
function fmtRate(v: number | null): string {
  return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);

  const [classId, setClassId] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [studentQuery, setStudentQuery] = useState('');
  const [studentId, setStudentId] = useState('');

  const dashboard = useTeacherDashboard();
  const { data: students } = useStudents();
  const { data: feedbacks } = useFeedbacks();
  const { data: counselings } = useCounselings();

  const classesQuery = useQuery({ queryKey: ['classes'], queryFn: () => listClasses() });
  const subjectsQuery = useQuery({
    queryKey: ['subjects', classId],
    queryFn: () => listSubjects(classId),
    enabled: Boolean(classId),
  });
  const studentsQuery = useQuery({
    queryKey: ['students', { classId: classId || undefined }],
    queryFn: () => listStudents(classId || undefined),
  });

  useEffect(() => {
    setSubjectId('');
    setStudentId('');
  }, [classId]);

  const filteredStudents = (studentsQuery.data ?? []).filter((s) =>
    studentQuery.trim() === '' ? true : s.name.includes(studentQuery.trim()),
  );

  const rankedClasses = useMemo(() => {
    const list = dashboard.data?.classes ?? [];
    return [...list].sort((a, b) => (b.avg_score ?? -1) - (a.avg_score ?? -1));
  }, [dashboard.data]);

  const totalStudents = (dashboard.data?.classes ?? []).reduce(
    (sum, c) => sum + c.student_count,
    0,
  );

  const recentFeedbacks = (feedbacks ?? []).slice(-4).reverse();
  const recentCounselings = (counselings ?? []).slice(-4).reverse();
  const nameOf = (id: string) => students?.find((s) => s.id === id)?.name ?? '알 수 없음';

  return (
    <div className="space-y-6">
      {/* Page header + global filters */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">대시보드</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {user ? `${user.name} 선생님, 오늘도 좋은 하루 되세요.` : '담당 학급 현황을 한눈에 확인하세요.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <FilterSelect
            ariaLabel="학급 선택"
            placeholder="전체 학급"
            value={classId}
            onChange={setClassId}
            options={(classesQuery.data ?? []).map((c) => ({ value: c.id, label: c.name }))}
            icon={
              <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
                <path d="M2 13V5l6-3 6 3v8M2 13h12M6 13V9h4v4" strokeLinejoin="round" />
              </svg>
            }
          />
          <FilterSelect
            ariaLabel="과목 선택"
            placeholder="과목 선택"
            value={subjectId}
            onChange={setSubjectId}
            disabled={!classId}
            options={(subjectsQuery.data ?? []).map((s) => ({ value: s.id, label: s.name }))}
          />
        </div>
      </div>

      {/* KPI strip */}
      <KpiStrip
        loading={dashboard.isLoading}
        error={Boolean(dashboard.error)}
        classCount={dashboard.data?.classes.length ?? 0}
        totalStudents={totalStudents}
        recentFeedbacks={dashboard.data?.recent_feedbacks_count ?? 0}
        pendingCounselings={dashboard.data?.pending_counselings_count ?? 0}
      />

      {/* Distribution + class ranking */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader
            title="학급 점수 분포"
            subtitle="선택한 학급·과목의 점수대별 학생 분포"
          />
          <div className="mt-4">
            <ClassDistributionChart classId={classId} subjectId={subjectId} />
          </div>
        </Card>

        <Card className="xl:col-span-2" flush>
          <CardHeader
            title="담당 학급"
            subtitle="평균 점수 순"
            className="p-5 pb-3 sm:p-6 sm:pb-3"
          />
          <ClassRankingTable
            rows={rankedClasses}
            loading={dashboard.isLoading}
          />
        </Card>
      </div>

      {/* Student detail + recent activity */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader
            title="학생 상세 분석"
            subtitle="학생별 평균·출석·과목 지표"
            action={
              <FilterSelect
                ariaLabel="학생 선택"
                placeholder="학생 선택"
                value={studentId}
                onChange={setStudentId}
                options={filteredStudents.map((s) => ({
                  value: s.id,
                  label: `${s.name} (${s.student_number}번)`,
                }))}
              />
            }
          />
          <div className="mt-3">
            <input
              className="w-full rounded-full border border-line bg-surface-soft/40 px-4 py-2 text-sm text-ink placeholder:text-muted focus:border-clay-soft focus:bg-surface focus:outline-none"
              placeholder="학생 이름 검색"
              value={studentQuery}
              onChange={(e) => setStudentQuery(e.target.value)}
              aria-label="학생 이름 검색"
            />
          </div>
          <div className="mt-4">
            <StudentOverviewPanel studentId={studentId || undefined} />
          </div>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader title="최근 활동" subtitle="피드백 · 상담 기록" />
          <div className="mt-4 space-y-5">
            <ActivityGroup
              title="최근 피드백"
              href="/feedbacks"
              empty="피드백이 없습니다"
              items={recentFeedbacks.map((fb) => ({
                id: fb.id,
                name: nameOf(fb.student_id),
                tag: CATEGORY_LABEL[(fb as { category?: string }).category ?? ''] ?? '기타',
                text: fb.content,
              }))}
            />
            <div className="border-t border-line-soft" />
            <ActivityGroup
              title="최근 상담"
              href="/counselings"
              empty="상담 기록이 없습니다"
              items={recentCounselings.map((cs) => ({
                id: cs.id,
                name: nameOf(cs.student_id),
                tag: cs.date,
                text: cs.content,
              }))}
            />
          </div>
        </Card>
      </div>
    </div>
  );
}

function KpiStrip({
  loading,
  error,
  classCount,
  totalStudents,
  recentFeedbacks,
  pendingCounselings,
}: {
  loading: boolean;
  error: boolean;
  classCount: number;
  totalStudents: number;
  recentFeedbacks: number;
  pendingCounselings: number;
}) {
  if (error) {
    return (
      <Card>
        <p className="text-sm text-negative" role="alert">
          분석 데이터를 가져올 수 없습니다. 잠시 후 다시 시도해 주세요.
        </p>
      </Card>
    );
  }

  const stats = [
    { label: '담당 학급', value: classCount, hint: '관리 중인 학급', accent: true },
    { label: '총 학생', value: totalStudents, hint: '전체 담당 학생' },
    { label: '최근 7일 피드백', value: recentFeedbacks, hint: '작성된 피드백' },
    { label: '예정 상담', value: pendingCounselings, hint: '대기 중 상담' },
  ];

  return (
    <div
      className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4"
      data-testid="analytics-dashboard-cards"
    >
      {stats.map((s) => (
        <StatCard
          key={s.label}
          label={s.label}
          value={loading ? '—' : s.value}
          hint={s.hint}
          accent={s.accent}
        />
      ))}
    </div>
  );
}

interface RankRow {
  class_id: string;
  name: string;
  student_count: number;
  avg_score: number | null;
  attendance_rate: number | null;
}

function ClassRankingTable({ rows, loading }: { rows: RankRow[]; loading: boolean }) {
  if (loading) {
    return <p className="px-6 pb-6 text-sm text-ink-soft">불러오는 중…</p>;
  }
  if (rows.length === 0) {
    return <p className="px-6 pb-6 text-sm text-muted">담당 학급이 없습니다.</p>;
  }

  return (
    <table className="min-w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
          <th className="py-2 pl-6 pr-2 font-medium">#</th>
          <th className="px-2 py-2 font-medium">학급</th>
          <th className="px-2 py-2 text-right font-medium">학생</th>
          <th className="px-2 py-2 text-right font-medium">평균</th>
          <th className="py-2 pl-2 pr-6 text-right font-medium">출석률</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c, i) => (
          <tr
            key={c.class_id}
            className="border-b border-line-soft last:border-0"
            data-testid={`class-card-${c.class_id}`}
          >
            <td className="py-3 pl-6 pr-2 text-muted tnum">{i + 1}</td>
            <td className="px-2 py-3 font-medium text-ink">{c.name}</td>
            <td className="px-2 py-3 text-right tnum text-ink-soft">{c.student_count}</td>
            <td className="px-2 py-3 text-right">
              <span className="font-display font-semibold tnum text-ink">{fmtScore(c.avg_score)}</span>
            </td>
            <td className="py-3 pl-2 pr-6 text-right tnum text-ink-soft">{fmtRate(c.attendance_rate)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface ActivityItem {
  id: string;
  name: string;
  tag: string;
  text: string;
}

function ActivityGroup({
  title,
  href,
  empty,
  items,
}: {
  title: string;
  href: string;
  empty: string;
  items: ActivityItem[];
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
        <Link to={href} className="text-xs font-medium text-clay-ink hover:underline">
          전체 보기
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-muted">{empty}</p>
      ) : (
        <ul className="space-y-2.5">
          {items.map((it) => (
            <li key={it.id} className="flex items-start gap-2.5">
              <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-clay-wash text-[11px] font-semibold text-clay-ink">
                {it.name[0] ?? '?'}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-ink">{it.name}</span>
                  <Badge>{it.tag}</Badge>
                </div>
                <p className="truncate text-xs text-ink-soft">{it.text}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
