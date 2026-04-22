import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Film, FolderOpen, Zap, CheckCircle2, AlertCircle, Clock, Plus } from 'lucide-react';
import api from '../utils/api';
import { useWebSocket } from '../hooks/useWebSocket';

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const { data: wsData } = useWebSocket(null); // dashboard-wide

  useEffect(() => {
    loadData();
  }, []);

  // Refresh on WebSocket update
  useEffect(() => {
    if (wsData) loadData();
  }, [wsData]);

  const loadData = async () => {
    try {
      const [projRes, jobRes] = await Promise.all([
        api.get('/api/projects'),
        api.get('/api/jobs'),
      ]);
      setProjects(projRes.data);
      setRecentJobs(jobRes.data.slice(0, 5));
    } catch (err) {
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  };

  const stats = {
    projects: projects.length,
    activeJobs: recentJobs.filter(j => j.status === 'running' || j.status === 'pending').length,
    completed: recentJobs.filter(j => j.status === 'completed').length,
    failed: recentJobs.filter(j => j.status === 'failed').length,
  };

  const statusBadge = (status) => {
    const map = {
      pending: { cls: 'badge-pending', icon: <Clock size={10} />, label: 'Pending' },
      running: { cls: 'badge-running', icon: <Zap size={10} />, label: 'Running' },
      completed: { cls: 'badge-success', icon: <CheckCircle2 size={10} />, label: 'Completed' },
      failed: { cls: 'badge-error', icon: <AlertCircle size={10} />, label: 'Failed' },
      cancelled: { cls: 'badge-warning', icon: <AlertCircle size={10} />, label: 'Cancelled' },
    };
    const s = map[status] || map.pending;
    return <span className={`badge ${s.cls}`}>{s.icon} {s.label}</span>;
  };

  if (loading) {
    return <div className="text-center mt-6 text-muted">Loading dashboard...</div>;
  }

  return (
    <div>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Dashboard</h1>
          <p>Overview of your video editing projects</p>
        </div>
        <Link to="/projects" className="btn btn-primary">
          <Plus size={16} /> New Project
        </Link>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(139,92,246,0.15)', color: '#a78bfa' }}>
            <FolderOpen size={20} />
          </div>
          <div className="stat-value">{stats.projects}</div>
          <div className="stat-label">Projects</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(6,182,212,0.15)', color: '#06b6d4' }}>
            <Zap size={20} />
          </div>
          <div className="stat-value">{stats.activeJobs}</div>
          <div className="stat-label">Active Jobs</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
            <CheckCircle2 size={20} />
          </div>
          <div className="stat-value">{stats.completed}</div>
          <div className="stat-label">Completed</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>
            <AlertCircle size={20} />
          </div>
          <div className="stat-value">{stats.failed}</div>
          <div className="stat-label">Failed</div>
        </div>
      </div>

      {/* Recent Jobs */}
      <div className="card mb-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold">Recent Jobs</h3>
        </div>
        {recentJobs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🎬</div>
            <h3>No jobs yet</h3>
            <p>Create a project and start editing videos</p>
          </div>
        ) : (
          <div className="file-list">
            {recentJobs.map(job => (
              <Link
                to={`/projects/${job.project_id}/jobs/${job.id}`}
                key={job.id}
                className="file-item"
                style={{ textDecoration: 'none', color: 'inherit' }}
              >
                <div className="file-icon">
                  <Film size={18} style={{ color: 'var(--text-accent)' }} />
                </div>
                <div className="file-info">
                  <div className="file-name">Job #{job.id} — {job.preset}</div>
                  <div className="file-meta">
                    <span>{job.current_step || 'Waiting...'}</span>
                    <span>{new Date(job.created_at).toLocaleString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {job.status === 'running' && (
                    <div style={{ width: 80 }}>
                      <div className="progress-bar">
                        <div className="progress-bar-fill" style={{ width: `${job.progress}%` }} />
                      </div>
                      <div className="text-xs text-muted mt-2" style={{ textAlign: 'center' }}>
                        {Math.round(job.progress)}%
                      </div>
                    </div>
                  )}
                  {statusBadge(job.status)}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Projects */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold">Projects</h3>
          <Link to="/projects" className="btn btn-secondary btn-sm">View All</Link>
        </div>
        {projects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📁</div>
            <h3>No projects</h3>
            <p>Create your first project to get started</p>
            <Link to="/projects" className="btn btn-primary">
              <Plus size={16} /> Create Project
            </Link>
          </div>
        ) : (
          <div className="card-grid">
            {projects.slice(0, 4).map(p => (
              <Link
                to={`/projects/${p.id}`}
                key={p.id}
                className="card"
                style={{ textDecoration: 'none', color: 'inherit', padding: 16 }}
              >
                <div className="font-semibold" style={{ marginBottom: 6 }}>{p.name}</div>
                <div className="text-xs text-muted" style={{ marginBottom: 8 }}>{p.description || 'No description'}</div>
                <div className="flex gap-3 text-xs text-muted">
                  <span>📁 {p.upload_count} files</span>
                  <span>🎬 {p.job_count} jobs</span>
                  {p.active_jobs > 0 && <span className="badge badge-running">⚡ {p.active_jobs} active</span>}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
