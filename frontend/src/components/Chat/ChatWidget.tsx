import { useEffect, useMemo, useRef, useState } from 'react';

import { useChatStore } from '../../stores/chatStore';

const SUGGESTED_QUESTIONS = [
  '1학기 우리 반 학생들의 영어 성적의 평균이 어때?',
  '1학기 학생들의 전체 점수의 평균을 알려줘',
  '1학기 학생들의 과학 점수의 중앙값을 알려줘',
];

const LOADING_PHRASES = [
  '📄 성적표를 넘겨보는 중...',
  '📋 출석부와 대조하는 중...',
  '🙋‍♂️ 학생과 상담하는 중...',
  '📊 데이터를 그려보는 중...',
];

const LOADING_PHRASE_INTERVAL_MS = 2200;
const TYPE_SPEED_MS = 70;

// Intl.Segmenter는 🙋‍♂️ 같은 ZWJ 이모지 조합을 한 글자(grapheme)로 묶어준다.
// code point 단위로 자르면 타이핑 중간에 깨진 글리프가 보인다.
// 현재 tsconfig lib에 Segmenter 타입이 없어 함수 안에서 국소적으로 선언한다.
type GraphemeSegmenter = {
  segment(input: string): Iterable<{ segment: string }>;
};
function toGraphemes(text: string): string[] {
  const intl = Intl as typeof Intl & {
    Segmenter?: new (
      locale?: string,
      options?: { granularity?: 'grapheme' }
    ) => GraphemeSegmenter;
  };
  if (intl.Segmenter) {
    const segmenter = new intl.Segmenter('ko', { granularity: 'grapheme' });
    return Array.from(segmenter.segment(text), (s) => s.segment);
  }
  return Array.from(text);
}

interface ChatWidgetProps {
  autoFocus?: boolean;
}

export default function ChatWidget({ autoFocus = false }: ChatWidgetProps) {
  const messages = useChatStore((s) => s.messages);
  const isLoading = useChatStore((s) => s.isLoading);
  const send = useChatStore((s) => s.send);

  const [input, setInput] = useState('');
  const [loadingPhraseIndex, setLoadingPhraseIndex] = useState(0);
  const [typedCount, setTypedCount] = useState(0);
  const listEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    if (!isLoading) return;
    setLoadingPhraseIndex(0);
    const id = setInterval(() => {
      setLoadingPhraseIndex((i) => (i + 1) % LOADING_PHRASES.length);
    }, LOADING_PHRASE_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isLoading]);

  const loadingGraphemes = useMemo(
    () => toGraphemes(LOADING_PHRASES[loadingPhraseIndex]),
    [loadingPhraseIndex]
  );

  useEffect(() => {
    if (!isLoading) return;
    setTypedCount(0);
    const id = setInterval(() => {
      setTypedCount((n) => Math.min(n + 1, loadingGraphemes.length));
    }, TYPE_SPEED_MS);
    return () => clearInterval(id);
  }, [isLoading, loadingGraphemes]);

  useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus();
    }
  }, [autoFocus]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (text.length === 0 || isLoading) return;
    setInput('');
    await send(text);
  }

  // 예시 프롬프트는 입력칸을 채우지 않고 곧바로 전송한다.
  async function handleSuggested(question: string) {
    if (isLoading) return;
    setInput('');
    await send(question);
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div
        className="flex-1 overflow-y-auto p-3 space-y-3"
        aria-live="polite"
        aria-busy={isLoading}
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              m.role === 'user' ? 'flex justify-end' : 'flex justify-start'
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
              {loadingGraphemes.slice(0, typedCount).join('')}
              <span className="animate-pulse">▍</span>
            </div>
          </div>
        )}
        <div ref={listEndRef} />
      </div>

      {messages.length === 0 && !isLoading && (
        <div className="px-3 pt-2 pb-1 flex flex-col gap-1.5">
          <p className="text-[11px] text-gray-400 font-medium">예시 질문</p>
          {SUGGESTED_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              disabled={isLoading}
              onClick={() => handleSuggested(q)}
              className="text-left text-xs text-gray-700 bg-blue-50 hover:bg-blue-100 border border-blue-100 rounded-lg px-2.5 py-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="border-t border-gray-200 p-3 flex gap-2"
      >
        <input
          ref={inputRef}
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
