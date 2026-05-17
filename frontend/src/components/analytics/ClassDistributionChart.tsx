import {
  Bar,
  BarChart,
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

export default function ClassDistributionChart({
  classId,
  subjectId,
  semesterId,
}: Props) {
  const { data, isLoading, error } = useClassDistribution(classId, subjectId, semesterId);

  if (!classId || !subjectId) {
    return (
      <p className="text-sm text-gray-400" data-testid="distribution-placeholder">
        학급과 과목을 선택해 분포를 확인하세요.
      </p>
    );
  }
  if (isLoading) {
    return <p className="text-sm text-gray-500">분포를 불러오는 중...</p>;
  }
  if (error) {
    return (
      <p className="text-sm text-red-600" role="alert">
        분포 데이터를 가져올 수 없습니다.
      </p>
    );
  }
  if (!data || data.total_students === 0) {
    return (
      <p className="text-sm text-gray-400">
        해당 과목·학기의 분포 데이터가 아직 없습니다.
      </p>
    );
  }

  return (
    <div data-testid="distribution-chart">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-600 mb-2">
        <span>학생 {data.total_students}명</span>
        <span>평균 {data.mean?.toFixed(1) ?? '—'}</span>
        <span>중앙값 {data.median?.toFixed(1) ?? '—'}</span>
      </div>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <BarChart data={data.buckets} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="range" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip />
            <Bar dataKey="count" fill="#4f46e5" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
