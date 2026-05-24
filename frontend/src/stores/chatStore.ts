import { create } from 'zustand';

import { postChat, type StudentRef } from '../api/chat';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  text: string;
  refs?: StudentRef[];
}

interface ChatState {
  isOpen: boolean;
  messages: ChatMessage[];
  threadId: string | null;
  isLoading: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
  send: (text: string) => Promise<void>;
  reset: () => void;
}

function resolveTokens(reply: string, refs: StudentRef[]): string {
  if (refs.length === 0) return reply;
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

export const useChatStore = create<ChatState>((set, get) => ({
  isOpen: false,
  messages: [],
  threadId: null,
  isLoading: false,

  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  reset: () => set({ messages: [], threadId: null, isLoading: false }),

  send: async (rawText: string) => {
    const text = rawText.trim();
    if (text.length === 0 || get().isLoading) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      text,
    };
    set((s) => ({
      messages: [...s.messages, userMsg],
      isLoading: true,
    }));

    try {
      const res = await postChat({ thread_id: get().threadId, message: text });
      set((s) => ({
        threadId: res.thread_id,
        messages: [
          ...s.messages,
          {
            id: `a-${Date.now()}`,
            role: 'assistant',
            text: resolveTokens(res.reply, res.referenced_students),
            refs: res.referenced_students,
          },
        ],
      }));
    } catch (err: unknown) {
      const status =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      const msg =
        status === 429
          ? '요청이 너무 잦습니다. 잠시 후 다시 시도하세요.'
          : '답변을 가져오지 못했습니다. 잠시 후 다시 시도하세요.';
      set((s) => ({
        messages: [
          ...s.messages,
          { id: `e-${Date.now()}`, role: 'error', text: msg },
        ],
      }));
    } finally {
      set({ isLoading: false });
    }
  },
}));
