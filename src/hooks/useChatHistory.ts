import { useCallback, useContext, useRef } from 'react';
import type { UIMessage } from 'ai';
import { AuthContext } from 'src/auth.context';
import { AuthConfigContext } from 'src/authConfig.context';

interface ChatHistoryMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

interface ChatHistoryResponse {
  messages: ChatHistoryMessage[];
}

function toUIMessage(message: ChatHistoryMessage): UIMessage {
  return {
    id: message.id,
    role: message.role,
    parts: [{ type: 'text', text: message.text }],
  };
}

/**
 * Returns a stable fetcher for a chat thread's persisted messages, mapped into
 * the AI SDK UIMessage shape so they can hydrate `useChat`. Resolves to an
 * empty array when auth is required but no token is available yet, or on any
 * failure — a missing history should never block starting a conversation.
 */
export function useChatHistory(): (threadId: string) => Promise<UIMessage[]> {
  const { accessToken } = useContext(AuthContext);
  const { auth_required } = useContext(AuthConfigContext);
  const accessTokenRef = useRef(accessToken);
  accessTokenRef.current = accessToken;
  const authRequiredRef = useRef(auth_required);
  authRequiredRef.current = auth_required;

  return useCallback(async (threadId: string): Promise<UIMessage[]> => {
    if (authRequiredRef.current && !accessTokenRef.current) return [];
    const headers: Record<string, string> = {};
    if (accessTokenRef.current)
      headers.Authorization = `Bearer ${accessTokenRef.current}`;
    try {
      const res = await fetch(
        `/api/v1/chat/history?thread_id=${encodeURIComponent(threadId)}`,
        { headers },
      );
      if (!res.ok) return [];
      const data = (await res.json()) as ChatHistoryResponse;
      return data.messages.map(toUIMessage);
    } catch {
      return [];
    }
  }, []);
}
