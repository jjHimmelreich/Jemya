import ReactMarkdown from 'react-markdown';
import type { ChatMessage } from '../types';
import styles from './MessageBubble.module.css';

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  return (
    <div className={`${styles.bubble} ${isUser ? styles.user : styles.assistant}`}>
      <div className={styles.label}>{isUser ? 'You' : 'Jemya'}</div>
      <div className={styles.content}>
        {isUser ? (
          <span>{message.content}</span>
        ) : (
          <ReactMarkdown>{message.content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
