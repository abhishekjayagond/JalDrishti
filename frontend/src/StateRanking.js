/**
 * StateRanking.js — JalDrishti Groundwater Intelligence & Forecasting
 * State & District Groundwater Resource Availability Index (RAI) Rankings
 * Design Direction A: Minimal Professional Dashboard
 */
import React, { useState, useEffect, useMemo } from 'react';
import './StateRanking.css';
import {
  IconDownload,
  IconArrowLeft,
  IconArrowRight,
  IconArrowUp,
  IconArrowDown,
  StatusSymbol
} from './icons';

const API_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API = `${API_BASE}/api`;

const STATUS_CONFIG = {
  safe:           { label: 'Safe',           dot: '#16a34a', bg: 'var(--status-safe-bg)', text: 'var(--status-safe-text)', border: 'var(--status-safe-border)', desc: '< 8m depth' },
  semi_critical:  { label: 'Semi-Critical',  dot: '#d97706', bg: 'var(--status-semi-bg)', text: 'var(--status-semi-text)', border: 'var(--status-semi-border)', desc: '8–15m depth' },
  critical:       { label: 'Critical',       dot: '#ea580c', bg: 'var(--status-crit-bg)', text: 'var(--status-crit-text)', border: 'var(--status-crit-border)', desc: '15–25m depth' },
  over_exploited: { label: 'Over-Exploited', dot: '#dc2626', bg: 'var(--status-over-bg)', text: 'var(--status-over-text)', border: 'var(--status-over-border)', desc: '> 25m depth' },
  no_data:        { label: 'Unavailable',    dot: '#64748b', bg: 'var(--status-unknown-bg)', text: 'var(--status-unknown-text)', border: 'var(--status-unknown-border)', desc: 'Baseline pending' },
};

export default function StateRanking({ onSelectStation }) {
  const [states, setStates]                   = useState([]);
  const [districts, setDistricts]             = useState([]);
  const [selectedState, setSelectedState]     = useState(null);
  const [loading, setLoading]                 = useState(true);
  const [loadingDistrict, setLoadingDistrict] = useState(false);
  const [view, setView]                       = useState('states'); // 'states' | 'districts'
  const [searchTerm, setSearchTerm]           = useState('');
  const [sortField, setSortField]             = useState('rai');
  const [sortAsc, setSortAsc]                 = useState(true); // default lowest RAI first (most stressed)
  const [currentPage, setCurrentPage]         = useState(1);
  const pageSize = 12;

  // Sidebar tab state: 'stressed' | 'sustainable' | 'norms'
  const [sidebarTab, setSidebarTab]           = useState('stressed');

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/ranking/states`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        setStates(d.states || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const selectState = async (state) => {
    setSelectedState(state);
    setView('districts');
    setLoadingDistrict(true);
    try {
      const r = await fetch(`${API}/ranking/districts/${encodeURIComponent(state.state)}`);
      const d = await r.json();
      setDistricts(d.districts || []);
    } catch {
      setDistricts([]);
    }
    setLoadingDistrict(false);
  };

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === 'state' || field === 'district');
    }
    setCurrentPage(1);
  };

  // Status counts across all states
  const statusCounts = useMemo(() => {
    return states.reduce((acc, s) => {
      acc[s.status] = (acc[s.status] || 0) + 1;
      return acc;
    }, {});
  }, [states]);

  // Filtered & sorted state list
  const sortedStates = useMemo(() => {
    let list = states.filter(s =>
      s.state.toLowerCase().includes(searchTerm.toLowerCase().trim())
    );

    list.sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      if (typeof aVal === 'string') {
        return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortAsc ? (aVal || 0) - (bVal || 0) : (bVal || 0) - (aVal || 0);
    });

    return list;
  }, [states, searchTerm, sortField, sortAsc]);

  // Pagination for states
  const totalPages = Math.max(1, Math.ceil(sortedStates.length / pageSize));
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedStates.slice(start, start + pageSize);
  }, [sortedStates, currentPage, pageSize]);

  const avgRAI = useMemo(() => {
    if (!states.length) return 0;
    return Math.round(states.reduce((acc, s) => acc + (s.rai || 0), 0) / states.length);
  }, [states]);

  const criticalCount = useMemo(() => {
    return states.filter(s => s.status === 'critical' || s.status === 'over_exploited').length;
  }, [states]);

  const worstStates = useMemo(() => {
    return [...states].sort((a, b) => (a.rai || 0) - (b.rai || 0)).slice(0, 5);
  }, [states]);

  const bestStates = useMemo(() => {
    return [...states].sort((a, b) => (b.rai || 0) - (a.rai || 0)).slice(0, 5);
  }, [states]);

  return (
    <div className="ranking-workspace">
      {/* ── Section Header ── */}
      <div className="section-header-row">
        <div>
          <div className="eyebrow-tag">National Aquifer Resource Accounting</div>
          <h1 className="page-title">State &amp; District Groundwater Rankings</h1>
          <p className="page-desc">
            Jurisdictional classification evaluating Resource Availability Index (RAI: 0–100 scale),
            well density, and static depth to water table against Central Ground Water Board (CGWB) norms.
          </p>
        </div>
        <div className="header-action-group">
          <a href={`${API}/export/summary/csv`} className="btn btn-secondary btn-sm" download>
            <IconDownload size={13} style={{ marginRight: '6px' }} /> Export National Summary CSV
          </a>
        </div>
      </div>

      {/* ── Top Summary KPIs (4 Cards Maximum Above the Fold) ── */}
      <div className="ranking-kpis-grid">
        <div className="kpi-metric-card">
          <div className="km-header">
            <span className="km-label">Monitored States &amp; UTs</span>
            <span className="km-icon">
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 1L2 5v1h12V5L8 1z"/><line x1="3" y1="7" x2="3" y2="13"/><line x1="6" y1="7" x2="6" y2="13"/><line x1="10" y1="7" x2="10" y2="13"/><line x1="13" y1="7" x2="13" y2="13"/><line x1="1" y1="13" x2="15" y2="13"/></svg>
            </span>
          </div>
          <div className="km-value tabular-nums">{states.length}</div>
          <div className="km-sub">Jurisdictions indexed in registry</div>
        </div>

        <div className="kpi-metric-card">
          <div className="km-header">
            <span className="km-label">National Mean RAI Score</span>
            <span className="km-icon">
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="2" y="9" width="3" height="6"/><rect x="6.5" y="5" width="3" height="10"/><rect x="11" y="1" width="3" height="14"/></svg>
            </span>
          </div>
          <div className={`km-value tabular-nums ${avgRAI > 60 ? 'text-positive' : avgRAI > 40 ? 'text-warning' : 'text-danger'}`}>
            {avgRAI}<span className="km-unit">/100</span>
          </div>
          <div className="km-sub">Resource Availability Index baseline</div>
        </div>

        <div className="kpi-metric-card">
          <div className="km-header">
            <span className="km-label">Stressed Jurisdictions</span>
            <span className="km-icon">
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 1L1 13h14L8 1z"/><path d="M8 6v3M8 11v.5" strokeWidth="1.6"/></svg>
            </span>
          </div>
          <div className={`km-value tabular-nums ${criticalCount > 0 ? 'text-danger' : 'text-positive'}`}>
            {criticalCount}
          </div>
          <div className="km-sub">Critical or Over-Exploited status</div>
        </div>

        <div className="kpi-metric-card">
          <div className="km-header">
            <span className="km-label">Safe Category States</span>
            <span className="km-icon">
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><polyline points="5,8 7.5,10.5 11,5.5"/></svg>
            </span>
          </div>
          <div className="km-value tabular-nums text-positive">
            {statusCounts.safe || 0}
          </div>
          <div className="km-sub">Average water table depth &lt; 8m bgl</div>
        </div>
      </div>

      {/* ── Status Distribution Strip ── */}
      <div className="status-distribution-card">
        <div className="sd-header">
          <span className="sd-title">National Jurisdictional Status Distribution</span>
          <span className="sd-total">{states.length} total administrative units</span>
        </div>
        <div className="sd-bar-track">
          {Object.entries(STATUS_CONFIG).filter(([k]) => k !== 'no_data').map(([k, cfg]) => {
            const count = statusCounts[k] || 0;
            const pct = states.length ? (count / states.length) * 100 : 0;
            if (pct === 0) return null;
            return (
              <div
                key={k}
                className="sd-bar-segment"
                style={{ width: `${pct}%`, backgroundColor: cfg.dot }}
                title={`${cfg.label}: ${count} states (${pct.toFixed(1)}%)`}
              />
            );
          })}
        </div>
        <div className="sd-legend-row">
          {Object.entries(STATUS_CONFIG).filter(([k]) => k !== 'no_data').map(([k, cfg]) => (
            <div key={k} className="sd-legend-item">
              <span className="sd-legend-dot" style={{ backgroundColor: cfg.dot }} />
              <span className="sd-legend-label">{cfg.label}:</span>
              <strong className="sd-legend-val tabular-nums">{statusCounts[k] || 0}</strong>
              <span className="sd-legend-crit">({cfg.desc})</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Main Layout: Table + Streamlined Sidebar ── */}
      <div className="ranking-layout-grid">
        {/* Left / Main Table Panel */}
        <div className="ranking-table-panel">
          <div className="rt-header">
            <div className="rt-title-group">
              {view === 'districts' ? (
                <>
                  <button className="btn btn-secondary btn-sm" onClick={() => setView('states')}>
                    <IconArrowLeft size={13} style={{ marginRight: '6px' }} /> Return to All States
                  </button>
                  <h3 className="rt-title">Districts in {selectedState?.state}</h3>
                </>
              ) : (
                <h3 className="rt-title">All States &amp; UTs — Ranked by Resource Availability</h3>
              )}
            </div>

            {view === 'states' && (
              <div className="rt-search-wrapper">
                <input
                  type="text"
                  className="form-input form-input-sm"
                  placeholder="Filter by state name..."
                  value={searchTerm}
                  onChange={e => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                />
              </div>
            )}
          </div>

          {loading ? (
            <div className="table-loading-row">
              <div className="spinner-ring" />
              <span>Querying state rankings from database engine...</span>
            </div>
          ) : view === 'states' ? (
            <>
              <div className="table-responsive">
                <table className="scientific-table ranking-table">
                  <thead>
                    <tr>
                      <th style={{ width: '45px' }}>Rank</th>
                      <th onClick={() => handleSort('state')} className="sortable-th">
                        State / UT {sortField === 'state' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
                      </th>
                      <th onClick={() => handleSort('total_stations')} className="sortable-th text-right">
                        Stations {sortField === 'total_stations' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
                      </th>
                      <th onClick={() => handleSort('avg_water_level_m')} className="sortable-th text-right">
                        Mean Depth (m bgl) {sortField === 'avg_water_level_m' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
                      </th>
                      <th className="text-right">Depth Range</th>
                      <th onClick={() => handleSort('rai')} className="sortable-th" style={{ width: '150px' }}>
                        RAI Score (0–100) {sortField === 'rai' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
                      </th>
                      <th>CGWB Status</th>
                      <th style={{ width: '90px' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((s, idx) => {
                      const st = STATUS_CONFIG[s.status] || STATUS_CONFIG.no_data;
                      const globalIdx = (currentPage - 1) * pageSize + idx + 1;
                      return (
                        <tr
                          key={s.state}
                          className={`clickable-row ${selectedState?.state === s.state ? 'selected-row' : ''}`}
                          onClick={() => selectState(s)}
                        >
                          <td className="tabular-nums font-mono text-muted">{globalIdx}</td>
                          <td>
                            <strong>{s.state}</strong>
                          </td>
                          <td className="tabular-nums font-mono text-right">{s.total_stations}</td>
                          <td className="tabular-nums font-mono text-right font-medium">
                            {s.avg_water_level_m != null ? `${s.avg_water_level_m.toFixed(2)} m` : '—'}
                          </td>
                          <td className="tabular-nums font-mono text-right text-muted" style={{ fontSize: '12px' }}>
                            {s.min_water_level_m != null && s.max_water_level_m != null
                              ? `${s.min_water_level_m} – ${s.max_water_level_m} m`
                              : '—'}
                          </td>
                          <td>
                            <div className="table-meter-cell">
                              <span className="tabular-nums font-mono font-medium">{s.rai}</span>
                              <div className="meter-track">
                                <div
                                  className="meter-fill"
                                  style={{ width: `${Math.min(100, Math.max(0, s.rai))}%`, backgroundColor: st.dot }}
                                />
                              </div>
                            </div>
                          </td>
                          <td>
                            <span
                              className="status-badge"
                              style={{ backgroundColor: st.bg, color: st.text, borderColor: st.border }}
                            >
                              <StatusSymbol status={s.status} size={11} fill={st.dot} style={{ marginRight: '6px' }} />
                              {st.label}
                            </span>
                          </td>
                          <td>
                            <button
                              className="btn btn-ghost btn-xs"
                              onClick={(e) => { e.stopPropagation(); selectState(s); }}
                            >
                              Districts <IconArrowRight size={12} style={{ marginLeft: '4px' }} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                    {sortedStates.length === 0 && (
                      <tr>
                        <td colSpan="8" className="empty-table-cell">No matching states found for "{searchTerm}".</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Table Pagination */}
              {totalPages > 1 && (
                <div className="table-pagination-bar">
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  >
                    <IconArrowLeft size={13} style={{ marginRight: '4px' }} /> Previous
                  </button>
                  <span className="font-mono" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Page {currentPage} of {totalPages} ({sortedStates.length} states)
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  >
                    Next <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
                  </button>
                </div>
              )}
            </>
          ) : loadingDistrict ? (
            <div className="table-loading-row">
              <div className="spinner-ring" />
              <span>Loading district telemetry for {selectedState?.state}...</span>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="scientific-table ranking-table">
                <thead>
                  <tr>
                    <th style={{ width: '45px' }}>Rank</th>
                    <th>District</th>
                    <th className="text-right">Monitored Stations</th>
                    <th className="text-right">Mean Depth (m bgl)</th>
                    <th style={{ width: '150px' }}>RAI Score</th>
                    <th>CGWB Category</th>
                  </tr>
                </thead>
                <tbody>
                  {districts.map((d, idx) => {
                    const st = STATUS_CONFIG[d.status] || STATUS_CONFIG.no_data;
                    return (
                      <tr key={d.district}>
                        <td className="tabular-nums font-mono text-muted">{idx + 1}</td>
                        <td><strong>{d.district}</strong></td>
                        <td className="tabular-nums font-mono text-right">{d.total_stations}</td>
                        <td className="tabular-nums font-mono text-right font-medium">
                          {d.avg_water_level_m != null ? `${d.avg_water_level_m.toFixed(2)} m` : '—'}
                        </td>
                        <td>
                          <div className="table-meter-cell">
                            <span className="tabular-nums font-mono font-medium">{d.rai}</span>
                            <div className="meter-track">
                              <div
                                className="meter-fill"
                                style={{ width: `${Math.min(100, Math.max(0, d.rai))}%`, backgroundColor: st.dot }}
                              />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span
                            className="status-badge"
                            style={{ backgroundColor: st.bg, color: st.text, borderColor: st.border }}
                          >
                            <StatusSymbol status={d.status} size={11} fill={st.dot} style={{ marginRight: '6px' }} />
                            {st.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                  {districts.length === 0 && (
                    <tr>
                      <td colSpan="6" className="empty-table-cell">No district telemetry records found for {selectedState?.state}.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: Streamlined Focus Sidebar (Tabbed to eliminate card clutter) */}
        <div className="ranking-sidebar">
          <div className="sidebar-tab-nav">
            <button
              className={`sidebar-tab-btn ${sidebarTab === 'stressed' ? 'active' : ''}`}
              onClick={() => setSidebarTab('stressed')}
            >
              Highest Stress
            </button>
            <button
              className={`sidebar-tab-btn ${sidebarTab === 'sustainable' ? 'active' : ''}`}
              onClick={() => setSidebarTab('sustainable')}
            >
              Sustainable Reserve
            </button>
            <button
              className={`sidebar-tab-btn ${sidebarTab === 'norms' ? 'active' : ''}`}
              onClick={() => setSidebarTab('norms')}
            >
              CGWB Norms
            </button>
          </div>

          {sidebarTab === 'stressed' && (
            <div className="sidebar-card">
              <h4 className="sc-heading text-danger">Highest Depletion Stress</h4>
              <p className="sc-sub">Lowest Resource Availability Index scores</p>
              <div className="stress-list">
                {worstStates.map((s, i) => (
                  <div key={s.state} className="stress-row" onClick={() => selectState(s)}>
                    <span className="stress-rank font-mono">{i + 1}</span>
                    <div className="stress-info">
                      <div className="stress-name">{s.state}</div>
                      <div className="stress-meta tabular-nums">{s.avg_water_level_m}m avg · {s.total_stations} stations</div>
                    </div>
                    <div className="stress-score font-mono text-danger font-medium">{s.rai}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {sidebarTab === 'sustainable' && (
            <div className="sidebar-card">
              <h4 className="sc-heading text-positive">Sustainable Aquifer Reserve</h4>
              <p className="sc-sub">Highest Resource Availability Index scores</p>
              <div className="stress-list">
                {bestStates.map((s, i) => (
                  <div key={s.state} className="stress-row" onClick={() => selectState(s)}>
                    <span className="stress-rank font-mono">{i + 1}</span>
                    <div className="stress-info">
                      <div className="stress-name">{s.state}</div>
                      <div className="stress-meta tabular-nums">{s.avg_water_level_m}m avg · {s.total_stations} stations</div>
                    </div>
                    <div className="stress-score font-mono text-positive font-medium">{s.rai}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {sidebarTab === 'norms' && (
            <div className="sidebar-card reference">
              <h4 className="sc-heading">CGWB Classification Criteria</h4>
              <p className="sc-sub">Standard static water table depth thresholds</p>
              <div className="cgwb-ref-list">
                {Object.entries(STATUS_CONFIG).filter(([k]) => k !== 'no_data').map(([k, cfg]) => (
                  <div key={k} className="cgwb-ref-item">
                    <span className="cgwb-dot" style={{ backgroundColor: cfg.dot }} />
                    <div className="cgwb-desc-group">
                      <div className="cgwb-name">{cfg.label}</div>
                      <div className="cgwb-threshold font-mono">{cfg.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
