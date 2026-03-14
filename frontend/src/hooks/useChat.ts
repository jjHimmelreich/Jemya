import { useState, useCallback } from 'react';
import { sendChat } from '../api/client';
import type { ChatMessage, TokenInfo } from '../types';

let idCounter = 0;
const uid = () => `msg-${++idCounter}-${Date.now()}`;

const MUTATING_TOOLS = new Set(['add_tracks', 'remove_tracks', 'replace_playlist', 'create_playlist']);

export function useChat(params: {
  tokenInfo: TokenInfo | null;
  userId?: string;
  playlistId?: string;
  playlistName?: string;
  mcpMode?: boolean;
  ensureValidToken?: () => Promise<TokenInfo | null>;
  onPlaylistMutated?: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSuggestions, setLastSuggestions] = useState<string[] | null>(null);

  const send = useCallback(
    async (text: string) => {
      if (!params.tokenInfo || !text.trim()) return;
      setError(null);

      // Always use a fresh token before sending
      const freshToken = params.ensureValidToken
        ? await params.ensureValidToken()
        : params.tokenInfo;
      if (!freshToken) return;

      const userMsg: ChatMessage = { id: uid(), role: 'user', content: text, timestamp: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        // Build history without the current message (API adds it internally)
        const history = messages
          .filter((m) => m.role !== 'system')
          .map(({ role, content }) => ({ role, content }));

        const result = await sendChat({
          tokenInfo: freshToken,
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

        // Refresh sidebar playlist list when the AI mutated Spotify data
        if (
          params.onPlaylistMutated &&
          result.tool_calls?.some((tc) => MUTATING_TOOLS.has(tc.name))
        ) {
          params.onPlaylistMutated();
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

  const injectMessage = useCallback((content: string, role: 'user' | 'assistant' = 'user') => {
    const msg: ChatMessage = { id: uid(), role, content, timestamp: Date.now() };
    setMessages((prev) => [...prev, msg]);
  }, []);

  // Restore a full saved conversation (e.g. loaded from server)
  const restoreMessages = useCallback((saved: { role: string; content: string }[]) => {
    const restored: ChatMessage[] = saved
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({
        id: uid(),
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: Date.now(),
      }));
    setMessages(restored);
  }, []);

  return { messages, isLoading, error, lastSuggestions, send, clearMessages, injectMessage, restoreMessages };
}
