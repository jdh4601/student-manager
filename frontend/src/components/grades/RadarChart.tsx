import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart as RechartsRadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { GradeItem, Subject } from '../../types';

interface GradeRadarChartProps {
  subjects: Subject[];
  grades: GradeItem[];
}

export default function GradeRadarChart({ subjects, grades }: GradeRadarChartProps) {
  const gradeMap = new Map(grades.map((g) => [g.subject_id, g.score ?? 0]));

  const data = subjects.map((s) => ({
    subject: s.name,
    score: gradeMap.get(s.id) ?? 0,
  }));

  if (data.length === 0) {
    return <p className="text-gray-500 text-sm">과목 데이터가 없습니다.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <RechartsRadarChart data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="subject" />
        <Radar name="점수" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.4} />
        <Tooltip />
        <Legend />
      </RechartsRadarChart>
    </ResponsiveContainer>
  );
}
