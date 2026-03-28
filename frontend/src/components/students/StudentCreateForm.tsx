import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createStudent } from '../../api/students';

export default function StudentCreateForm({ classId, onClose }: { classId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [studentNumber, setStudentNumber] = useState<number>(1);
  const [birthDate, setBirthDate] = useState<string>('');
  const [gender, setGender] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [address, setAddress] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () =>
      createStudent(classId, {
        name,
        student_number: studentNumber,
        birth_date: birthDate || undefined,
        gender: gender || undefined,
        phone: phone || undefined,
        address: address || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['students', { classId }] });
      onClose();
    },
    onError: (e: any) => {
      const code = e?.response?.data?.code;
      if (code === 'STUDENT_DUPLICATE_NUMBER') setError('이미 존재하는 번호입니다.');
      else setError('등록 중 오류가 발생했습니다.');
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-xl p-4 w-full max-w-md">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">학생 추가</h2>
          <button onClick={onClose} className="text-gray-500">×</button>
        </div>
        {error && <div className="text-sm text-red-600 mb-2">{error}</div>}
        <div className="space-y-2">
          <div>
            <label className="block text-sm">이름</label>
            <input className="border p-1 w-full" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm">번호</label>
            <input
              className="border p-1 w-full"
              type="number"
              min={1}
              max={100}
              value={studentNumber}
              onChange={(e) => setStudentNumber(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="block text-sm">생년월일</label>
            <input className="border p-1 w-full" type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm">성별</label>
            <select className="border p-1 w-full" value={gender} onChange={(e) => setGender(e.target.value)}>
              <option value="">선택 안함</option>
              <option value="male">남</option>
              <option value="female">여</option>
            </select>
          </div>
          <div>
            <label className="block text-sm">연락처</label>
            <input className="border p-1 w-full" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm">주소</label>
            <input className="border p-1 w-full" value={address} onChange={(e) => setAddress(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-3">
          <button onClick={onClose} className="px-3 py-1 text-sm border rounded">취소</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name || !studentNumber || mutation.isPending}
            className="px-3 py-1 text-sm bg-indigo-600 text-white rounded disabled:opacity-50"
          >
            {mutation.isPending ? '등록 중...' : '등록'}
          </button>
        </div>
      </div>
    </div>
  );
}

