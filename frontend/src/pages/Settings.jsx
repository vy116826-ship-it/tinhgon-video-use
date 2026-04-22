import { useState, useEffect } from 'react';
import { Save, Key } from 'lucide-react';

export default function SettingsPage() {
  const [elevenlabsKey, setElevenlabsKey] = useState('');
  const [googleKey, setGoogleKey] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // Load saved keys from localStorage (client-side only)
    setElevenlabsKey(localStorage.getItem('elevenlabs_key') || '');
    setGoogleKey(localStorage.getItem('google_tts_key') || '');
  }, []);

  const handleSave = () => {
    localStorage.setItem('elevenlabs_key', elevenlabsKey);
    localStorage.setItem('google_tts_key', googleKey);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
        <p>Configure API keys and preferences</p>
      </div>

      <div className="card" style={{ maxWidth: 600 }}>
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <Key size={18} /> API Keys
        </h3>

        <div className="form-group">
          <label className="form-label">ElevenLabs API Key</label>
          <input
            type="password"
            className="form-input"
            placeholder="sk-..."
            value={elevenlabsKey}
            onChange={e => setElevenlabsKey(e.target.value)}
          />
          <div className="text-xs text-muted mt-2">
            Used for Scribe transcription. Get one at{' '}
            <a href="https://elevenlabs.io" target="_blank" rel="noopener">elevenlabs.io</a>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Google Cloud API Key</label>
          <input
            type="password"
            className="form-input"
            placeholder="AIza..."
            value={googleKey}
            onChange={e => setGoogleKey(e.target.value)}
          />
          <div className="text-xs text-muted mt-2">
            Used for Google Speech-to-Text. Get one at{' '}
            <a href="https://console.cloud.google.com" target="_blank" rel="noopener">Google Cloud Console</a>
          </div>
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button className="btn btn-primary" onClick={handleSave}>
            <Save size={16} /> Save Settings
          </button>
          {saved && (
            <span className="text-sm" style={{ color: 'var(--color-success)' }}>
              ✅ Settings saved
            </span>
          )}
        </div>
      </div>

      <div className="card mt-4" style={{ maxWidth: 600 }}>
        <h3 className="font-semibold mb-4">ℹ️ About</h3>
        <div className="text-sm text-muted" style={{ lineHeight: 1.8 }}>
          <p><strong>Video-Use Platform</strong> v1.0.0</p>
          <p>Automated video editing powered by FFmpeg and AI transcription.</p>
          <p>
            Based on{' '}
            <a href="https://github.com/browser-use/video-use" target="_blank" rel="noopener">
              browser-use/video-use
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
