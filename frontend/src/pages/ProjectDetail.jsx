import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Upload as UploadIcon, Film, Trash2, ArrowLeft,
  Scissors, Play, FileVideo, HardDrive, Palette, Star, ChevronDown, X
} from 'lucide-react';
import api from '../utils/api';

const DIFF_COLORS = { easy: '#10b981', medium: '#f59e0b', advanced: '#ef4444' };

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

  // Template state
  const [templates, setTemplates] = useState([]);
  const [templateCategories, setTemplateCategories] = useState([]);
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [templateFilter, setTemplateFilter] = useState('');

  useEffect(() => {
    loadProject();
    loadUploads();
    loadJobs();
    loadTemplates();
  }, [projectId]);

  // Check for template from session (coming from Template Library page)
  useEffect(() => {
    const tplConfig = sessionStorage.getItem('template_config');
    const tplName = sessionStorage.getItem('template_name');
    if (tplConfig && tplName) {
      applyConfig(JSON.parse(tplConfig), tplName);
      sessionStorage.removeItem('template_config');
      sessionStorage.removeItem('template_name');
    }
  }, []);

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

  const loadTemplates = async () => {
    try {
      const [tplRes, catRes] = await Promise.all([
        api.get('/api/templates?sort=popular&limit=50'),
        api.get('/api/templates/categories'),
      ]);
      setTemplates(tplRes.data);
      setTemplateCategories(catRes.data);
    } catch { /* templates are optional */ }
  };

  const applyConfig = (config, templateName = null) => {
    if (config.preset) setPreset(config.preset);
    if (config.silence_threshold_ms !== undefined) setSilenceThreshold(config.silence_threshold_ms);
    if (config.filler_remove !== undefined) setFillerRemove(config.filler_remove);
    if (config.subtitles_enabled !== undefined) setSubtitlesEnabled(config.subtitles_enabled);
    if (config.subtitle_style) setSubtitleStyle(config.subtitle_style);
    if (config.grade_preset) setGradePreset(config.grade_preset);
    if (config.transcription_backend) setTranscriptionBackend(config.transcription_backend);
    if (templateName) {
      setSelectedTemplate({ name: templateName, config });
    }
  };

  const selectTemplate = async (tpl) => {
    try { await api.post(`/api/templates/${tpl.id}/use`); } catch {}
    applyConfig(tpl.config, tpl.name);
    setSelectedTemplate(tpl);
    setShowTemplatePicker(false);
  };

  const clearTemplate = () => {
    setSelectedTemplate(null);
    setPreset('quick_clean');
    setSilenceThreshold(400);
    setFillerRemove(true);
    setSubtitlesEnabled(true);
    setSubtitleStyle('bold-overlay');
    setGradePreset('none');
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
          template_name: selectedTemplate?.name || null,
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

  const filteredTemplates = templateFilter
    ? templates.filter(t => t.category_slug === templateFilter)
    : templates;

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

      <div style={{ display: 'grid', gridTemplateColumns: showEditor ? '1fr 400px' : '1fr', gap: 24 }}>
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

            {/* Template Selector */}
            <div className="form-group">
              <label className="form-label">
                <Palette size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                Template Preset
              </label>

              {selectedTemplate ? (
                <div className="tpl-selected">
                  <div className="tpl-selected-info">
                    <div className="tpl-selected-name">{selectedTemplate.name}</div>
                    <div className="tpl-selected-meta">
                      {selectedTemplate.difficulty && (
                        <span style={{ color: DIFF_COLORS[selectedTemplate.difficulty] }}>● {selectedTemplate.difficulty}</span>
                      )}
                      {selectedTemplate.aspect_ratio && <span>{selectedTemplate.aspect_ratio}</span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-sm btn-secondary" onClick={() => setShowTemplatePicker(true)}>Change</button>
                    <button className="btn btn-sm btn-icon" onClick={clearTemplate} title="Clear template"><X size={14} /></button>
                  </div>
                </div>
              ) : (
                <button className="tpl-picker-btn" onClick={() => setShowTemplatePicker(true)}>
                  <Palette size={16} />
                  <span>Browse Templates...</span>
                  <ChevronDown size={14} style={{ marginLeft: 'auto' }} />
                </button>
              )}
            </div>

            <div className="tpl-divider">
              <span>OR configure manually</span>
            </div>

            <div className="form-group">
              <label className="form-label">Preset</label>
              <select className="form-select" value={preset} onChange={e => { setPreset(e.target.value); setSelectedTemplate(null); }}>
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
                {selectedTemplate && <span> • Template: <strong>{selectedTemplate.name}</strong></span>}
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

      {/* Template Picker Modal */}
      {showTemplatePicker && (
        <div className="modal-overlay" onClick={() => setShowTemplatePicker(false)}>
          <div className="modal tpl-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2><Palette size={20} /> Choose Template</h2>
              <button className="modal-close" onClick={() => setShowTemplatePicker(false)}>✕</button>
            </div>

            {/* Category filter pills */}
            <div className="tpl-modal-pills">
              <button className={`pill-sm ${!templateFilter ? 'active' : ''}`} onClick={() => setTemplateFilter('')}>All</button>
              {templateCategories.map(c => (
                <button key={c.slug} className={`pill-sm ${templateFilter === c.slug ? 'active' : ''}`}
                  onClick={() => setTemplateFilter(templateFilter === c.slug ? '' : c.slug)}>
                  {c.icon} {c.name.replace(/^[^\s]+\s/, '')}
                </button>
              ))}
            </div>

            {/* Template grid */}
            <div className="tpl-modal-grid">
              {filteredTemplates.map(tpl => (
                <div key={tpl.id} className="tpl-modal-card" onClick={() => selectTemplate(tpl)}>
                  <div className="tpl-modal-thumb">
                    <img src={tpl.thumbnail_url} alt={tpl.name} loading="lazy" />
                    {tpl.is_featured && <div className="tpl-modal-star"><Star size={10} /></div>}
                    {tpl.duration_hint && <div className="tpl-modal-dur">{tpl.duration_hint}</div>}
                  </div>
                  <div className="tpl-modal-body">
                    <div className="tpl-modal-name">{tpl.name}</div>
                    <div className="tpl-modal-desc">{tpl.description}</div>
                    <div className="tpl-modal-meta">
                      <span>👁 {tpl.use_count.toLocaleString()}</span>
                      <span style={{ color: DIFF_COLORS[tpl.difficulty] }}>● {tpl.difficulty}</span>
                      <span>{tpl.aspect_ratio}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .tpl-selected { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--gradient-subtle); border: 1px solid var(--border-accent); border-radius: var(--radius-sm); }
        .tpl-selected-name { font-weight: 600; font-size: 0.9rem; color: var(--text-accent); }
        .tpl-selected-meta { font-size: 0.7rem; color: var(--text-muted); display: flex; gap: 8px; margin-top: 2px; }

        .tpl-picker-btn { width: 100%; display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: var(--bg-input); border: 1px dashed var(--border-primary); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 0.85rem; cursor: pointer; transition: all var(--transition-fast); font-family: inherit; }
        .tpl-picker-btn:hover { border-color: var(--border-accent); color: var(--text-accent); background: var(--gradient-subtle); }

        .tpl-divider { text-align: center; margin: 16px 0; position: relative; }
        .tpl-divider::before { content: ''; position: absolute; left: 0; right: 0; top: 50%; border-top: 1px solid var(--border-primary); }
        .tpl-divider span { position: relative; background: var(--bg-card); padding: 0 12px; font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

        .tpl-modal { max-width: 700px; max-height: 80vh; display: flex; flex-direction: column; }
        .tpl-modal-pills { display: flex; gap: 6px; flex-wrap: wrap; padding: 0 0 16px; }
        .pill-sm { padding: 5px 12px; border-radius: 14px; border: 1px solid var(--border-primary); background: transparent; color: var(--text-secondary); font-size: 0.72rem; cursor: pointer; transition: all var(--transition-fast); white-space: nowrap; font-family: inherit; }
        .pill-sm:hover { border-color: var(--border-hover); }
        .pill-sm.active { background: var(--gradient-subtle); border-color: var(--border-accent); color: var(--text-accent); }

        .tpl-modal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; overflow-y: auto; max-height: 50vh; padding-right: 4px; }
        .tpl-modal-card { background: var(--bg-glass); border: 1px solid var(--border-primary); border-radius: var(--radius-sm); overflow: hidden; cursor: pointer; transition: all var(--transition-fast); }
        .tpl-modal-card:hover { border-color: var(--border-accent); box-shadow: var(--shadow-glow); transform: translateY(-2px); }

        .tpl-modal-thumb { position: relative; height: 100px; overflow: hidden; }
        .tpl-modal-thumb img { width: 100%; height: 100%; object-fit: cover; }
        .tpl-modal-star { position: absolute; top: 4px; right: 4px; background: rgba(251,191,36,0.9); padding: 2px; border-radius: 50%; color: white; display: flex; }
        .tpl-modal-dur { position: absolute; bottom: 4px; right: 4px; background: rgba(0,0,0,0.7); padding: 1px 6px; border-radius: 6px; font-size: 0.6rem; color: white; }

        .tpl-modal-body { padding: 8px 10px; }
        .tpl-modal-name { font-size: 0.8rem; font-weight: 600; line-height: 1.3; margin-bottom: 2px; }
        .tpl-modal-desc { font-size: 0.65rem; color: var(--text-muted); line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 6px; }
        .tpl-modal-meta { display: flex; gap: 8px; font-size: 0.6rem; color: var(--text-muted); }
      `}</style>
    </div>
  );
}
