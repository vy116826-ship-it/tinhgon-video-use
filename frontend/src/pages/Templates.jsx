import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Sparkles, Eye, Play, Star, Filter, Grid3x3, Rows3 } from 'lucide-react';
import api from '../utils/api';

const ASPECT_FILTERS = [
  { value: '', label: 'All' },
  { value: '16:9', label: '16:9 Landscape' },
  { value: '9:16', label: '9:16 Portrait' },
  { value: '1:1', label: '1:1 Square' },
];
const SORT_OPTIONS = [
  { value: 'popular', label: '🔥 Popular' },
  { value: 'newest', label: '🆕 Newest' },
  { value: 'name', label: '🔤 A-Z' },
];
const DIFF_COLORS = { easy: '#10b981', medium: '#f59e0b', advanced: '#ef4444' };

export default function Templates() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [activeCategory, setActiveCategory] = useState('');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('popular');
  const [aspect, setAspect] = useState('');
  const [gridView, setGridView] = useState(true);
  const [previewTemplate, setPreviewTemplate] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => { loadCategories(); }, []);
  useEffect(() => { if (ready) loadTemplates(); }, [activeCategory, sort, aspect, ready]);

  const loadCategories = async () => {
    try {
      const res = await api.get('/api/templates/categories');
      setCategories(res.data);
      if (res.data.length === 0) {
        await seedTemplates();
        return; // seedTemplates will re-call loadCategories
      }
      setReady(true);
    } catch { setReady(true); }
  };

  const seedTemplates = async () => {
    setSeeding(true);
    try {
      await api.post('/api/templates/seed');
      await loadCategories();
    } catch { /* ignore */ }
    setSeeding(false);
  };

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (activeCategory) params.set('category', activeCategory);
      if (sort) params.set('sort', sort);
      if (aspect) params.set('aspect', aspect);
      if (search) params.set('search', search);
      const res = await api.get(`/api/templates?${params}`);
      setTemplates(res.data);
    } catch { setTemplates([]); }
    setLoading(false);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    loadTemplates();
  };

  const useTemplate = async (tpl) => {
    try {
      await api.post(`/api/templates/${tpl.id}/use`);
      // Store config in session and navigate to projects
      sessionStorage.setItem('template_config', JSON.stringify(tpl.config));
      sessionStorage.setItem('template_name', tpl.name);
      navigate('/projects?from_template=1');
    } catch { alert('Failed to apply template'); }
  };

  const featured = templates.filter(t => t.is_featured);

  return (
    <div>
      <div className="page-header">
        <h1>🎬 Template Library</h1>
        <p>Browse pre-built editing presets — choose a style and start editing instantly</p>
      </div>

      {/* Search + Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap', alignItems: 'center' }}>
        <form onSubmit={handleSearch} style={{ flex: 1, minWidth: 200, position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input className="form-input" placeholder="Search templates..." value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ paddingLeft: 36 }} />
        </form>
        <select className="form-select" value={sort} onChange={e => setSort(e.target.value)} style={{ width: 160 }}>
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select className="form-select" value={aspect} onChange={e => setAspect(e.target.value)} style={{ width: 160 }}>
          {ASPECT_FILTERS.map(o => <option key={o.value} value={o.value}>{o.label || 'All Ratios'}</option>)}
        </select>
        <button className={`btn btn-icon ${gridView ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setGridView(true)}><Grid3x3 size={16}/></button>
        <button className={`btn btn-icon ${!gridView ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setGridView(false)}><Rows3 size={16}/></button>
      </div>

      {/* Categories */}
      <div className="category-pills">
        <button className={`pill ${!activeCategory ? 'active' : ''}`} onClick={() => setActiveCategory('')}>
          ✨ All
        </button>
        {categories.map(c => (
          <button key={c.slug} className={`pill ${activeCategory === c.slug ? 'active' : ''}`}
            onClick={() => setActiveCategory(activeCategory === c.slug ? '' : c.slug)}>
            {c.icon} {c.name.replace(/^[^\s]+\s/, '')}
            <span className="pill-count">{c.template_count}</span>
          </button>
        ))}
      </div>

      {/* Featured Banner */}
      {!activeCategory && featured.length > 0 && (
        <div className="featured-section">
          <h3 className="section-title"><Sparkles size={18} /> Featured Templates</h3>
          <div className="featured-grid">
            {featured.slice(0, 4).map(tpl => (
              <div key={tpl.id} className="featured-card" onClick={() => setPreviewTemplate(tpl)}>
                <div className="featured-img">
                  <img src={tpl.thumbnail_url} alt={tpl.name} loading="lazy" />
                  <div className="featured-overlay">
                    <Star size={14} style={{ color: '#fbbf24' }} />
                    <span>Featured</span>
                  </div>
                  <div className="featured-badge">{tpl.category_name}</div>
                </div>
                <div className="featured-info">
                  <h4>{tpl.name}</h4>
                  <p>{tpl.description}</p>
                  <div className="tpl-meta">
                    <span>👁 {tpl.use_count.toLocaleString()}</span>
                    <span className="tpl-diff" style={{ color: DIFF_COLORS[tpl.difficulty] }}>{tpl.difficulty}</span>
                    <span>{tpl.aspect_ratio}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Template Grid */}
      {loading ? (
        <div className="text-center text-muted mt-6">Loading templates...</div>
      ) : templates.length === 0 ? (
        <div className="card"><div className="empty-state">
          <div className="empty-state-icon">🎬</div>
          <h3>No templates found</h3>
          <p>Try a different search or category</p>
        </div></div>
      ) : (
        <div className={gridView ? 'tpl-grid' : 'tpl-list'}>
          {templates.map(tpl => (
            <div key={tpl.id} className={gridView ? 'tpl-card' : 'tpl-row'} onClick={() => setPreviewTemplate(tpl)}>
              <div className="tpl-thumb">
                <img src={tpl.thumbnail_url} alt={tpl.name} loading="lazy" />
                <div className="tpl-play"><Play size={20} /></div>
                {tpl.is_featured && <div className="tpl-star"><Star size={12} /></div>}
                {tpl.duration_hint && <div className="tpl-duration">{tpl.duration_hint}</div>}
              </div>
              <div className="tpl-body">
                <h4 className="tpl-name">{tpl.name}</h4>
                <p className="tpl-desc">{tpl.description}</p>
                <div className="tpl-tags">
                  {(tpl.tags || []).slice(0, 3).map(tag => (
                    <span key={tag} className="tpl-tag">#{tag}</span>
                  ))}
                </div>
                <div className="tpl-meta">
                  <span>👁 {tpl.use_count.toLocaleString()}</span>
                  <span className="tpl-diff" style={{ color: DIFF_COLORS[tpl.difficulty] }}>● {tpl.difficulty}</span>
                  <span>{tpl.aspect_ratio}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {previewTemplate && (
        <div className="modal-overlay" onClick={() => setPreviewTemplate(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 560 }}>
            <div className="modal-header">
              <h2>{previewTemplate.name}</h2>
              <button className="modal-close" onClick={() => setPreviewTemplate(null)}>✕</button>
            </div>
            <div className="tpl-preview-img">
              <img src={previewTemplate.thumbnail_url} alt={previewTemplate.name} style={{ width: '100%', borderRadius: 'var(--radius-md)', marginBottom: 16 }} />
            </div>
            <p className="text-sm" style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>{previewTemplate.description}</p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', fontSize: '0.85rem', marginBottom: 20 }}>
              <span className="text-muted">Category:</span><span>{previewTemplate.category_name}</span>
              <span className="text-muted">Difficulty:</span>
              <span style={{ color: DIFF_COLORS[previewTemplate.difficulty] }}>● {previewTemplate.difficulty}</span>
              <span className="text-muted">Aspect Ratio:</span><span>{previewTemplate.aspect_ratio}</span>
              <span className="text-muted">Duration:</span><span>{previewTemplate.duration_hint || 'Any'}</span>
              <span className="text-muted">Used:</span><span>{previewTemplate.use_count.toLocaleString()} times</span>
            </div>

            <h4 style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>Edit Settings</h4>
            <div style={{ background: 'var(--bg-glass)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', padding: 12, fontSize: '0.8rem', marginBottom: 20 }}>
              {Object.entries(previewTemplate.config || {}).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                  <span className="text-muted">{k.replace(/_/g, ' ')}</span>
                  <span>{String(v)}</span>
                </div>
              ))}
            </div>

            <div className="tpl-tags mb-4">
              {(previewTemplate.tags || []).map(tag => (
                <span key={tag} className="tpl-tag">#{tag}</span>
              ))}
            </div>

            <button className="btn btn-primary btn-lg w-full" onClick={() => { useTemplate(previewTemplate); setPreviewTemplate(null); }}>
              <Play size={18} /> Use This Template
            </button>
          </div>
        </div>
      )}

      <style>{`
        .category-pills { display: flex; gap: 8px; margin-bottom: 24px; overflow-x: auto; padding-bottom: 4px; }
        .pill { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 20px; border: 1px solid var(--border-primary); background: var(--bg-glass); color: var(--text-secondary); font-size: 0.8rem; font-weight: 500; cursor: pointer; transition: all var(--transition-fast); white-space: nowrap; font-family: inherit; }
        .pill:hover { border-color: var(--border-hover); background: var(--bg-input); color: var(--text-primary); }
        .pill.active { background: var(--gradient-subtle); border-color: var(--border-accent); color: var(--text-accent); }
        .pill-count { background: rgba(255,255,255,0.08); padding: 1px 6px; border-radius: 10px; font-size: 0.7rem; }

        .section-title { font-size: 1rem; font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }

        .featured-section { margin-bottom: 32px; }
        .featured-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
        .featured-card { background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: var(--radius-lg); overflow: hidden; cursor: pointer; transition: all var(--transition-base); }
        .featured-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-glow); border-color: var(--border-accent); }
        .featured-img { position: relative; height: 160px; overflow: hidden; }
        .featured-img img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s ease; }
        .featured-card:hover .featured-img img { transform: scale(1.08); }
        .featured-overlay { position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); padding: 4px 10px; border-radius: 12px; font-size: 0.7rem; display: flex; align-items: center; gap: 4px; color: #fbbf24; }
        .featured-badge { position: absolute; bottom: 8px; right: 8px; background: rgba(139,92,246,0.85); padding: 3px 10px; border-radius: 10px; font-size: 0.65rem; font-weight: 600; color: white; }
        .featured-info { padding: 14px; }
        .featured-info h4 { font-size: 0.95rem; font-weight: 700; margin-bottom: 4px; }
        .featured-info p { font-size: 0.78rem; color: var(--text-muted); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

        .tpl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
        .tpl-list { display: flex; flex-direction: column; gap: 8px; }

        .tpl-card { background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: var(--radius-md); overflow: hidden; cursor: pointer; transition: all var(--transition-base); }
        .tpl-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-glow); border-color: var(--border-hover); }

        .tpl-row { display: flex; gap: 16px; background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: var(--radius-sm); padding: 12px; cursor: pointer; transition: all var(--transition-fast); align-items: center; }
        .tpl-row:hover { background: var(--bg-card-hover); border-color: var(--border-hover); }
        .tpl-row .tpl-thumb { width: 120px; height: 80px; flex-shrink: 0; border-radius: var(--radius-sm); overflow: hidden; }

        .tpl-thumb { position: relative; height: 150px; overflow: hidden; }
        .tpl-thumb img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s ease; }
        .tpl-card:hover .tpl-thumb img, .tpl-row:hover .tpl-thumb img { transform: scale(1.06); }
        .tpl-play { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.3); opacity: 0; transition: opacity 0.2s ease; color: white; }
        .tpl-card:hover .tpl-play, .tpl-row:hover .tpl-play { opacity: 1; }
        .tpl-star { position: absolute; top: 6px; right: 6px; background: rgba(251,191,36,0.9); padding: 3px; border-radius: 50%; color: white; display: flex; }
        .tpl-duration { position: absolute; bottom: 6px; right: 6px; background: rgba(0,0,0,0.7); padding: 2px 8px; border-radius: 8px; font-size: 0.65rem; color: white; }

        .tpl-body { padding: 12px; }
        .tpl-name { font-size: 0.9rem; font-weight: 600; margin-bottom: 4px; line-height: 1.3; }
        .tpl-desc { font-size: 0.75rem; color: var(--text-muted); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 8px; }
        .tpl-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
        .tpl-tag { font-size: 0.65rem; padding: 2px 8px; border-radius: 10px; background: rgba(139,92,246,0.1); color: var(--text-accent); }
        .tpl-meta { display: flex; gap: 10px; font-size: 0.7rem; color: var(--text-muted); align-items: center; }
        .tpl-diff { font-weight: 600; }
      `}</style>
    </div>
  );
}
