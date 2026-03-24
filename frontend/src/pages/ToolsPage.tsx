import { useState } from 'react';
import styles from './ToolsPage.module.css';

interface Tool {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: 'installed' | 'available' | 'coming-soon';
  url?: string;
  installation?: string;
}

const TOOLS: Tool[] = [
  {
    id: 'spotify-crossfade',
    name: 'Spotify Crossfade',
    description: 'Add smooth crossfade transitions between tracks on Spotify Web Player. Fade out the current track while fading in the next one with customizable duration (1-10 seconds).',
    icon: '🎵',
    status: 'available',
    url: 'https://github.com/jjHimmelreich/Jemya/tree/feature/migrate-to-fastapi-react/tools/spotify-crossfade-extension',
    installation: 'chrome-extension',
  },
  {
    id: 'playlist-merger',
    name: 'Playlist Merger Pro',
    description: 'Merge multiple playlists into one with smart deduplication and ordering. Coming soon with batch operations.',
    icon: '🎯',
    status: 'coming-soon',
  },
];

function ToolCard({ tool }: { tool: Tool }) {
  const [expanded, setExpanded] = useState(false);

  const getStatusColor = (status: Tool['status']) => {
    switch (status) {
      case 'installed':
        return '#4CAF50';
      case 'available':
        return '#3B7EA5';
      case 'coming-soon':
        return '#666';
      default:
        return '#999';
    }
  };

  const getStatusText = (status: Tool['status']) => {
    switch (status) {
      case 'installed':
        return '✓ Installed';
      case 'available':
        return 'Available';
      case 'coming-soon':
        return 'Coming Soon';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className={styles.toolCard}>
      <div className={styles.toolHeader}>
        <div className={styles.toolTitleSection}>
          <span className={styles.toolIcon}>{tool.icon}</span>
          <div className={styles.toolInfo}>
            <h3 className={styles.toolName}>{tool.name}</h3>
            <p className={styles.toolDescription}>{tool.description}</p>
          </div>
        </div>
        <div className={styles.toolActions}>
          <span
            className={styles.statusBadge}
            style={{ borderColor: getStatusColor(tool.status) }}
          >
            {getStatusText(tool.status)}
          </span>
          {tool.status === 'available' && (
            <button
              className={styles.expandBtn}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? '▼' : '▶'}
            </button>
          )}
        </div>
      </div>

      {expanded && tool.status === 'available' && (
        <div className={styles.toolDetails}>
          <h4>Installation Instructions</h4>
          {tool.id === 'spotify-crossfade' && (
            <ol className={styles.instructionsList}>
              <li>
                <strong>Clone or download the extension:</strong> Navigate to<br/>
                <code>tools/spotify-crossfade-extension</code> in the Jemya repository
              </li>
              <li>
                <strong>Open Chrome and go to</strong> <code>chrome://extensions/</code>
              </li>
              <li>
                <strong>Enable "Developer mode"</strong> (toggle in top-right)
              </li>
              <li>
                <strong>Click "Load unpacked"</strong> and select the <code>spotify-crossfade-extension</code> folder
              </li>
              <li>
                <strong>Visit Spotify Web Player</strong> and click the extension icon to configure
              </li>
            </ol>
          )}

          <div className={styles.installButton}>
            <a href={tool.url} target="_blank" rel="noreferrer" className={styles.downloadBtn}>
              📦 View on GitHub
            </a>
          </div>

          <div className={styles.features}>
            <h4>Features</h4>
            <ul>
              <li>✨ Smooth crossfade transitions between tracks</li>
              <li>⚙️ Configurable fade duration (1-10 seconds)</li>
              <li>🎚️ Enable/disable with one click</li>
              <li>🚀 Lightweight with minimal performance impact</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export function ToolsPage() {
  const available = TOOLS.filter((t) => t.status !== 'coming-soon');
  const comingSoon = TOOLS.filter((t) => t.status === 'coming-soon');

  return (
    <div className={styles.toolsPage}>
      <div className={styles.toolsHeader}>
        <h1>🔧 Jemya Tools</h1>
        <p>Enhance your Spotify experience with community-created tools and integrations.</p>
      </div>

      {available.length > 0 && (
        <section className={styles.toolsSection}>
          <h2>Available Tools</h2>
          <div className={styles.toolsList}>
            {available.map((tool) => (
              <ToolCard key={tool.id} tool={tool} />
            ))}
          </div>
        </section>
      )}

      {comingSoon.length > 0 && (
        <section className={styles.toolsSection}>
          <h2>Coming Soon</h2>
          <div className={styles.toolsList}>
            {comingSoon.map((tool) => (
              <ToolCard key={tool.id} tool={tool} />
            ))}
          </div>
        </section>
      )}

      <div className={styles.developersSection}>
        <h3>🚀 Build Your Own Tool</h3>
        <p>
          Interested in creating a tool? Check out our{' '}
          <a href="https://github.com/jjHimmelreich/Jemya/blob/main/docs/TOOLS-DEV-GUIDE.md" target="_blank" rel="noreferrer">
            developer guide
          </a>{' '}
          for creating Jemya-compatible tools.
        </p>
      </div>
    </div>
  );
}
