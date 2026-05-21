import { useEffect, useRef, useState } from 'react';

import { postChat, type StudentRef } from '../../api/chat';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  text: string;
  refs?: StudentRef[];
}

// 응답 안에 등장한 학생A.. 토큰을 실제 학생명으로 치환한다.
// 예: "학생A는 평균이..." → "김철수는 평균이..."
function resolveTokens(reply: string, refs: StudentRef[]): string {
  if (refs.length === 0) return reply;
  // 토큰을 길이 내림차순으로 정렬해 부분 치환 충돌을 피한다.
  const refsByToken = new Map<string, string>();
  refs.forEach((r, i) => {
    refsByToken.set(`학생${String.fromCharCode(65 + i)}`, r.name);
  });
  let out = reply;
  for (const [token, name] of refsByToken) {
    out = out.split(token).join(name);
  }
  return out;
}

export default function ChatWidget() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const listEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (text.length === 0 || isLoading) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await postChat({ thread_id: threadId, message: text });
      setThreadId(res.thread_id);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          text: resolveTokens(res.reply, res.referenced_students),
          refs: res.referenced_students,
        },
      ]);
    } catch (err: unknown) {
      const status =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      const msg =
        status === 429
          ? '요청이 너무 잦습니다. 잠시 후 다시 시도하세요.'
          : '답변을 가져오지 못했습니다. 잠시 후 다시 시도하세요.';
      setMessages((prev) => [
        ...prev,
        { id: `e-${Date.now()}`, role: 'error', text: msg },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto w-full bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <h2 className="text-base font-semibold text-gray-900">AI 분석 비서</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          학급 통계 기반 질의응답 (k≥5 익명화)
        </p>
      </div>

      <div
        className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[320px]"
        aria-live="polite"
        aria-busy={isLoading}
      >
        {messages.length === 0 && !isLoading && (
          <p className="text-sm text-gray-400 text-center py-8">
            예: "이번 학기 우리 반 영어 평균이 어때?"
          </p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              m.role === 'user'
                ? 'flex justify-end'
                : 'flex justify-start'
            }
          >
            <div
              className={`max-w-[85%] px-3 py-2 rounded-lg text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : m.role === 'error'
                    ? 'bg-red-50 text-red-700 border border-red-200'
                    : 'bg-gray-100 text-gray-900'
              }`}
            >
              {m.text}
              {m.role === 'assistant' && m.refs && m.refs.length > 0 && (
                <div className="mt-2 text-xs text-gray-500 border-t border-gray-200 pt-1.5">
                  관련 학생: {m.refs.map((r) => r.name).join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-500 text-sm px-3 py-2 rounded-lg">
              생각 중...
            </div>
          </div>
        )}
        <div ref={listEndRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-gray-200 p-3 flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="질문을 입력하세요..."
          maxLength={1000}
          disabled={isLoading}
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
          aria-label="메시지 입력"
        />
        <button
          type="submit"
          disabled={isLoading || input.trim().length === 0}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          전송
        </button>
      </form>
    </div>
  );
}
