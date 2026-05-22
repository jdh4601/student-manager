import { useEffect } from 'react';

import { useChatStore } from '../../stores/chatStore';
import ChatWidget from './ChatWidget';
import TeacherMascot from './TeacherMascot';

export default function FloatingTeacher() {
  const isOpen = useChatStore((s) => s.isOpen);
  const open = useChatStore((s) => s.open);
  const close = useChatStore((s) => s.close);
  const reset = useChatStore((s) => s.reset);
  const messagesCount = useChatStore((s) => s.messages.length);

  useEffect(() => {
    if (!isOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') close();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, close]);

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={open}
        aria-label="AI 교사 열기"
        className="fixed bottom-6 right-6 z-[60] flex items-center gap-2 rounded-full bg-white shadow-lg border border-gray-200 pl-2 pr-4 py-2 hover:shadow-xl hover:-translate-y-0.5 transition group"
      >
        <span className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
          <TeacherMascot className="w-9 h-9" />
        </span>
        <span className="text-sm font-semibold text-gray-800">AI 교사</span>
      </button>
    );
  }

  return (
    <div
      role="dialog"
      aria-labelledby="ai-teacher-title"
      aria-modal="false"
      className="fixed z-[60] bg-white shadow-2xl border border-gray-200 flex flex-col
                 inset-x-4 bottom-4 top-20 rounded-2xl
                 md:inset-auto md:bottom-6 md:right-6 md:top-auto md:left-auto md:w-[380px] md:h-[560px] md:max-h-[80vh]"
    >
      <header className="flex items-center justify-between px-3 py-2.5 border-b border-gray-200 bg-gray-50 rounded-t-2xl">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
            <TeacherMascot className="w-7 h-7" />
          </span>
          <div className="min-w-0">
            <h2
              id="ai-teacher-title"
              className="text-sm font-semibold text-gray-900 leading-tight truncate"
            >
              AI 교사
            </h2>
            <p className="text-[11px] text-gray-500 leading-tight truncate">
              학급 통계 기반 질의응답 (k≥5 익명화)
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {messagesCount > 0 && (
            <button
              type="button"
              onClick={reset}
              className="text-xs text-gray-500 hover:text-gray-800 px-2 py-1 rounded hover:bg-gray-100"
              aria-label="새 대화 시작"
            >
              새 대화
            </button>
          )}
          <button
            type="button"
            onClick={close}
            className="text-gray-400 hover:text-gray-700 p-1 rounded hover:bg-gray-100"
            aria-label="AI 교사 닫기"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      </header>

      <div className="flex-1 min-h-0 flex flex-col">
        <ChatWidget autoFocus />
      </div>
    </div>
  );
}
