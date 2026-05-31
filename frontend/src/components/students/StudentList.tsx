import type { StudentSummary, SpecialNote, Attendance as AttendanceType, GradeItem, Subject, Semester } from '../../types';
import { useStudent } from '../../hooks/useStudent';
import { useGrades } from '../../hooks/useGrades';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { listAttendance, listSpecialNotes, createAttendance, updateAttendance } from '../../api/students';
import { listSubjects } from '../../api/classes';
import { listSemesters } from '../../api/semesters';
import { resendStudentInvitation } from '../../api/users';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import InvitationStatusBadge from './InvitationStatusBadge';
import { copyText } from '../../utils/clipboard';

function formatDateYYYYMMDD(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function useAttendanceToday(studentId: string) {
  const today = formatDateYYYYMMDD(new Date());
  return useQuery<AttendanceType[]>({
    queryKey: ['attendance-today', studentId, today],
    queryFn: () => listAttendance(studentId, { start_date: today, end_date: today }),
  });
}

function useLatestSpecialNote(studentId: string) {
  return useQuery<SpecialNote[]>({
    queryKey: ['special-notes', studentId],
    queryFn: () => listSpecialNotes(studentId),
  });
}

function genderLabel(g?: string | null) {
  if (!g) return '-';
  if (g === 'male') return '남';
  if (g === 'female') return '여';
  return g;
}

function selectDisplaySemesterId(semesters: Semester[]) {
  const lastSemesterId = safeGetLocal('lastSemesterId');
  if (lastSemesterId && semesters.some((semester) => semester.id === lastSemesterId)) {
    return lastSemesterId;
  }
  return semesters[0]?.id;
}

function formatGradePreview(grades: GradeItem[], orderedSubjectIds: string[]) {
  const rankedGrades = grades.filter((grade) => grade.grade_rank != null);
  if (rankedGrades.length === 0) return '';

  const orderedRanks = orderedSubjectIds.length > 0
    ? orderedSubjectIds
        .map((subjectId) => rankedGrades.find((grade) => grade.subject_id === subjectId)?.grade_rank)
        .filter((gradeRank): gradeRank is number => gradeRank != null)
    : rankedGrades.map((grade) => grade.grade_rank).filter((gradeRank): gradeRank is number => gradeRank != null);

  if (orderedRanks.length === 0) return '';
  return `${orderedRanks.join('/')}/`;
}

function StudentRow({ s, displaySemesterId, orderedSubjectIds }: { s: StudentSummary; displaySemesterId?: string; orderedSubjectIds: string[] }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: detail } = useStudent(s.id);
  const { data: grades } = useGrades(s.id, displaySemesterId, { enabled: !!displaySemesterId });
  const { data: attendance } = useAttendanceToday(s.id);
  const { data: notes } = useLatestSpecialNote(s.id);
  const latestNote = (notes || [])
    .slice()
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0];
  const gradePreview = formatGradePreview(grades || [], orderedSubjectIds);
  const gradeAverage = (() => {
    const scored = (grades || []).filter((g) => g.score != null);
    if (scored.length === 0) return null;
    const sum = scored.reduce((acc, g) => acc + Number(g.score), 0);
    return Math.round((sum / scored.length) * 10) / 10;
  })();

  const todayStr = formatDateYYYYMMDD(new Date());
  const current = attendance && attendance[0];

  const { mutate: setTodayStatus, isPending } = useMutation({
    mutationFn: async (status: AttendanceType['status']) => {
      if (current) {
        return updateAttendance(s.id, current.id, { date: current.date, status, note: current.note ?? null });
      }
      return createAttendance(s.id, { date: todayStr, status });
    },
    onSuccess: (saved) => {
      // Update cache for today's attendance for this student
      qc.setQueryData<AttendanceType[]>(['attendance-today', s.id, todayStr], (old) => {
        if (!old || old.length === 0) return [saved];
        return [{ ...old[0], status: saved.status, note: saved.note }];
      });
      toast.success('오늘 출결을 저장했습니다.');
    },
    onError: () => {
      toast.error('출결 저장 중 오류가 발생했습니다.');
    },
  });

  const { mutateAsync: resendInvite, isPending: isResending } = useMutation({
    mutationFn: async () => resendStudentInvitation(s.id),
  });

  // 만료 처리는 빠른 액션에서 제거됨 (2026-04-08)

  const effectiveInviteStatus: 'not_sent' | 'pending' | 'accepted' | 'expired' = !s.invite_sent_at
    ? 'not_sent'
    : (s.invite_status as any) || 'pending';
  const disableInviteActions = effectiveInviteStatus === 'accepted';
  const isNotSent = effectiveInviteStatus === 'not_sent';
  const showSendNow = isNotSent || effectiveInviteStatus === 'expired';

  const handleResend = async (copyAfter: boolean) => {
    try {
      const result = await resendInvite();
      qc.invalidateQueries({ queryKey: ['students'] });
      if (copyAfter && result.invite_url) {
        await copyText(result.invite_url);
        toast.success('새 초대 링크를 복사했습니다.');
        return;
      }
      toast.success('초대를 재전송했습니다.');
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || '초대 재전송에 실패했습니다.');
    }
  };

  return (
    <tr className="odd:bg-white even:bg-gray-50/70 transition-colors hover:bg-blue-50/60">
      <td className="px-3 py-2.5 text-center text-gray-500">{s.student_number}</td>
      <td className="px-3 py-2.5 text-center">
        <button
          className="text-blue-600 hover:underline"
          type="button"
          onClick={() => navigate(`/students/${s.id}`)}
        >
          {s.name}
        </button>
      </td>
      <td className="px-3 py-2.5 text-center">{genderLabel(detail?.gender)}</td>
      <td className="px-3 py-2.5 text-center">
        <select
          className="border rounded px-1 py-0.5 text-sm"
          value={current?.status ?? ''}
          onChange={(e) => {
            const val = e.target.value as AttendanceType['status'] | '';
            if (!val) return;
            setTodayStatus(val);
          }}
          disabled={isPending}
        >
          <option value="" disabled>
            선택
          </option>
          <option value="present">출석</option>
          <option value="absent">결석</option>
          <option value="late">지각</option>
          <option value="early_leave">조퇴</option>
        </select>
      </td>
      <td className="px-3 py-2.5">
        {latestNote ? (
          <span title={latestNote.content}>
            {latestNote.content.length > 24 ? latestNote.content.slice(0, 24) + '…' : latestNote.content}
          </span>
        ) : (
          <span className="text-gray-400">-</span>
        )}
      </td>
      <td className="px-3 py-2.5 text-center">
        <button
          type="button"
          className={gradePreview ? 'text-blue-600 hover:underline font-medium' : 'px-2 py-1 text-xs border rounded'}
          onClick={() => navigate(`/grades/${s.id}`)}
        >
          {gradePreview || '성적 입력'}
        </button>
      </td>
      <td className="px-3 py-2.5 text-center">
        {gradeAverage != null ? gradeAverage.toFixed(1) : <span className="text-gray-400">-</span>}
      </td>
      <td className="px-3 py-2.5 text-center">
        <div className="flex flex-wrap justify-center gap-1 relative z-0">
          {showSendNow ? (
            <button
              type="button"
              className="rounded border px-2 py-1 text-xs relative z-10"
              disabled={isResending}
              onClick={() => void handleResend(true)}
            >
              전송
            </button>
          ) : (
            <>
              <button type="button" className="rounded border px-2 py-1 text-xs relative z-10 disabled:opacity-50 disabled:bg-gray-100 disabled:cursor-not-allowed hover:bg-gray-50" disabled={disableInviteActions || isResending} onClick={() => void handleResend(false)}>
                재전송
              </button>
              <button type="button" className="rounded border px-2 py-1 text-xs relative z-10 disabled:opacity-50 disabled:bg-gray-100 disabled:cursor-not-allowed hover:bg-gray-50" disabled={disableInviteActions || isResending} onClick={() => void handleResend(true)}>
                링크 복사
              </button>
            </>
          )}
        </div>
      </td>
      <td className="px-3 py-2.5 text-center">
        <InvitationStatusBadge status={effectiveInviteStatus} sentAt={s.invite_sent_at ?? null} />
      </td>
    </tr>
  );
}

export default function StudentList({ students }: { students: StudentSummary[] }) {
  const sorted = students.slice().sort((a, b) => a.student_number - b.student_number);
  const classId = sorted[0]?.class_id;
  const { data: semesters = [] } = useQuery<Semester[]>({
    queryKey: ['semesters'],
    queryFn: listSemesters,
  });
  const { data: subjects = [] } = useQuery<Subject[]>({
    queryKey: ['class-subjects', classId],
    queryFn: () => listSubjects(classId || ''),
    enabled: !!classId,
  });
  const displaySemesterId = selectDisplaySemesterId(semesters);
  const orderedSubjectIds = subjects.map((subject) => subject.id);

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead className="border-b border-gray-200 bg-gray-100 text-xs font-semibold uppercase tracking-wide text-gray-600">
          <tr>
            <th className="px-3 py-3 text-center">번호</th>
            <th className="px-3 py-3 text-center">이름</th>
            <th className="px-3 py-3 text-center">성별</th>
            <th className="px-3 py-3 text-center">오늘 출결</th>
            <th className="px-3 py-3 text-left">특이사항</th>
            <th className="px-3 py-3 text-center">성적</th>
            <th className="px-3 py-3 text-center">평균</th>
            <th className="px-3 py-3 text-center">빠른 액션</th>
            <th className="px-3 py-3 text-center">초대 상태</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 text-gray-800">
          {sorted.map((s) => (
            <StudentRow key={s.id} s={s} displaySemesterId={displaySemesterId} orderedSubjectIds={orderedSubjectIds} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function safeGetLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
