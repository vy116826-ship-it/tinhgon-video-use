import { useState, useEffect } from 'react';
import { Save, Key, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import api from '../utils/api';

export default function SettingsPage() {
  const [elevenlabsKey, setElevenlabsKey] = useState('');
  const [googleKey, setGoogleKey] = useState('');
  const [status, setStatus] = useState(null); // null | 'saving' | 'saved' | 'error'
  const [errorMsg, setErrorMsg] = useState('');
  const [keyStatus, setKeyStatus] = useState({
    elevenlabs_configured: false,
    google_configured: false,
    elevenlabs_key_masked: '',
    google_key_masked: '',
  });

  useEffect(() => {
    loadKeyStatus();
  }, []);

  const loadKeyStatus = async () => {
    try {
      const res = await api.get('/api/settings/api-keys');
      setKeyStatus(res.data);
    } catch { /* ignore */ }
  };

  const handleSave = async () => {
    setStatus('saving');
    setErrorMsg('');
    try {
      const payload = {};
      if (elevenlabsKey) payload.elevenlabs_api_key = elevenlabsKey;
      if (googleKey) payload.google_tts_api_key = googleKey;

      await api.put('/api/settings/api-keys', payload);
      setStatus('saved');
      setElevenlabsKey('');
      setGoogleKey('');
      await loadKeyStatus();
      setTimeout(() => setStatus(null), 3000);
    } catch (err) {
      setStatus('error');
      setErrorMsg(err.response?.data?.detail || 'Failed to save');
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>⚙️ Settings</h1>
        <p>Configure API keys for video transcription and editing</p>
      </div>

      <div className="card" style={{ maxWidth: 640 }}>
        <h3 className="font-semibold mb-2 flex items-center gap-2">
          <Key size={18} /> API Keys
        </h3>
        <p className="text-sm text-muted mb-4">
          API keys are required for word-level transcription. Without them, the system uses basic FFmpeg silence detection which only provides coarse results.
        </p>

        {/* Status indicators */}
        <div className="settings-status-grid">
          <div className={`settings-status-item ${keyStatus.elevenlabs_configured ? 'configured' : 'missing'}`}>
            <div className="settings-status-icon">
              {keyStatus.elevenlabs_configured ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
            </div>
            <div>
              <div className="settings-status-label">ElevenLabs Scribe</div>
              <div className="settings-status-value">
                {keyStatus.elevenlabs_configured
                  ? <span className="text-success">{keyStatus.elevenlabs_key_masked}</span>
                  : <span className="text-warning">Not configured</span>
                }
              </div>
            </div>
          </div>
          <div className={`settings-status-item ${keyStatus.google_configured ? 'configured' : 'missing'}`}>
            <div className="settings-status-icon">
              {keyStatus.google_configured ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
            </div>
            <div>
              <div className="settings-status-label">Google Cloud STT</div>
              <div className="settings-status-value">
                {keyStatus.google_configured
                  ? <span className="text-success">{keyStatus.google_key_masked}</span>
                  : <span className="text-warning">Not configured</span>
                }
              </div>
            </div>
          </div>
        </div>

        <div className="settings-divider" />

        <div className="form-group">
          <label className="form-label">ElevenLabs API Key</label>
          <input
            type="password"
            className="form-input"
            placeholder={keyStatus.elevenlabs_configured ? "Leave blank to keep current key" : "Paste your API key here..."}
            value={elevenlabsKey}
            onChange={e => setElevenlabsKey(e.target.value)}
          />
          <div className="text-xs text-muted mt-2" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            Best quality transcription. Get a key at{' '}
            <a href="https://elevenlabs.io/app/settings/api-keys" target="_blank" rel="noopener" style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
              elevenlabs.io <ExternalLink size={10} />
            </a>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Google Cloud API Key</label>
          <input
            type="password"
            className="form-input"
            placeholder={keyStatus.google_configured ? "Leave blank to keep current key" : "Paste your API key here..."}
            value={googleKey}
            onChange={e => setGoogleKey(e.target.value)}
          />
          <div className="text-xs text-muted mt-2" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            Alternative STT backend.{' '}
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener" style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
              Google Cloud Console <ExternalLink size={10} />
            </a>
          </div>
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={status === 'saving' || (!elevenlabsKey && !googleKey)}
          >
            <Save size={16} /> {status === 'saving' ? 'Saving...' : 'Save API Keys'}
          </button>
          {status === 'saved' && (
            <span className="text-sm" style={{ color: 'var(--color-success)' }}>
              ✅ Keys saved and activated!
            </span>
          )}
          {status === 'error' && (
            <span className="text-sm" style={{ color: 'var(--color-error)' }}>
              ❌ {errorMsg}
            </span>
          )}
        </div>
      </div>

      <div className="card mt-4" style={{ maxWidth: 640 }}>
        <h3 className="font-semibold mb-4">📖 How Templates Work</h3>
        <div className="text-sm text-muted" style={{ lineHeight: 1.8 }}>
          <p><strong>1. Transcription</strong> — Audio is transcribed word-by-word using ElevenLabs Scribe or Google STT.</p>
          <p><strong>2. Analysis</strong> — The system detects silences, filler words ("umm", "uh", "like"), and speech boundaries.</p>
          <p><strong>3. Auto-Cut</strong> — Based on the template config, it generates an Edit Decision List (EDL) that removes silences and fillers.</p>
          <p><strong>4. Color Grade</strong> — FFmpeg video filters apply the template's color grading (warm cinematic, neutral punch, etc.).</p>
          <p><strong>5. Subtitles</strong> — Word-level subtitles are generated in the chosen style (bold overlay, natural sentence) and burned into the video.</p>
          <p><strong>6. Render</strong> — The final video is assembled from the kept segments with smooth audio fades.</p>
        </div>
      </div>

      <div className="card mt-4" style={{ maxWidth: 640 }}>
        <h3 className="font-semibold mb-4">ℹ️ About</h3>
        <div className="text-sm text-muted" style={{ lineHeight: 1.8 }}>
          <p><strong>Video-Use Platform</strong> v1.1.0</p>
          <p>Automated video editing powered by FFmpeg and AI transcription.</p>
        </div>
      </div>

      <style>{`
        .settings-status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
        .settings-status-item { display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-primary); background: var(--bg-glass); }
        .settings-status-item.configured { border-color: rgba(16,185,129,0.3); }
        .settings-status-item.missing { border-color: rgba(245,158,11,0.3); }
        .settings-status-icon { display: flex; }
        .settings-status-item.configured .settings-status-icon { color: #10b981; }
        .settings-status-item.missing .settings-status-icon { color: #f59e0b; }
        .settings-status-label { font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
        .settings-status-value { font-size: 0.7rem; font-family: monospace; }
        .text-success { color: #10b981; }
        .text-warning { color: #f59e0b; }
        .settings-divider { border-top: 1px solid var(--border-primary); margin: 16px 0; }
      `}</style>
    </div>
  );
}
