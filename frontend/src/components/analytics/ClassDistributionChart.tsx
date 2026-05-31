import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useClassDistribution } from '../../hooks/useAnalytics';

interface Props {
  classId?: string;
  subjectId?: string;
  semesterId?: string;
}

const CLAY = '#BD5D3A';

function EmptyState({ children, testId }: { children: string; testId?: string }) {
  return (
    <div
      className="flex h-[240px] items-center justify-center rounded-xl border border-dashed border-line bg-surface-soft/50 px-4 text-center text-sm text-muted"
      data-testid={testId}
    >
      {children}
    </div>
  );
}

export default function ClassDistributionChart({
  classId,
  subjectId,
  semesterId,
}: Props) {
  const { data, isLoading, error } = useClassDistribution(classId, subjectId, semesterId);

  if (!classId || !subjectId) {
    return (
      <EmptyState testId="distribution-placeholder">
        학급과 과목을 선택해 분포를 확인하세요.
      </EmptyState>
    );
  }
  if (isLoading) {
    return <EmptyState>분포를 불러오는 중…</EmptyState>;
  }
  if (error) {
    return (
      <p className="text-sm text-negative" role="alert">
        분포 데이터를 가져올 수 없습니다.
      </p>
    );
  }
  if (!data || data.total_students === 0) {
    return <EmptyState>해당 과목·학기의 분포 데이터가 아직 없습니다.</EmptyState>;
  }

  return (
    <div data-testid="distribution-chart">
      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        <Chip label="학생" value={`${data.total_students}명`} />
        <Chip label="평균" value={data.mean?.toFixed(1) ?? '—'} accent />
        <Chip label="중앙값" value={data.median?.toFixed(1) ?? '—'} />
      </div>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <AreaChart data={data.buckets} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="clayFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CLAY} stopOpacity={0.28} />
                <stop offset="100%" stopColor={CLAY} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#EBE5DB" vertical={false} />
            <XAxis
              dataKey="range"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: '#EBE5DB' }}
              tick={{ fill: '#9A9189' }}
            />
            <YAxis
              allowDecimals={false}
              fontSize={11}
              tickLine={false}
              axisLine={false}
              tick={{ fill: '#9A9189' }}
            />
            <Tooltip
              cursor={{ stroke: '#D98E6F', strokeWidth: 1 }}
              contentStyle={{
                borderRadius: 12,
                border: '1px solid #EBE5DB',
                boxShadow: '0 8px 24px -12px rgba(38,33,27,0.2)',
                fontSize: 12,
              }}
              labelStyle={{ color: '#26211B', fontWeight: 600 }}
            />
            <Area
              type="monotone"
              dataKey="count"
              name="학생 수"
              stroke={CLAY}
              strokeWidth={2.5}
              fill="url(#clayFill)"
              dot={{ r: 3, fill: CLAY, strokeWidth: 0 }}
              activeDot={{ r: 5 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Chip({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ${
        accent ? 'bg-clay-wash text-clay-ink' : 'bg-surface-soft text-ink-soft'
      }`}
    >
      <span className="text-muted">{label}</span>
      <span className="font-semibold tnum">{value}</span>
    </span>
  );
}
