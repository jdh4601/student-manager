import { useState } from 'react';
import { useUploadGrades } from '../../hooks/useImport';
import { getGradeTemplateUrl } from '../../api/imports';

export default function GradeExcelUploadModal({ classId, semesterId, onClose }: { classId: string; semesterId: string; onClose: () => void }) {
  const upload = useUploadGrades();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<{ created: number; skipped: number; errors: any[] } | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    const res = await upload.mutateAsync({ classId, semesterId, file });
    setResult(res);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-xl p-4 w-full max-w-lg">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">성적 엑셀 업로드</h2>
          <button onClick={onClose} className="text-gray-500">×</button>
        </div>
        <div className="text-sm text-gray-600 mb-2">
          템플릿을 내려받아 형식에 맞게 작성 후 업로드하세요.{' '}
          <a href={getGradeTemplateUrl(classId)} className="text-indigo-600 underline">템플릿 다운로드</a>
        </div>
        <input
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="mb-3"
        />
        {result && (
          <div className="mb-3 text-sm">
            <div>등록: {result.created} / 건너뜀: {result.skipped}</div>
            {result.errors.length > 0 && (
              <div className="mt-2 max-h-40 overflow-auto border rounded p-2 text-red-600">
                {result.errors.map((e, i) => (
                  <div key={i}>행 {e.row}: {e.error}</div>
                ))}
              </div>
            )}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1 text-sm border rounded">닫기</button>
          <button
            onClick={handleUpload}
            disabled={!file || upload.isPending}
            className="px-3 py-1 text-sm bg-indigo-600 text-white rounded disabled:opacity-50"
          >
            {upload.isPending ? '업로드 중...' : '업로드'}
          </button>
        </div>
      </div>
    </div>
  );
}

