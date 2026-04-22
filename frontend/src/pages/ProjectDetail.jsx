import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Upload as UploadIcon, Film, Trash2, ArrowLeft,
  Scissors, Play, FileVideo, HardDrive
} from 'lucide-react';
import api from '../utils/api';

export default function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [uploads, setUploads] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef(null);

  // Edit config state
  const [showEditor, setShowEditor] = useState(false);
  const [selectedUploads, setSelectedUploads] = useState([]);
  const [preset, setPreset] = useState('quick_clean');
  const [silenceThreshold, setSilenceThreshold] = useState(400);
  const [fillerRemove, setFillerRemove] = useState(true);
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  const [subtitleStyle, setSubtitleStyle] = useState('bold-overlay');
  const [gradePreset, setGradePreset] = useState('none');
  const [transcriptionBackend, setTranscriptionBackend] = useState('elevenlabs');

  useEffect(() => {
    loadProject();
    loadUploads();
    loadJobs();
  }, [projectId]);

  const loadProject = async () => {
    try {
      const res = await api.get(`/api/projects/${projectId}`);
      setProject(res.data);
    } catch { navigate('/projects'); }
  };

  const loadUploads = async () => {
    try {
      const res = await api.get(`/api/uploads?project_id=${projectId}`);
      setUploads(res.data);
    } catch (err) { console.error(err); }
  };

  const loadJobs = async () => {
    try {
      const res = await api.get(`/api/jobs?project_id=${projectId}`);
      setJobs(res.data);
    } catch (err) { console.error(err); }
  };

  const handleFiles = async (files) => {
    for (const file of files) {
      setUploading(true);
      setUploadProgress(0);
      const formData = new FormData();
      formData.append('project_id', projectId);
      formData.append('file', file);

      try {
        await api.post('/api/uploads', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (e) => {
            setUploadProgress(Math.round((e.loaded / e.total) * 100));
          },
        });
        await loadUploads();
      } catch (err) {
        alert(`Upload failed: ${err.response?.data?.detail || err.message}`);
      }
    }
    setUploading(false);
   setUploadProgress(0);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(f =>
      /\.(mp4|mov|avi|mkv|webm|m4v|flv|wmv|ts|mts)$/i.test(f.name)
    );
    if (files.length) handleFiles(files);
  }, [projectId]);

  const deleteUpload = async (id) => {
    if (!confirm('Delete this video file?')) return;
    try {
      await api.delete(`/api/uploads/${id}`);
      setUploads(uploads.filter(u => u.id !== id));
      setSelectedUploads(selectedUploads.filter(sid => sid !== id));
    } catch { alert('Delete failed'); }
  };

  const toggleSelect = (id) => {
    setSelectedUploads(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const startJob = async () => {
    if (selectedUploads.length === 0) {
      alert('Select at least one video file');
      return;
    }
    try {
      const res = await api.post('/api/jobs', {
        project_id: parseInt(projectId),
        config: {
          upload_ids: selectedUploads,
          preset,
          silence_threshold_ms: silenceThreshold,
          silence_remove: true,
          filler_remove: fillerRemove,
          filler_words: ["umm", "uh", "um", "ah", "like", "you know"],
          grade_preset: gradePreset,
          subtitles_enabled: subtitlesEnabled,
          subtitle_style: subtitleStyle,
          output_resolution: '1080p',
          output_format: 'mp4',
          transcription_backend: transcriptionBackend,
        },
      });
      navigate(`/projects/${projectId}/jobs/${res.data.id}`);
    } catch (err) {
      alert(`Failed to start job: ${err.response?.data?.detail || err.message}`);
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
  };

  const formatDuration = (s) => {
    if (!s) return '--:--';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  if (!project) return <div className="text-center text-muted mt-6">Loading...</div>;

  return (
    <div>
      <div className="page-header">
        <Link to="/projects" className="flex items-center gap-2 text-sm text-muted mb-4" style={{ textDecoration: 'none' }}>
          <ArrowLeft size={14} /> Back to Projects
        </Link>
        <div className="flex justify-between items-center">
          <div>
            <h1>{project.name}</h1>
            <p>{project.description || 'No description'}</p>
          </div>
          <button
            className="btn btn-primary"
            onClick={() => setShowEditor(!showEditor)}
            disabled={uploads.length === 0}
          >
            <Scissors size={16} /> {showEditor ? 'Hide Editor' : 'Start Editing'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: showEditor ? '1fr 380px' : '1fr', gap: 24 }}>
        {/* Left: Upload + Files */}
        <div>
          {/* Dropzone */}
          <div
            className={`dropzone ${dragging ? 'dragging' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            style={{ marginBottom: 24 }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              multiple
              hidden
              onChange={(e) => handleFiles(Array.from(e.target.files))}
            />
            {uploading ? (
              <>
                <div className="dropzone-icon">⏳</div>
                <div className="dropzone-text">Uploading... {uploadProgress}%</div>
                <div className="progress-bar mt-4" style={{ maxWidth: 300, margin: '16px auto 0' }}>
                  <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                </div>
              </>
            ) : (
              <>
                <div className="dropzone-icon">📁</div>
                <div className="dropzone-text">
                  <span className="dropzone-accent">Click to browse</span> or drag & drop video files here
                </div>
                <div className="text-xs text-muted mt-2">
                  Supports: MP4, MOV, AVI, MKV, WebM and more
                </div>
              </>
            )}
          </div>

          {/* File List */}
          <div className="card">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">Video Files ({uploads.length})</h3>
              {showEditor && uploads.length > 0 && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setSelectedUploads(
                    selectedUploads.length === uploads.length ? [] : uploads.map(u => u.id)
                  )}
                >
                  {selectedUploads.length === uploads.length ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>

            {uploads.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon"><FileVideo size={48} /></div>
                <h3>No videos uploaded</h3>
                <p>Upload raw video files to start editing</p>
              </div>
            ) : (
              <div className="file-list">
                {uploads.map(u => (
                  <div key={u.id} className={`file-item ${selectedUploads.includes(u.id) ? 'selected' : ''}`}
                    style={selectedUploads.includes(u.id) ? {
                      background: 'var(--gradient-subtle)',
                      borderColor: 'var(--border-accent)',
                    } : {}}
                  >
                    {showEditor && (
                      <input
                        type="checkbox"
                        checked={selectedUploads.includes(u.id)}
                        onChange={() => toggleSelect(u.id)}
                        style={{ width: 18, height: 18, accentColor: '#8b5cf6' }}
                      />
                    )}
                    <div className="file-icon">
                      <Film size={18} style={{ color: 'var(--text-accent)' }} />
                    </div>
                    <div className="file-info">
                      <div className="file-name">{u.original_filename}</div>
                      <div className="file-meta">
                        <span>⏱ {formatDuration(u.duration)}</span>
                        <span>📐 {u.width}×{u.height}</span>
                        <span><HardDrive size={10} /> {formatSize(u.file_size)}</span>
                        {u.fps && <span>{u.fps} fps</span>}
                      </div>
                    </div>
                    <button className="btn btn-icon" onClick={() => deleteUpload(u.id)}
                      style={{ color: 'var(--text-muted)' }}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Jobs */}
          {jobs.length > 0 && (
            <div className="card mt-4">
              <h3 className="font-semibold mb-4">Edit Jobs ({jobs.length})</h3>
              <div className="file-list">
                {jobs.map(j => (
                  <Link
                    to={`/projects/${projectId}/jobs/${j.id}`}
                    key={j.id}
                    className="file-item"
                    style={{ textDecoration: 'none', color: 'inherit' }}
                  >
                    <div className="file-icon">
                      <Scissors size={16} style={{ color: 'var(--text-accent)' }} />
                    </div>
                    <div className="file-info">
                      <div className="file-name">Job #{j.id} — {j.preset}</div>
                      <div className="file-meta">
                        <span>{j.current_step || 'Queued'}</span>
                        <span>{new Date(j.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                    <span className={`badge badge-${j.status === 'completed' ? 'success' : j.status === 'failed' ? 'error' : j.status === 'running' ? 'running' : 'pending'}`}>
                      {j.status}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Editor Panel */}
        {showEditor && (
          <div className="card" style={{ height: 'fit-content', position: 'sticky', top: 32 }}>
            <h3 className="font-semibold mb-4">⚙️ Edit Configuration</h3>

            <div className="form-group">
              <label className="form-label">Preset</label>
              <select className="form-select" value={preset} onChange={e => setPreset(e.target.value)}>
                <option value="quick_clean">🧹 Quick Clean — Remove silences & fillers</option>
                <option value="full_edit">🎬 Full Edit — Complete pipeline</option>
                <option value="subtitles_only">📝 Subtitles Only — Transcribe & burn subs</option>
                <option value="custom">⚙️ Custom</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Transcription Backend</label>
              <select className="form-select" value={transcriptionBackend} onChange={e => setTranscriptionBackend(e.target.value)}>
                <option value="elevenlabs">ElevenLabs Scribe</option>
                <option value="google">Google TTS</option>
                <option value="whisper">Whisper (Local)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Silence Threshold (ms)</label>
              <input type="number" className="form-input" value={silenceThreshold}
                onChange={e => setSilenceThreshold(parseInt(e.target.value))} min={100} max={2000} step={50} />
              <div className="text-xs text-muted mt-2">Gaps longer than this will be cut</div>
            </div>

            <div className="form-group">
              <label className="form-checkbox">
                <input type="checkbox" checked={fillerRemove} onChange={e => setFillerRemove(e.target.checked)} />
                <span>Remove filler words (umm, uh, like...)</span>
              </label>
            </div>

            <div className="form-group">
              <label className="form-label">Color Grade</label>
              <select className="form-select" value={gradePreset} onChange={e => setGradePreset(e.target.value)}>
                <option value="none">None (original)</option>
                <option value="warm_cinematic">🎥 Warm Cinematic</option>
                <option value="neutral_punch">💪 Neutral Punch</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-checkbox">
                <input type="checkbox" checked={subtitlesEnabled} onChange={e => setSubtitlesEnabled(e.target.checked)} />
                <span>Burn subtitles</span>
              </label>
            </div>

            {subtitlesEnabled && (
              <div className="form-group">
                <label className="form-label">Subtitle Style</label>
                <select className="form-select" value={subtitleStyle} onChange={e => setSubtitleStyle(e.target.value)}>
                  <option value="bold-overlay">BOLD OVERLAY — 2-word, uppercase</option>
                  <option value="natural-sentence">Natural Sentence — 5-word, readable</option>
                </select>
              </div>
            )}

            <div className="mt-4">
              <div className="text-sm text-muted mb-4">
                Selected: {selectedUploads.length} video{selectedUploads.length !== 1 ? 's' : ''}
              </div>
              <button
                className="btn btn-primary btn-lg w-full"
                onClick={startJob}
                disabled={selectedUploads.length === 0}
              >
                <Play size={18} /> Start Editing
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
