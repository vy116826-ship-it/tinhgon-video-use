import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, FolderOpen, Trash2, X } from 'lucide-react';
import api from '../utils/api';

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { loadProjects(); }, []);

  const loadProjects = async () => {
    try {
      const res = await api.get('/api/projects');
      setProjects(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const createProject = async (e) => {
    e.preventDefault();
    try {
      const res = await api.post('/api/projects', { name, description: desc });
      setShowModal(false);
      setName('');
      setDesc('');
      navigate(`/projects/${res.data.id}`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create project');
    }
  };

  const deleteProject = async (id, e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Delete this project and all its files?')) return;
    try {
      await api.delete(`/api/projects/${id}`);
      setProjects(projects.filter(p => p.id !== id));
    } catch (err) {
      alert('Delete failed');
    }
  };

  return (
    <div>
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Projects</h1>
          <p>Manage your video editing projects</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={16} /> New Project
        </button>
      </div>

      {loading ? (
        <div className="text-center text-muted mt-6">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📁</div>
            <h3>No projects yet</h3>
            <p>Create a project to start uploading and editing videos</p>
            <button className="btn btn-primary" onClick={() => setShowModal(true)}>
              <Plus size={16} /> Create First Project
            </button>
          </div>
        </div>
      ) : (
        <div className="card-grid">
          {projects.map(p => (
            <Link to={`/projects/${p.id}`} key={p.id} className="card" style={{ textDecoration: 'none', color: 'inherit' }}>
              <div className="flex justify-between items-center" style={{ marginBottom: 12 }}>
                <div className="flex items-center gap-3">
                  <div style={{
                    width: 36, height: 36, borderRadius: 10,
                    background: 'var(--gradient-subtle)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <FolderOpen size={18} style={{ color: 'var(--text-accent)' }} />
                  </div>
                  <div>
                    <div className="font-semibold">{p.name}</div>
                  </div>
                </div>
                <button
                  className="btn btn-icon"
                  onClick={(e) => deleteProject(p.id, e)}
                  style={{ color: 'var(--text-muted)' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="text-sm text-muted" style={{ marginBottom: 12 }}>
                {p.description || 'No description'}
              </div>
              <div className="flex gap-3 text-xs text-muted">
                <span>📁 {p.upload_count} videos</span>
                <span>🎬 {p.job_count} jobs</span>
                {p.active_jobs > 0 && <span className="badge badge-running">⚡ {p.active_jobs} active</span>}
              </div>
              <div className="text-xs text-muted mt-2">
                Created {new Date(p.created_at).toLocaleDateString()}
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>New Project</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={createProject}>
              <div className="form-group">
                <label className="form-label">Project Name</label>
                <input type="text" className="form-input" placeholder="e.g. Product Launch Video"
                  value={name} onChange={e => setName(e.target.value)} required autoFocus />
              </div>
              <div className="form-group">
                <label className="form-label">Description (optional)</label>
                <textarea className="form-textarea" placeholder="Brief description of the project"
                  value={desc} onChange={e => setDesc(e.target.value)} />
              </div>
              <div className="flex gap-3" style={{ justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Create Project</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
