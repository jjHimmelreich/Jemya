import { useState, useCallback } from 'react';
import { sendChat } from '../api/client';
import type { ChatMessage, TokenInfo } from '../types';

let idCounter = 0;
const uid = () => `msg-${++idCounter}-${Date.now()}`;

export function useChat(params: {
  tokenInfo: TokenInfo | null;
  userId?: string;
  playlistId?: string;
  playlistName?: string;
  mcpMode?: boolean;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSuggestions, setLastSuggestions] = useState<string[] | null>(null);

  const send = useCallback(
    async (text: string) => {
      if (!params.tokenInfo || !text.trim()) return;
      setError(null);

      const userMsg: ChatMessage = { id: uid(), role: 'user', content: text, timestamp: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        // Build history without the current message (API adds it internally)
        const history = messages
          .filter((m) => m.role !== 'system')
          .map(({ role, content }) => ({ role, content }));

        const result = await sendChat({
          tokenInfo: params.tokenInfo,
          userMessage: text,
          conversationHistory: history,
          playlistId: params.playlistId,
          playlistName: params.playlistName,
          userId: params.userId,
          mcpMode: params.mcpMode,
        });

        const assistantMsg: ChatMessage = {
          id: uid(),
          role: 'assistant',
          content: result.response,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        if (result.track_suggestions?.length) {
          setLastSuggestions(result.track_suggestions);
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Something went wrong';
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [messages, params],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setLastSuggestions(null);
  }, []);

  return { messages, isLoading, error, lastSuggestions, send, clearMessages };
}
