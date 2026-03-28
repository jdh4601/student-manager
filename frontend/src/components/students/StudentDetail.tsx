import type { Attendance, SpecialNote, StudentDetail as StudentDetailType } from '../../types';

export default function StudentDetail({ student, attendance, notes }: { student: StudentDetailType; attendance: Attendance[]; notes: SpecialNote[] }) {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="font-semibold mb-2">기본 정보</h2>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div><span className="text-gray-600">이름: </span>{student.name}</div>
          <div><span className="text-gray-600">번호: </span>{student.student_number}</div>
          <div><span className="text-gray-600">생년월일: </span>{student.birth_date ?? '-'}</div>
          {student.gender && (
            <div><span className="text-gray-600">성별: </span>{student.gender === 'male' ? '남' : '여'}</div>
          )}
          {student.phone && (
            <div><span className="text-gray-600">연락처: </span>{student.phone}</div>
          )}
          {student.address && (
            <div className="col-span-2"><span className="text-gray-600">주소: </span>{student.address}</div>
          )}
        </div>
      </section>

      <section>
        <h2 className="font-semibold mb-2">출결</h2>
        <table className="w-full text-sm border">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 border">날짜</th>
              <th className="p-2 border">상태</th>
              <th className="p-2 border">메모</th>
            </tr>
          </thead>
          <tbody>
            {attendance.map((a) => (
              <tr key={a.id} className="border-b">
                <td className="p-2 border">{a.date}</td>
                <td className="p-2 border">{a.status}</td>
                <td className="p-2 border">{a.note ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="font-semibold mb-2">특기사항</h2>
        <ul className="text-sm space-y-2">
          {notes.map((n) => (
            <li key={n.id} className="border p-2 rounded">
              <div className="text-gray-600 text-xs">{new Date(n.created_at).toLocaleString()}</div>
              <div>{n.content}</div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
