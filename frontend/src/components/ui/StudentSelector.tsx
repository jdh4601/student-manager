import { useStudents } from '../../hooks/useStudents';
import type { StudentSummary } from '../../types';

interface StudentSelectorProps {
  value: string;
  onChange: (studentId: string) => void;
  classId?: string;
  disabled?: boolean;
  required?: boolean;
}

export default function StudentSelector({
  value,
  onChange,
  classId,
  disabled,
  required,
}: StudentSelectorProps) {
  const { data: students, isLoading } = useStudents(classId);

  const selectedStudent: StudentSummary | undefined = students?.find((s) => s.id === value);

  return (
    <div className="relative">
      <select
        className="border w-full p-1 text-sm bg-white disabled:bg-gray-100"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || isLoading}
        required={required}
      >
        <option value="">
          {isLoading ? '학생 목록 불러오는 중...' : '학생 선택'}
        </option>
        {(students ?? []).map((s) => (
          <option key={s.id} value={s.id}>
            {s.student_number}번 {s.name}
          </option>
        ))}
      </select>
      {value && selectedStudent && (
        <p className="text-xs text-gray-500 mt-0.5">
          선택됨: {selectedStudent.student_number}번 {selectedStudent.name}
        </p>
      )}
    </div>
  );
}
