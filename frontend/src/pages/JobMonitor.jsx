import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Download, XCircle, CheckCircle2,
  Clock, Zap, AlertCircle, Loader, RefreshCw
} from 'lucide-react';
import api, { API_BASE } from '../utils/api';

export default function JobMonitor() {
  const { projectId, jobId } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadJob();
    // Poll every 2 seconds while running
    const interval = setInterval(() => {
      loadJob(true);
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId]);

  const loadJob = async (silent = false) => {
    try {
      const res = await api.get(`/api/jobs/${jobId}`);
      setJob(res.data);
      // Stop polling if job is done
      if (['completed', 'failed', 'cancelled'].includes(res.data.status)) {
        // keep but reduce frequency
      }
    } catch (err) {
      if (!silent) console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const cancelJob = async () => {
    if (!confirm('Cancel this job?')) return;
    try {
      await api.post(`/api/jobs/${jobId}/cancel`);
      loadJob();
    } catch (err) {
      alert('Failed to cancel');
    }
  };

  const stepIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle2 size={16} />;
      case 'running': return <Loader size={16} className="spinning" />;
      case 'failed': return <AlertCircle size={16} />;
      case 'skipped': return <span style={{ opacity: 0.3 }}>⏭</span>;
      default: return <Clock size={16} />;
    }
  };

  const statusColor = (status) => {
    switch (status) {
      case 'completed': return 'var(--color-success)';
      case 'running': return '#a78bfa';
      case 'failed': return 'var(--color-error)';
      default: return 'var(--text-muted)';
    }
  };

  if (loading) return <div className="text-center text-muted mt-6">Loading job...</div>;
  if (!job) return <div className="text-center text-muted mt-6">Job not found</div>;

  const isRunning = ['pending', 'running'].includes(job.status);
  const isDone = job.status === 'completed';
  const isFailed = job.status === 'failed';

  return (
    <div>
      <div className="page-header">
        <Link to={`/projects/${projectId}`} className="flex items-center gap-2 text-sm text-muted mb-4" style={{ textDecoration: 'none' }}>
          <ArrowLeft size={14} /> Back to Project
        </Link>
        <div className="flex justify-between items-center">
          <div>
            <h1>Job #{job.id}</h1>
            <p>Preset: {job.preset} • Created {new Date(job.created_at).toLocaleString()}</p>
          </div>
          <div className="flex gap-3">
            {isRunning && (
              <button className="btn btn-danger" onClick={cancelJob}>
                <XCircle size={16} /> Cancel
              </button>
            )}
            {isDone && job.output_path && (
              <a
                href={`${API_BASE}/api/jobs/${job.id}/download`}
                className="btn btn-primary"
                target="_blank"
                rel="noopener"
                onClick={(e) => {
                  e.preventDefault();
                  const token = localStorage.getItem('token');
                  fetch(`${API_BASE}/api/jobs/${job.id}/download`, {
                    headers: { Authorization: `Bearer ${token}` },
                  })
                    .then(res => res.blob())
                    .then(blob => {
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = `video_use_output_${job.id}.mp4`;
                      a.click();
                      window.URL.revokeObjectURL(url);
                    });
                }}
              >
                <Download size={16} /> Download Output
              </a>
            )}
            <button className="btn btn-secondary btn-sm" onClick={() => loadJob()}>
              <RefreshCw size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Overall Progress */}
      <div className="card mb-6">
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-3">
            <span style={{ fontSize: '1.5rem' }}>
              {isDone ? '✅' : isFailed ? '❌' : isRunning ? '⚡' : '⏳'}
            </span>
            <div>
              <div className="font-semibold" style={{ fontSize: '1.1rem' }}>
                {isDone ? 'Processing Complete!' :
                 isFailed ? 'Processing Failed' :
                 job.status === 'cancelled' ? 'Cancelled' :
                 'Processing...'}
              </div>
              <div className="text-sm text-muted">
                {job.current_step || 'Waiting to start'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: statusColor(job.status) }}>
              {Math.round(job.progress)}%
            </div>
          </div>
        </div>
        <div className="progress-bar progress-bar-lg">
          <div
            className="progress-bar-fill"
            style={{
              width: `${job.progress}%`,
              background: isFailed
                ? 'var(--color-error)'
                : job.status === 'cancelled'
                ? 'var(--color-warning)'
                : undefined,
            }}
          />
        </div>
        {job.started_at && (
          <div className="text-xs text-muted mt-2">
            Started: {new Date(job.started_at).toLocaleString()}
            {job.completed_at && ` • Finished: ${new Date(job.completed_at).toLocaleString()}`}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Steps */}
        <div className="card">
          <h3 className="font-semibold mb-4">Pipeline Steps</h3>
          <div className="step-tracker">
            {(job.steps || []).map((step) => (
              <div
                key={step.id}
                className={`step-item ${step.status === 'running' ? 'active' : ''} ${step.status === 'completed' ? 'completed' : ''}`}
              >
                <div className={`step-icon ${step.status}`}>
                  {stepIcon(step.status)}
                </div>
                <div className="step-info" style={{ flex: 1 }}>
                  <div className="step-name">{step.display_name}</div>
                  {step.log_output && (
                    <div className="step-log">{step.log_output}</div>
                  )}
                </div>
                <div style={{ width: 60 }}>
                  {step.status === 'running' && (
                    <>
                      <div className="progress-bar" style={{ height: 4 }}>
                        <div className="progress-bar-fill" style={{ width: `${step.progress}%` }} />
                      </div>
                      <div className="text-xs text-muted" style={{ textAlign: 'right', marginTop: 2 }}>
                        {Math.round(step.progress)}%
                      </div>
                    </>
                  )}
                  {step.status === 'completed' && (
                    <span className="text-xs" style={{ color: 'var(--color-success)' }}>Done</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Details & Error */}
        <div>
          {/* Config */}
          <div className="card mb-4">
            <h3 className="font-semibold mb-4">Configuration</h3>
            <div className="text-sm" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px' }}>
              <span className="text-muted">Preset:</span>
              <span>{job.config?.preset || '-'}</span>
              <span className="text-muted">Silence threshold:</span>
              <span>{job.config?.silence_threshold_ms || 400}ms</span>
              <span className="text-muted">Filler removal:</span>
              <span>{job.config?.filler_remove ? '✅ Yes' : '❌ No'}</span>
              <span className="text-muted">Subtitles:</span>
              <span>{job.config?.subtitles_enabled ? `✅ ${job.config?.subtitle_style}` : '❌ No'}</span>
              <span className="text-muted">Color grade:</span>
              <span>{job.config?.grade_preset || 'none'}</span>
              <span className="text-muted">Transcription:</span>
              <span>{job.config?.transcription_backend || 'elevenlabs'}</span>
              <span className="text-muted">Videos:</span>
              <span>{job.config?.upload_ids?.length || 0} file(s)</span>
            </div>
          </div>

          {/* Output info */}
          {isDone && job.output_size && (
            <div className="card mb-4">
              <h3 className="font-semibold mb-4">✅ Output</h3>
              <div className="text-sm">
                <span className="text-muted">Size: </span>
                <span>{(job.output_size / (1024 * 1024)).toFixed(1)} MB</span>
              </div>
            </div>
          )}

          {/* Error */}
          {isFailed && job.error_message && (
            <div className="card" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
              <h3 className="font-semibold mb-4" style={{ color: 'var(--color-error)' }}>❌ Error</h3>
              <div className="log-viewer" style={{ maxHeight: 200 }}>
                <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--color-error)', fontSize: '0.75rem' }}>
                  {job.error_message}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .spinning {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
