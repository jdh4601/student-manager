import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { createClass } from '../../api/classes';
import type { ClassSummary } from '../../types';

export default function ClassCreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: ClassSummary) => void }) {
  const nowYear = new Date().getFullYear();
  const [name, setName] = useState('');
  const [grade, setGrade] = useState<number>(1);
  const [year, setYear] = useState<number>(nowYear);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => createClass({ name, grade, year }),
    onSuccess: (c) => {
      onCreated(c);
      onClose();
    },
    onError: () => setError('학급 생성 중 오류가 발생했습니다.'),
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-xl p-4 w-full max-w-md">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">학급 만들기</h2>
          <button onClick={onClose} className="text-gray-500">×</button>
        </div>
        {error && <div className="text-sm text-red-600 mb-2">{error}</div>}
        <div className="space-y-2">
          <div>
            <label className="block text-sm">학년도</label>
            <input
              className="border p-1 w-full"
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              min={2000}
              max={3000}
            />
          </div>
          <div>
            <label className="block text-sm">학년</label>
            <input
              className="border p-1 w-full"
              type="number"
              value={grade}
              onChange={(e) => setGrade(Number(e.target.value))}
              min={1}
              max={12}
            />
          </div>
          <div>
            <label className="block text-sm">반 이름 (예: 1반)</label>
            <input
              className="border p-1 w-full"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예: 1반"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-3">
          <button onClick={onClose} className="px-3 py-1 text-sm border rounded">취소</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name || !grade || !year || mutation.isPending}
            className="px-3 py-1 text-sm bg-indigo-600 text-white rounded disabled:opacity-50"
          >
            {mutation.isPending ? '생성 중...' : '생성'}
          </button>
        </div>
      </div>
    </div>
  );
}

