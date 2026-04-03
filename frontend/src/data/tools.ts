export interface Tool {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: 'installed' | 'available' | 'coming-soon';
  url?: string;
  installation?: string;
}

export const TOOLS: Tool[] = [
  {
    id: 'spotify-crossfade',
    name: 'Spotify Crossfade',
    description:
      'Add smooth crossfade transitions between tracks on Spotify Web Player. Fade out the current track while fading in the next one with customizable duration (1-10 seconds).',
    icon: '🎵',
    status: 'available',
    url: 'https://github.com/jjHimmelreich/Jemya/tree/feature/migrate-to-fastapi-react/tools/spotify-crossfade-extension',
    installation: 'chrome-extension',
  },
  {
    id: 'dj-mixer',
    name: 'DJ Mixer',
    description:
      'A DJ mixing tool that lets you blend, cue, and cross-fade your playlists like a real DJ deck. Load two tracks side by side and build live mixes on the fly.',
    icon: '🎛️',
    status: 'available',
    url: 'https://github.com/jjHimmelreich/DJMixer',
    installation: 'standalone',
  },
  {
    id: 'playlist-merger',
    name: 'Playlist Merger Pro',
    description:
      'Merge multiple playlists into one with smart deduplication and ordering. Coming soon with batch operations.',
    icon: '🎯',
    status: 'coming-soon',
  },
];
