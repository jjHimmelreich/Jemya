import { useEffect, useRef, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import type { ChatMessage } from '../types';
import styles from './ChatWindow.module.css';

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  onSend: (text: string) => void;
  lastSuggestions?: string[] | null;
  onPreview?: () => void;
  previewLoading?: boolean;
  disabled?: boolean;
}

export function ChatWindow({
  messages,
  isLoading,
  error,
  onSend,
  lastSuggestions,
  onPreview,
  previewLoading,
  disabled,
}: Props) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll - works natively, no JS injection needed
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const submit = () => {
    const text = input.trim();
    if (!text || isLoading || disabled) return;
    setInput('');
    onSend(text);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.messages}>
        {messages.length === 0 && !isLoading && (
          <div className={styles.empty}>
            Ask Jam-ya to enrich, reorder, or transform your playlist ✨
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {isLoading && (
          <div className={`${styles.bubble} ${styles.thinking}`}>
            <span className={styles.dot} />
            <span className={styles.dot} />
            <span className={styles.dot} />
          </div>
        )}
        {error && <div className={styles.error}>{error}</div>}
        <div ref={bottomRef} />
      </div>

      {lastSuggestions && lastSuggestions.length > 0 && (
        <div className={styles.actionBar}>
          {onPreview && (
            <button className={styles.previewBtn} onClick={onPreview} disabled={previewLoading}>
              {previewLoading ? 'Searching…' : 'Preview & Save'}
            </button>
          )}
        </div>
      )}

      <div className={styles.inputRow}>
        <textarea
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder={disabled ? 'Select a playlist first…' : 'Message Jam-ya…'}
          rows={2}
          disabled={isLoading || disabled}
        />
        <button
          className={styles.sendBtn}
          onClick={submit}
          disabled={!input.trim() || isLoading || disabled}
        >
          Send
        </button>
      </div>
    </div>
  );
}
