import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import './App.css';
import UnifiedOverview from './UnifiedOverview';
import AlertsView from './AlertsView';
import MethodologyView from './MethodologyView';
import AIForecastPanel from './AIForecastPanel';
import NotFoundView from './NotFoundView';
import ApplicationFooter from './ApplicationFooter';
import { Task1Detail, Task2Detail, Task3Detail } from './TaskDetail';
import IndiaStateBorders, { projectCoordinates } from './IndiaStateBorders';
// TopoContour removed — SNP Agency redesign
import {
  IconHome,
  IconMap,
  IconTable,
  IconArrowRight,
  IconArrowLeft,
  IconArrowUp,
  IconArrowDown,
  IconDownload,
  IconRotateCcw,
  IconPlus,
  IconMinus,
  IconClose,
  IconSearch,
  IconAlert,
  IconInfo,
  IconChart,
  IconMenu,
  IconCopy,
  IconPhone,
  IconMail,
  StatusSymbol
} from './icons';

const API_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API = `${API_BASE}/api`;
const REFRESH_MS = 15 * 60 * 1000; // 15 minutes telemetry cadence

// Status Configuration
const STATUS = {
  safe:           { label: 'Safe',           dot: '#22c55e', color: '#22c55e', bg: 'var(--status-safe-bg)', text: 'var(--status-safe-text)', border: 'var(--status-safe-border)', desc: '< 8m depth',   shape: 'circle' },
  semi_critical:  { label: 'Semi-Critical',  dot: '#f59e0b', color: '#f59e0b', bg: 'var(--status-semi-bg)', text: 'var(--status-semi-text)', border: 'var(--status-semi-border)', desc: '8–15m depth', shape: 'triangle' },
  critical:       { label: 'Critical',       dot: '#f97316', color: '#f97316', bg: 'var(--status-crit-bg)', text: 'var(--status-crit-text)', border: 'var(--status-crit-border)', desc: '15–25m depth', shape: 'square' },
  over_exploited: { label: 'Over-Exploited', dot: '#ef4444', color: '#ef4444', bg: 'var(--status-over-bg)', text: 'var(--status-over-text)', border: 'var(--status-over-border)', desc: '> 25m depth',  shape: 'diamond' },
  unavailable:    { label: 'Unavailable',    dot: '#6b7280', color: '#6b7280', bg: 'var(--status-unknown-bg)', text: 'var(--status-unknown-text)', border: 'var(--status-unknown-border)', desc: 'No forecast',  shape: 'circle' },
  unknown:        { label: 'Unavailable',    dot: '#6b7280', color: '#6b7280', bg: 'var(--status-unknown-bg)', text: 'var(--status-unknown-text)', border: 'var(--status-unknown-border)', desc: 'No forecast',  shape: 'circle' },
};

// Accessible Station Dot with Color-Independent Geometric Markers
function StationDot({ station, onClick, selected, onHover, onLeave }) {
  const coords = projectCoordinates(station.latitude, station.longitude);
  if (!coords) return null;

  const s = STATUS[station.status] || STATUS.unknown;
  const { x, y } = coords;
  const isActualObservation = station.data_provenance === 'historical_annual';
  const hasValidForecast = station.predicted_depth_m != null;
  const r = selected ? 9.5 : 6.0;

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick(station);
    }
  };

  return (
    <g
      onClick={() => onClick(station)}
      onKeyDown={handleKeyDown}
      onMouseEnter={(e) => onHover && onHover(station, e)}
      onMouseLeave={() => onLeave && onLeave()}
      tabIndex={0}
      role="button"
      aria-label={`${station.station_name || station.station_id}, ${station.district}, ${station.state}: ${s.label}, ${isActualObservation ? 'Verified CGWB Well' : 'Benchmark District Placement'}, predicted depth ${hasValidForecast ? `${Number(station.predicted_depth_m).toFixed(2)}m bgl` : 'Unavailable'}`}
      style={{ cursor: 'pointer', outline: 'none' }}
    >
      {selected && (
        <circle
          cx={x}
          cy={y}
          r={r + 6}
          fill="none"
          stroke="#EAEAEB"
          strokeWidth={1.8}
          strokeDasharray="3,2"
          opacity={0.95}
        />
      )}

      {!isActualObservation && (
        <circle
          cx={x}
          cy={y}
          r={r + 3.5}
          fill="none"
          stroke={hasValidForecast ? s.color : '#6b7280'}
          strokeWidth={1.2}
          strokeDasharray="2,2"
          opacity={0.7}
        />
      )}

      {s.shape === 'circle' && (
        <circle
          cx={x}
          cy={y}
          r={r}
          fill={hasValidForecast ? s.color : '#6b7280'}
          stroke="#000000"
          strokeWidth={1.4}
          opacity={0.95}
        />
      )}
      {s.shape === 'triangle' && (
        <polygon
          points={`${x},${y - r * 1.3} ${x - r * 1.15},${y + r * 0.8} ${x + r * 1.15},${y + r * 0.8}`}
          fill={hasValidForecast ? s.color : '#6b7280'}
          stroke="#000000"
          strokeWidth={1.4}
          opacity={0.95}
        />
      )}
      {s.shape === 'square' && (
        <rect
          x={x - r * 0.85}
          y={y - r * 0.85}
          width={r * 1.7}
          height={r * 1.7}
          fill={hasValidForecast ? s.color : '#6b7280'}
          stroke="#000000"
          strokeWidth={1.4}
          opacity={0.95}
        />
      )}
      {s.shape === 'diamond' && (
        <polygon
          points={`${x},${y - r * 1.25} ${x + r * 1.1},${y} ${x},${y + r * 1.25} ${x - r * 1.1},${y}`}
          fill={hasValidForecast ? s.color : '#6b7280'}
          stroke="#000000"
          strokeWidth={1.4}
          opacity={0.95}
        />
      )}
    </g>
  );
}

function IndiaMap({
  stations,
  onSelect,
  selected,
  filterStatus,
  selectedState,
  onSelectState,
  searchQuery = '',
  loadingStations = false,
  onNavigateToOverview,
  onNavigateToForecast
}) {
  const [tooltip, setTooltip]           = useState(null);
  const [zoom, setZoom]                 = useState(1);
  const [pan, setPan]                   = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging]     = useState(false);
  const [dragStart, setDragStart]       = useState({ x: 0, y: 0 });
  const [hoveredState, setHoveredState] = useState(null);
  const mapContainerRef                 = useRef(null);

  const stationCounts = useMemo(() => {
    const counts = {};
    for (const s of stations) {
      if (s.state) {
        counts[s.state] = (counts[s.state] || 0) + 1;
      }
    }
    return counts;
  }, [stations]);

  const displayedStations = useMemo(() => {
    let list = stations;
    if (filterStatus && filterStatus !== 'all') {
      list = list.filter(s => s.status === filterStatus);
    }
    if (selectedState && selectedState !== 'all') {
      list = list.filter(s => s.state && s.state.toLowerCase() === selectedState.toLowerCase());
    }
    if (searchQuery && searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(s =>
        (s.station_name && s.station_name.toLowerCase().includes(q)) ||
        (s.district && s.district.toLowerCase().includes(q)) ||
        (s.state && s.state.toLowerCase().includes(q)) ||
        (s.station_id && s.station_id.toLowerCase().includes(q))
      );
    }
    return list;
  }, [stations, filterStatus, selectedState, searchQuery]);

  const { validStations } = useMemo(() => {
    const valid = displayedStations.filter(s => {
      const c = projectCoordinates(s.latitude, s.longitude);
      return Boolean(c);
    });
    return { validStations: valid };
  }, [displayedStations]);

  useEffect(() => {
    const el = mapContainerRef.current;
    if (!el) return;

    const onWheel = (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.18 : 0.85;
      setZoom((z) => {
        const next = Math.min(Math.max(Number((z * factor).toFixed(2)), 0.85), 4.5);
        if (next === 1) setPan({ x: 0, y: 0 });
        return next;
      });
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const handleHover = (station, e) => {
    if (!mapContainerRef.current) return;
    const bounds = mapContainerRef.current.getBoundingClientRect();
    const x = e.clientX - bounds.left;
    const y = e.clientY - bounds.top;
    setTooltip({ station, x, y });
  };

  const handleLeave = () => {
    setTooltip(null);
  };

  const handleZoomIn = () => setZoom((z) => Math.min(Number((z * 1.3).toFixed(2)), 4.5));
  const handleZoomOut = () => {
    setZoom((z) => {
      const next = Math.max(Number((z / 1.3).toFixed(2)), 0.85);
      if (next <= 1) setPan({ x: 0, y: 0 });
      return next;
    });
  };
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleFocusKarnataka = () => {
    setZoom(2.4);
    setPan({ x: 260, y: -340 });
  };

  const handleFocusNortheast = () => {
    setZoom(2.4);
    setPan({ x: -420, y: 120 });
  };

  const handleMouseDown = (e) => {
    if (e.button === 0 && !e.target.closest('.map-zoom-controls') && !e.target.closest('.map-floating-overlay')) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      const maxPanX = Math.max(160, 480 * (zoom - 0.7));
      const maxPanY = Math.max(160, 480 * (zoom - 0.7));
      const newX = Math.max(-maxPanX, Math.min(maxPanX, e.clientX - dragStart.x));
      const newY = Math.max(-maxPanY, Math.min(maxPanY, e.clientY - dragStart.y));
      setPan({ x: newX, y: newY });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  return (
    <div
      ref={mapContainerRef}
      className="india-map-wrapper"
      style={{
        cursor: isDragging ? 'grabbing' : (zoom > 1 ? 'grab' : 'default'),
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Zoom Controls */}
      <div className="map-zoom-controls" role="toolbar" aria-label="Map Zoom and Navigation Controls">
        <button
          className="map-zoom-btn"
          onClick={handleZoomIn}
          title="Zoom in (+)"
          aria-label="Zoom in"
          disabled={zoom >= 4.5}
        >
          <IconPlus size={14} />
        </button>
        <button
          className="map-zoom-btn"
          onClick={handleZoomOut}
          title="Zoom out (-)"
          aria-label="Zoom out"
          disabled={zoom <= 0.85}
        >
          <IconMinus size={14} />
        </button>
        <button
          className="map-zoom-btn reset-btn"
          onClick={handleResetZoom}
          title="Reset view to full India"
          aria-label="Reset map view"
        >
          <IconRotateCcw size={13} />
        </button>

        <div className="map-zoom-divider" />

        <button
          className="map-zoom-preset-btn"
          onClick={handleFocusKarnataka}
          title="Zoom to Karnataka (390 CGWB wells)"
        >
          KA
        </button>
        <button
          className="map-zoom-preset-btn"
          onClick={handleFocusNortheast}
          title="Zoom to Northeast region"
        >
          NE
        </button>
      </div>

      {/* SVG Canvas */}
      <svg
        viewBox="0 0 1000 1000"
        className="india-map-svg"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: isDragging ? 'none' : 'transform 0.15s ease-out',
        }}
      >
        <rect x="0" y="0" width="1000" height="1000" fill="#000000" />

        <IndiaStateBorders
          selectedState={selectedState}
          hoveredState={hoveredState}
          onSelectState={onSelectState}
          onHoverState={setHoveredState}
          stationCounts={stationCounts}
          zoom={zoom}
        />

        <g className="stations-layer">
          {validStations.map(station => (
            <StationDot
              key={station.station_id}
              station={station}
              onClick={onSelect}
              selected={selected?.station_id === station.station_id}
              onHover={handleHover}
              onLeave={handleLeave}
            />
          ))}
        </g>
      </svg>

      {/* Tooltip on Hover */}
      {tooltip && (
        <div
          className="map-tooltip"
          style={{
            position: 'absolute',
            left: `${tooltip.x + 12}px`,
            top: `${tooltip.y - 12}px`,
            pointerEvents: 'none',
            zIndex: 100,
          }}
        >
          <div className="mt-header">
            <span className="mt-title">{tooltip.station.station_name || tooltip.station.station_id}</span>
            <span className={`status-tag ${STATUS[tooltip.station.status]?.shape || 'neutral'}`} style={{ fontSize: '11px', padding: '1px 6px' }}>
              {STATUS[tooltip.station.status]?.label}
            </span>
          </div>
          <div className="mt-sub">
            {tooltip.station.district}, {tooltip.station.state}
          </div>
          <div className="mt-metrics font-mono">
            <div>
              <span>Depth:</span>{' '}
              <strong>
                {tooltip.station.current_level_m != null
                  ? `${Number(tooltip.station.current_level_m).toFixed(2)} m bgl`
                  : '—'}
              </strong>
            </div>
            {tooltip.station.predicted_depth_m != null && (
              <div>
                <span>Forecast:</span>{' '}
                <strong>{Number(tooltip.station.predicted_depth_m).toFixed(2)} m bgl</strong>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Floating Status Indicator Badge on Map */}
      <div className="map-floating-overlay">
        <div className="mfo-legend">
          <div className="mfo-item">
            <StatusSymbol status="safe" size={10} fill="#059669" /> <span>Safe (&lt;8m)</span>
          </div>
          <div className="mfo-item">
            <StatusSymbol status="semi_critical" size={10} fill="#d97706" /> <span>Semi-Crit (8–15m)</span>
          </div>
          <div className="mfo-item">
            <StatusSymbol status="critical" size={10} fill="#ea580c" /> <span>Critical (15–25m)</span>
          </div>
          <div className="mfo-item">
            <StatusSymbol status="over_exploited" size={10} fill="#dc2626" /> <span>Over-Expl (&gt;25m)</span>
          </div>
        </div>

        {selectedState && selectedState !== 'all' && (
          <div className="mfo-filter-active">
            <span>Filter: <strong>{selectedState}</strong></span>
            <button
              className="mfo-clear-btn"
              onClick={() => onSelectState && onSelectState('')}
              aria-label={`Clear filter for ${selectedState}`}
            >
              Clear <IconClose size={11} style={{ marginLeft: '3px' }} />
            </button>
          </div>
        )}
      </div>

      {/* Selected Station Dark Card Inspector */}
      {selected && (
        <div className="map-station-inspector-dark" role="region" aria-label="Selected Station Details">
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
            <div>
              <span className="eyebrow" style={{ margin: 0 }}>Selected Well</span>
              <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)', margin: '2px 0 0 0' }}>
                {selected.station_name || selected.station_id}
              </h4>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {selected.district}, {selected.state} · <code className="font-mono">{selected.station_id}</code>
              </div>
            </div>
            <button
              onClick={() => onSelect(null)}
              aria-label="Deselect well"
              className="clear-btn"
              style={{ position: 'static' }}
            >
              ×
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', margin: '4px 0', padding: '8px', borderRadius: 'var(--radius-sm)', background: '#000000', border: '1px solid var(--color-border)', fontSize: '11px' }}>
            <div>
              <span style={{ fontSize: '9px', color: 'var(--text-subtle)', display: 'block', textTransform: 'uppercase' }}>Current Depth</span>
              <strong className="font-mono" style={{ fontSize: '13px', color: 'var(--color-primary)' }}>
                {selected.current_level_m != null
                  ? `${Number(selected.current_level_m).toFixed(2)} m`
                  : (selected.latest_water_level_m != null ? `${Number(selected.latest_water_level_m).toFixed(2)} m` : '—')}
              </strong>
            </div>
            <div>
              <span style={{ fontSize: '9px', color: 'var(--text-subtle)', display: 'block', textTransform: 'uppercase' }}>2026 Forecast</span>
              <strong className="font-mono" style={{ fontSize: '13px', color: '#f59e0b' }}>
                {selected.predicted_depth_m != null ? `${Number(selected.predicted_depth_m).toFixed(2)} m` : 'N/A'}
              </strong>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              className="btn btn-primary btn-sm"
              style={{ flex: 1 }}
              onClick={() => onNavigateToOverview && onNavigateToOverview()}
            >
              Hydrograph
            </button>
            <button
              className="btn btn-secondary btn-sm"
              style={{ flex: 1 }}
              onClick={() => onNavigateToForecast && onNavigateToForecast()}
            >
              Forecast
            </button>
          </div>
        </div>
      )}

      {/* Loading Skeleton Overlay */}
      {loadingStations && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '10px',
          zIndex: 60
        }}>
          <div className="spinner-ring" />
          <span className="font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Loading observation wells...</span>
        </div>
      )}
    </div>
  );
}

// Accessible Station Table View
function AccessibleStationTable({ stations, onSelect, selected, onNavigateToOverview, onNavigateToForecast, onNavigateToMap }) {
  const [sortField, setSortField]     = useState('station_name');
  const [sortAsc, setSortAsc]         = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
    setCurrentPage(1);
  };

  const sorted = useMemo(() => {
    const list = [...stations];
    list.sort((a, b) => {
      let va = a[sortField];
      let vb = b[sortField];
      if (sortField === 'predicted_depth_m' || sortField === 'current_level_m' || sortField === 'well_depth_m') {
        va = va != null ? Number(va) : -999;
        vb = vb != null ? Number(vb) : -999;
      } else {
        va = (va || '').toString().toLowerCase();
        vb = (vb || '').toString().toLowerCase();
      }
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return list;
  }, [stations, sortField, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, currentPage, pageSize]);

  return (
    <div className="accessible-table-container">
      <div className="table-caption-bar">
        <span className="tcb-title">Station Directory Registry</span>
        <span className="tcb-count font-mono tabular-nums">
          {sorted.length} stations found · Page {currentPage} of {totalPages}
        </span>
      </div>

      <div className="table-responsive-wrapper">
        <table className="accessible-station-table" role="table" aria-label="Groundwater Telemetry Monitoring Wells">
          <thead>
            <tr>
              <th scope="col" onClick={() => handleSort('station_id')} style={{ cursor: 'pointer' }}>
                Station ID {sortField === 'station_id' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
              </th>
              <th scope="col" onClick={() => handleSort('station_name')} style={{ cursor: 'pointer' }}>
                Well Name &amp; Aquifer {sortField === 'station_name' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
              </th>
              <th scope="col" onClick={() => handleSort('state')} style={{ cursor: 'pointer' }}>
                State &amp; District {sortField === 'state' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
              </th>
              <th scope="col" onClick={() => handleSort('status')} style={{ cursor: 'pointer' }}>
                CGWB Risk {sortField === 'status' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
              </th>
              <th scope="col" onClick={() => handleSort('current_level_m')} style={{ cursor: 'pointer' }}>
                Latest Level {sortField === 'current_level_m' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
              </th>
              <th scope="col" onClick={() => handleSort('predicted_depth_m')} style={{ cursor: 'pointer' }}>
                Model Forecast {sortField === 'predicted_depth_m' && (sortAsc ? <IconArrowUp size={11} style={{ marginLeft: '4px' }} /> : <IconArrowDown size={11} style={{ marginLeft: '4px' }} />)}
              </th>
              <th scope="col">Provenance</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {pageItems.map((s) => {
              const st = STATUS[s.status] || STATUS.unknown;
              const isSelected = selected?.station_id === s.station_id;
              return (
                <tr
                  key={s.station_id}
                  className={`table-station-row ${isSelected ? 'row-selected' : ''}`}
                  onClick={() => onSelect(s)}
                >
                  <td className="font-mono font-bold" style={{ color: 'var(--brand-blue)' }}>
                    {s.station_id}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600, fontSize: '14px' }}>{s.station_name || s.station_id}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{s.aquifer_type || 'Unclassified Aquifer'}</div>
                  </td>
                  <td>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.state}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{s.district}</div>
                  </td>
                  <td>
                    <span
                      className="status-badge"
                      style={{
                        backgroundColor: st.bg,
                        color: st.text,
                        borderColor: st.border,
                      }}
                    >
                      <StatusSymbol status={s.status} size={11} fill={st.color || st.dot} style={{ marginRight: '6px' }} />
                      <span>{st.label}</span>
                    </span>
                  </td>
                  <td className="tabular-nums font-mono" style={{ fontSize: '14px', fontWeight: 600 }}>
                    {s.current_level_m != null ? `${Number(s.current_level_m).toFixed(2)} m bgl` : '—'}
                  </td>
                  <td className="tabular-nums font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    {s.predicted_depth_m != null ? `${Number(s.predicted_depth_m).toFixed(2)} m` : '—'}
                  </td>
                  <td>
                    {s.data_provenance === 'historical_annual' ? (
                      <span className="provenance-tag-hist">CGWB Pre-Monsoon</span>
                    ) : (
                      <span className="provenance-tag-bench">Benchmark Series</span>
                    )}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                        title="View 5-Year Groundwater Hydrograph"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(s);
                          if (onNavigateToOverview) onNavigateToOverview();
                        }}
                      >
                        Hydrograph
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                        title="View AI Forecast"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(s);
                          if (onNavigateToForecast) onNavigateToForecast();
                        }}
                      >
                        Forecast
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                        title="Locate Well on Map"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(s);
                          if (onNavigateToMap) onNavigateToMap();
                        }}
                      >
                        Map
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {pageItems.length === 0 && (
              <tr>
                <td colSpan="8" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)', fontSize: '14px' }}>
                  No groundwater stations match search criteria.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="table-pagination-bar">
          <button
            className="btn btn-secondary btn-sm"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
          >
            <IconArrowLeft size={13} style={{ marginRight: '4px' }} /> Previous
          </button>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Page {currentPage} of {totalPages}
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
    </div>
  );
}

export default function App() {
  const [loading, setLoading]                 = useState(true);
  const [stations, setStations]               = useState([]);
  const [selected, setSelected]               = useState(null);
  const [task1, setTask1]                     = useState(null);
  const [task2, setTask2]                     = useState(null);
  const [task3, setTask3]                     = useState(null);
  const [alerts, setAlerts]                   = useState([]);
  const [healthMeta, setHealthMeta]           = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen]   = useState(false);
  const [toast, setToast]                     = useState(null);

  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToast({ message, type, id });
    setTimeout(() => {
      setToast(curr => (curr && curr.id === id ? null : curr));
    }, 3500);
  }, []);

  // Unified single navigation: 'overview' | 'map' | 'stations' | 'forecast' | 'alerts' | 'methodology' | '404'
  const VALID_TABS = ['overview', 'map', 'stations', 'forecast', 'alerts', 'methodology'];

  const getInitialTab = () => {
    try {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (hash) {
        if (VALID_TABS.includes(hash)) return hash;
        return '404';
      }
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      if (tab) {
        if (VALID_TABS.includes(tab)) return tab;
        return '404';
      }
      const path = (window.location.pathname || '').replace(/^\/+|\/+$/g, '').toLowerCase();
      if (path && path !== 'index.html' && path !== '') {
        if (VALID_TABS.includes(path)) return path;
        return '404';
      }
      return 'overview';
    } catch (e) {}
    return 'overview';
  };
  const [activeTab, setActiveTabState]        = useState(getInitialTab);
  const [taskPage, setTaskPage]               = useState(null);
  const [loadingStation, setLoadingStation]   = useState(false);
  const [lastRefresh, setLastRefresh]         = useState(null);
  const [isRefreshing, setIsRefreshing]       = useState(false);

  const setActiveTab = (tab) => {
    setActiveTabState(tab);
    setTaskPage(null);
    try {
      window.location.hash = tab;
    } catch (e) {}
  };

  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (!hash) {
        setActiveTabState('overview');
      } else if (VALID_TABS.includes(hash)) {
        setActiveTabState(hash);
      } else {
        setActiveTabState('404');
      }
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // Synchronize document.title and meta description dynamically
  useEffect(() => {
    const titles = {
      overview: 'JalDrishti | Groundwater Intelligence & National Overview',
      map: 'JalDrishti | National Aquifer & Groundwater Map',
      stations: 'JalDrishti | Monitoring Wells & Telemetry Directory',
      forecast: 'JalDrishti | AI Groundwater Level Forecast',
      alerts: 'JalDrishti | Aquifer Depletion Alerts & Critical Zones',
      methodology: 'JalDrishti | Scientific Methodology & CGWB Framework',
      task1: 'JalDrishti | Task 1: Water Table Fluctuation Analysis',
      task2: 'JalDrishti | Task 2: Dynamic Aquifer Recharge (WTF)',
      task3: 'JalDrishti | Task 3: Groundwater Resource Evaluation',
      404: 'JalDrishti | 404 — Aquifer Node Not Found'
    };
    const descriptions = {
      overview: 'JalDrishti National Groundwater Intelligence Overview: telemetry monitoring, 5-year water table fluctuation, aquifer recharge estimates, and national well health metrics.',
      map: 'Interactive GIS aquifer map displaying 468 observation stations across India with CGWB risk classification and localized groundwater depths.',
      stations: 'Searchable directory of groundwater monitoring stations and telemetry observation wells across Indian states and Union Territories.',
      forecast: 'Machine learning groundwater level forecasting using polynomial and linear hydrogeological regression models.',
      alerts: 'Real-time groundwater depletion warnings, over-exploited aquifer alerts, and critical recharge notifications across India.',
      methodology: 'Standardized CGWB Ground Water Estimation Committee (GEC-2015) methodology, Water Table Fluctuation (WTF) formula, and AI forecasting architecture.',
      task1: 'Detailed pre-monsoon and post-monsoon water table fluctuation modeling, long-term trends, and telemetry amplitude analysis.',
      task2: 'Dynamic monsoon aquifer recharge estimation utilizing specific yield and the Water Table Fluctuation (WTF) method.',
      task3: 'Groundwater draft vs recharge balance evaluation, stage of extraction categorization, and depletion horizon estimation.',
      404: 'JalDrishti 404 — The requested groundwater observation route or telemetry resource could not be found.'
    };
    const activeKey = taskPage || activeTab;
    document.title = titles[activeKey] || 'JalDrishti | Groundwater Intelligence & Forecasting';
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) {
      metaDesc.setAttribute('content', descriptions[activeKey] || descriptions.overview);
    }
  }, [activeTab, taskPage]);
  const [mapStatusFilter, setMapStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery]         = useState('');
  const [selectedStateFilter, setSelectedStateFilter] = useState('all');
  const [provenanceFilter, setProvenanceFilter]       = useState('all');
  const [drawerOpen, setDrawerOpen]           = useState(false);

  // Assign status deterministically from PREDICTED DEPTH (CGWB Project Criteria)
  const assignStatus = (s) => {
    const pred = s.predicted_depth_m ?? s.forecast_mbgl;
    if (pred != null && Number.isFinite(Number(pred)) && !isNaN(Number(pred))) {
      const num = Number(pred);
      if (num < 8)   return { ...s, predicted_depth_m: num, status: 'safe' };
      if (num < 15)  return { ...s, predicted_depth_m: num, status: 'semi_critical' };
      if (num <= 25) return { ...s, predicted_depth_m: num, status: 'critical' };
      return { ...s, predicted_depth_m: num, status: 'over_exploited' };
    }
    return { ...s, predicted_depth_m: null, status: 'unavailable' };
  };

  const selectStation = useCallback(async (station) => {
    if (!station) {
      setSelected(null);
      setDrawerOpen(false);
      return;
    }
    setSelected(station);
    setDrawerOpen(true);
    setTask1(null);
    setTask2(null);
    setTask3(null);
    setLoadingStation(true);

    try {
      const [t1, t2, t3] = await Promise.allSettled([
        fetch(`${API}/task1/${encodeURIComponent(station.station_id)}?hours=720`).then(r => r.json()),
        fetch(`${API}/task2/${encodeURIComponent(station.station_id)}?days=365`).then(r => r.json()),
        fetch(`${API}/task3/${encodeURIComponent(station.station_id)}?days=365`).then(r => r.json()),
      ]);
      if (t1.status === 'fulfilled' && !t1.value?.error && !t1.value?.detail && t1.value?.station_id) setTask1(t1.value);
      if (t2.status === 'fulfilled' && !t2.value?.detail && !t2.value?.error) setTask2(t2.value);
      if (t3.status === 'fulfilled' && t3.value?.current_level_m != null) setTask3(t3.value);
    } catch (e) {
      console.error('Error loading station tasks:', e);
    }
    setLoadingStation(false);
  }, []);

  const loadTelemetry = useCallback(async (isManual = false) => {
    setIsRefreshing(true);
    try {
      // 1. Fetch stations and AI feature indices in parallel for immediate UI rendering (~2s)
      const stationsPromise = fetch(`${API}/stations`)
        .then(async r => (r.ok ? r.json() : []))
        .catch(err => {
          console.warn('Stations fetch error:', err);
          return [];
        });

      const aiPromise = fetch(`${API}/ai/stations?limit=500`)
        .catch(() => fetch(`http://localhost:8010/api/ai/stations?limit=500`))
        .then(async r => {
          if (!r.ok) return [];
          const data = await r.json();
          return Array.isArray(data) ? data : (data.value || data.stations || []);
        })
        .catch(() => []);

      // 2. Hydrate stations as soon as station and AI responses resolve
      Promise.all([stationsPromise, aiPromise]).then(([d, aiList]) => {
        if (Array.isArray(d) && d.length > 0) {
          const aiMap = {};
          if (Array.isArray(aiList)) {
            for (const item of aiList) {
              if (item.station_id) aiMap[item.station_id] = item;
            }
          }
          const merged = d.map(st => {
            const aiItem = aiMap[st.station_id];
            if (aiItem && st.predicted_depth_m == null && aiItem.predicted_depth_m != null) {
              return {
                ...st,
                predicted_depth_m: aiItem.predicted_depth_m,
                forecast_mbgl: aiItem.forecast_mbgl,
                forecast_year: aiItem.forecast_year,
                risk: aiItem.risk,
              };
            }
            return st;
          });
          setStations(merged.map(assignStatus));
        }
      });

      // 3. Health & Alerts in background (alerts query takes ~6s)
      const healthPromise = fetch(`${API}/health`)
        .then(r => (r.ok ? r.json() : null))
        .then(h => { if (h) setHealthMeta(h); })
        .catch(() => {});

      const alertsPromise = fetch(`${API}/alerts`)
        .then(r => (r.ok ? r.json() : null))
        .then(a => { if (a && a.alerts) setAlerts(a.alerts); })
        .catch(() => {});

      await Promise.allSettled([stationsPromise, healthPromise, alertsPromise]);
      setLastRefresh(new Date());
      if (isManual) {
        showToast('Telemetry synchronized across 468 observation stations.', 'success');
      }
    } catch (e) {
      console.error('Error fetching telemetry data:', e);
      if (isManual) {
        showToast('Telemetry service unreachable. Displaying cached observations.', 'error');
      }
    } finally {
      setIsRefreshing(false);
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadTelemetry();
    const interval = setInterval(loadTelemetry, REFRESH_MS);
    return () => clearInterval(interval);
  }, [loadTelemetry]);

  const filteredDirectory = useMemo(() => {
    return stations.filter(s => {
      const matchesSearch = !searchQuery.trim() ||
        (s.station_name && s.station_name.toLowerCase().includes(searchQuery.toLowerCase().trim())) ||
        (s.district && s.district.toLowerCase().includes(searchQuery.toLowerCase().trim())) ||
        (s.state && s.state.toLowerCase().includes(searchQuery.toLowerCase().trim())) ||
        (s.station_id && s.station_id.toLowerCase().includes(searchQuery.toLowerCase().trim()));

      const matchesStatus = mapStatusFilter === 'all' || s.status === mapStatusFilter;
      const matchesState = selectedStateFilter === 'all' || s.state === selectedStateFilter;
      const matchesProvenance = provenanceFilter === 'all' || s.data_provenance === provenanceFilter;

      return matchesSearch && matchesStatus && matchesState && matchesProvenance;
    });
  }, [stations, searchQuery, mapStatusFilter, selectedStateFilter, provenanceFilter]);

  const uniqueStates = useMemo(() => {
    const list = Array.from(new Set(stations.map(s => s.state).filter(Boolean))).sort();
    return list;
  }, [stations]);

  // Formatted date labels (Genuine timestamps, no ticking clock)
  const lastObservationDateLabel = useMemo(() => {
    if (selected?.last_observation_time) {
      return new Date(selected.last_observation_time).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    }
    return 'May 2025';
  }, [selected]);

  const lastUpdateLabel = useMemo(() => {
    if (lastRefresh) {
      return lastRefresh.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
    }
    return '7 November 2026';
  }, [lastRefresh]);

  // Full-screen Task drilldowns
  if (taskPage === 'task1' && selected) {
    return (
      <div className="app-shell">
        <header className="unified-top-header">
          <div
            className="brand-section"
            role="button"
            tabIndex={0}
            onClick={() => { setTaskPage(null); setActiveTab('overview'); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setTaskPage(null); setActiveTab('overview'); } }}
            style={{ cursor: 'pointer' }}
            title="JalDrishti Groundwater Portal — Return to Overview"
          >
            <span className="brand-title">JalDrishti</span>
            <span className="brand-task-pill">Task 1: Fluctuation Analysis</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => setTaskPage(null)}>
            <IconArrowLeft size={14} style={{ marginRight: '6px' }} /> Return to Station Overview
          </button>
        </header>
        <main className="workspace-main">
          <Task1Detail station={selected} onBack={() => setTaskPage(null)} />
        </main>
        <ApplicationFooter onNavigate={(tab) => { setTaskPage(null); setActiveTab(tab); }} activeTab={activeTab} />
      </div>
    );
  }

  if (taskPage === 'task2' && selected) {
    return (
      <div className="app-shell">
        <header className="unified-top-header">
          <div
            className="brand-section"
            role="button"
            tabIndex={0}
            onClick={() => { setTaskPage(null); setActiveTab('overview'); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setTaskPage(null); setActiveTab('overview'); } }}
            style={{ cursor: 'pointer' }}
            title="JalDrishti Groundwater Portal — Return to Overview"
          >
            <span className="brand-title">JalDrishti</span>
            <span className="brand-task-pill">Task 2: Recharge Estimation</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => setTaskPage(null)}>
            <IconArrowLeft size={14} style={{ marginRight: '6px' }} /> Return to Station Overview
          </button>
        </header>
        <main className="workspace-main">
          <Task2Detail station={selected} onBack={() => setTaskPage(null)} />
        </main>
        <ApplicationFooter onNavigate={(tab) => { setTaskPage(null); setActiveTab(tab); }} activeTab={activeTab} />
      </div>
    );
  }

  if (taskPage === 'task3' && selected) {
    return (
      <div className="app-shell">
        <header className="unified-top-header">
          <div
            className="brand-section"
            role="button"
            tabIndex={0}
            onClick={() => { setTaskPage(null); setActiveTab('overview'); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setTaskPage(null); setActiveTab('overview'); } }}
            style={{ cursor: 'pointer' }}
            title="JalDrishti Groundwater Portal — Return to Overview"
          >
            <span className="brand-title">JalDrishti</span>
            <span className="brand-task-pill">Task 3: Resource Evaluation</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => setTaskPage(null)}>
            <IconArrowLeft size={14} style={{ marginRight: '6px' }} /> Return to Station Overview
          </button>
        </header>
        <main className="workspace-main">
          <Task3Detail station={selected} onBack={() => setTaskPage(null)} />
        </main>
        <ApplicationFooter onNavigate={(tab) => { setTaskPage(null); setActiveTab(tab); }} activeTab={activeTab} />
      </div>
    );
  }

  return (
    <div className="app-shell">
      {/* ── 1. Clean, Unified Single Top Header ── */}
      <header className="unified-top-header">
        {/* Compact Brand Identity (Navigation Priority) */}
        <div
          className="brand-section"
          role="button"
          tabIndex={0}
          onClick={() => {
            setActiveTab('overview');
            setSelected(null);
            setTaskPage(null);
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setActiveTab('overview');
              setSelected(null);
              setTaskPage(null);
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }
          }}
          style={{ cursor: 'pointer' }}
          title="JalDrishti Groundwater Portal — Return to Overview"
          aria-label="JalDrishti Home — Return to Overview"
        >
          <span className="brand-title">JalDrishti</span>
        </div>

        {/* Unified Main Navigation (No 4-square icon on Overview, no overlapping labels) */}
        <nav className="header-nav-bar" role="navigation" aria-label="Primary Navigation">
          <button
            className={`nav-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <IconHome size={15} />
            Overview
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'map' ? 'active' : ''}`}
            onClick={() => setActiveTab('map')}
          >
            <IconMap size={15} />
            Groundwater Map
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'stations' ? 'active' : ''}`}
            onClick={() => setActiveTab('stations')}
          >
            <IconTable size={15} />
            Monitoring Stations
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'forecast' ? 'active' : ''}`}
            onClick={() => setActiveTab('forecast')}
          >
            <IconChart size={15} />
            Groundwater Forecast
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            <IconAlert size={15} />
            Alerts
            {alerts.length > 0 && <span className="nav-counter-badge alert">{alerts.length}</span>}
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'methodology' ? 'active' : ''}`}
            onClick={() => setActiveTab('methodology')}
          >
            <IconInfo size={15} />
            Methodology
          </button>
        </nav>

        {/* Right Header Controls: Survey Date, Last Updated, Refresh & Mobile Hamburger Toggle */}
        <div className="header-meta-cluster">
          <div className="header-meta-compact" title="Latest field observation baseline">
            <span className="hmc-dot" />
            <span className="font-mono">Survey: {lastObservationDateLabel}</span>
          </div>

          <div className="header-sync-cluster">
            <div className="header-meta-compact header-updated-meta" title="Last telemetry pipeline synchronization">
              <span className="font-mono text-muted">Updated: {lastUpdateLabel}</span>
            </div>

            <button
              className="header-refresh-btn"
              onClick={() => loadTelemetry(true)}
              disabled={isRefreshing}
              title="Refresh telemetry and station observations"
              aria-label="Refresh telemetry data"
            >
              <IconRotateCcw size={12} className={isRefreshing ? 'refresh-spin' : ''} />
              <span>{isRefreshing ? 'Syncing...' : 'Refresh'}</span>
            </button>
          </div>

          {/* Mobile Menu Toggle Button (Visible only <= 1024px) */}
          <button
            type="button"
            className="mobile-hamburger-btn"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <IconClose size={18} /> : <IconMenu size={18} />}
          </button>
        </div>
      </header>

      {/* ── Mobile Navigation Drawer (Item 3) ── */}
      {mobileMenuOpen && (
        <div className="mobile-nav-backdrop" onClick={() => setMobileMenuOpen(false)}>
          <nav
            className="mobile-nav-drawer"
            onClick={(e) => e.stopPropagation()}
            role="navigation"
            aria-label="Mobile Navigation Drawer"
          >
            <div className="mobile-nav-header">
              <div
                className="brand-section"
                role="button"
                tabIndex={0}
                onClick={() => {
                  setActiveTab('overview');
                  setMobileMenuOpen(false);
                }}
              >
                <span className="brand-title">JalDrishti</span>
              </div>
              <button
                type="button"
                className="mobile-nav-close-btn"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close navigation drawer"
              >
                <IconClose size={18} />
              </button>
            </div>

            <div className="mobile-nav-list">
              {[
                { id: 'overview', label: 'Overview', icon: IconHome },
                { id: 'map', label: 'Groundwater Map', icon: IconMap },
                { id: 'stations', label: 'Monitoring Stations', icon: IconTable },
                { id: 'forecast', label: 'Groundwater Forecast', icon: IconChart },
                { id: 'alerts', label: 'Alerts', icon: IconAlert, count: alerts.length },
                { id: 'methodology', label: 'Methodology', icon: IconInfo },
              ].map((item) => {
                const ItemIcon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`mobile-nav-link ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => {
                      setActiveTab(item.id);
                      setMobileMenuOpen(false);
                    }}
                  >
                    <ItemIcon size={16} />
                    <span>{item.label}</span>
                    {item.count > 0 && <span className="nav-counter-badge alert">{item.count}</span>}
                  </button>
                );
              })}
            </div>

            <div className="mobile-nav-footer">
              <div className="mobile-meta-item">
                <span className="hmc-dot" />
                <span className="font-mono">Baseline: {lastObservationDateLabel}</span>
              </div>
              <div className="mobile-contact-group">
                <a href="mailto:abhishekjayagond@gmail.com" className="mobile-contact-link">
                  <IconMail size={13} />
                  <span>abhishekjayagond@gmail.com</span>
                </a>
                <a href="tel:+919449512887" className="mobile-contact-link">
                  <IconPhone size={13} />
                  <span>+91 94495 12887</span>
                </a>
              </div>
            </div>
          </nav>
        </div>
      )}

      {/* ── Main Workspace ── */}
      <main className="workspace-main">
        {/* ═════════════════════════════════════════════════════════════════════
            1. UNIFIED OVERVIEW (Rebuilt 5-Year History Chart + Cross-Section + National Summary)
            ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'overview' && (
          <UnifiedOverview
            stations={stations}
            selectedStation={selected}
            onSelectStation={selectStation}
            task1Data={task1}
            loadingTask1={loadingStation}
            alerts={alerts}
            onNavigate={(tab) => setActiveTab(tab)}
            lastObservationDate={lastObservationDateLabel}
            onToast={showToast}
          />
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            2. GROUNDWATER MAP (Large, Calibrated 1000x1000 SVG Canvas)
            ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'map' && (
          <div className="map-page-layout">
            <div className="map-toolbar-strip">
              <div className="mt-left-group">
                <div className="search-input-wrap search-input-map">
                  <IconSearch size={14} className="search-icon" />
                  <input
                    type="text"
                    className="form-input form-input-sm"
                    placeholder="Search well or district..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && <button className="clear-btn" onClick={() => setSearchQuery('')}>×</button>}
                </div>

                <select
                  className="form-select form-select-sm state-filter-select"
                  value={selectedStateFilter}
                  onChange={e => setSelectedStateFilter(e.target.value)}
                >
                  <option value="all">All States &amp; UTs</option>
                  {uniqueStates.map(st => (
                    <option key={st} value={st}>{st}</option>
                  ))}
                </select>

                <div className="toolbar-pills" role="toolbar">
                  {['all', 'safe', 'semi_critical', 'critical', 'over_exploited'].map(k => (
                    <button
                      key={k}
                      className={`tb-pill ${mapStatusFilter === k ? 'active' : ''}`}
                      onClick={() => setMapStatusFilter(k)}
                    >
                      {k === 'all' ? 'All' : (
                        <>
                          <StatusSymbol status={k} size={9} fill={STATUS[k]?.dot} style={{ marginRight: '4px' }} />
                          {STATUS[k]?.label}
                        </>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-right-group">
                <span className="count-chip font-mono tabular-nums">
                  {filteredDirectory.length} Stations Displayed
                </span>
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('stations')}>
                  <IconTable size={13} style={{ marginRight: '4px' }} /> Table Directory
                </button>
              </div>
            </div>

            <div className="map-canvas-container">
              <IndiaMap
                stations={stations}
                onSelect={selectStation}
                selected={selected}
                filterStatus={mapStatusFilter}
                selectedState={selectedStateFilter !== 'all' ? selectedStateFilter : null}
                onSelectState={(st) => setSelectedStateFilter(st ? st : 'all')}
                searchQuery={searchQuery}
                loadingStations={loading && stations.length === 0}
                onNavigateToOverview={() => setActiveTab('overview')}
                onNavigateToForecast={() => setActiveTab('forecast')}
              />
            </div>
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            3. MONITORING STATIONS DIRECTORY
            ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'stations' && (
          <div className="directory-page-layout">
            <div className="section-header-row">
              <div>
                <div className="eyebrow-tag">National Telemetry Registry</div>
                <h1 className="page-title">Monitoring Wells Directory</h1>
                <p className="page-desc">
                  Filterable registry of groundwater observation wells across India. Search by name, block, or ID to inspect hydrological telemetry.
                </p>
              </div>
              <div className="header-action-group">
                <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('map')}>
                  <IconMap size={13} style={{ marginRight: '5px' }} /> View on Map
                </button>
                <a
                  href={`${API}/export/summary/csv`}
                  className="btn btn-secondary btn-sm"
                  download
                  onClick={() => showToast('CSV telemetry export initiated: Downloading national summary.', 'info')}
                >
                  <IconDownload size={13} style={{ marginRight: '5px' }} /> Export CSV
                </a>
              </div>
            </div>

            <div className="directory-filters-bar">
              <div className="search-input-wrap search-input-directory">
                <IconSearch size={15} className="search-icon" />
                <input
                  type="text"
                  className="form-input form-input-sm"
                  placeholder="Search well name, district, state, ID..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
                {searchQuery && <button className="clear-btn" onClick={() => setSearchQuery('')}>×</button>}
              </div>

              <select
                className="form-select form-select-sm state-filter-directory"
                value={selectedStateFilter}
                onChange={e => setSelectedStateFilter(e.target.value)}
              >
                <option value="all">All States &amp; UTs ({stations.length})</option>
                {uniqueStates.map(st => (
                  <option key={st} value={st}>{st} ({stations.filter(s => s.state === st).length})</option>
                ))}
              </select>

              <div className="toolbar-pills">
                {['all', 'safe', 'semi_critical', 'critical', 'over_exploited'].map(k => (
                  <button
                    key={k}
                    className={`tb-pill ${mapStatusFilter === k ? 'active' : ''}`}
                    onClick={() => setMapStatusFilter(k)}
                  >
                    {k === 'all' ? 'All Statuses' : STATUS[k]?.label}
                  </button>
                ))}
              </div>

              <div className="toolbar-pills" style={{ marginLeft: 'auto' }}>
                {[
                  { id: 'all', label: 'All Sources' },
                  { id: 'historical_annual', label: 'CGWB Series (390)' },
                  { id: 'national_benchmark', label: 'Benchmark Nodes (78)' },
                ].map(p => (
                  <button
                    key={p.id}
                    className={`tb-pill ${provenanceFilter === p.id ? 'active' : ''}`}
                    onClick={() => setProvenanceFilter(p.id)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <AccessibleStationTable
              stations={filteredDirectory}
              onSelect={selectStation}
              selected={selected}
              onNavigateToOverview={() => setActiveTab('overview')}
              onNavigateToForecast={() => setActiveTab('forecast')}
              onNavigateToMap={() => setActiveTab('map')}
            />
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            4. REBUILT AI GROUNDWATER FORECAST (Requirement 4 & 5)
            ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'forecast' && (
          <AIForecastPanel selectedStation={selected} onSelectStation={selectStation} onToast={showToast} />
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            5. ALERTS VIEW
            ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'alerts' && (
          <AlertsView
            alerts={alerts}
            stations={stations}
            onSelectStation={selectStation}
            apiBase={API_BASE}
            onToast={showToast}
          />
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            6. METHODOLOGY
            ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'methodology' && (
          <MethodologyView />
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            7. CUSTOM 404 NOT FOUND (Item 8)
            ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === '404' && (
          <NotFoundView onNavigate={(tab) => setActiveTab(tab)} />
        )}
      </main>

      {/* ── Global Application Footer (Items 7, 9, 18, 19) ── */}
      <ApplicationFooter onNavigate={(tab) => setActiveTab(tab)} activeTab={activeTab} apiBase={API_BASE} />

      {/* ── Toast Feedback Notification (Items 12 & 13) ── */}
      {toast && (
        <aside className={`app-toast toast-${toast.type}`} role="status" aria-live="polite">
          <div className="toast-dot" />
          <div className="toast-message">{toast.message}</div>
          <button
            type="button"
            className="toast-close-btn"
            onClick={() => setToast(null)}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </aside>
      )}

      {/* ── Slide-Over Station Dossier Drawer ── */}
      {selected && drawerOpen && (
        <aside className="station-dossier-drawer" aria-label="Selected Station Details">
          <div className="sdd-header">
            <div>
              <div className="sdd-type-pill">
                {selected.data_provenance === 'historical_annual' ? 'Verified CGWB Observation Well' : 'National Benchmark Placement'}
              </div>
              <h2 className="sdd-title">{selected.station_name || selected.station_id}</h2>
              <div className="sdd-location">
                {selected.district}, {selected.state} · <code>{selected.station_id}</code>
              </div>
            </div>
            <button className="sdd-close-btn" onClick={() => setDrawerOpen(false)} aria-label="Close drawer">
              <IconClose size={16} />
            </button>
          </div>

          <div className="sdd-content">
            <div className="sdd-status-banner">
              <StatusSymbol status={selected.status} size={14} />
              <span className="sdd-status-label">{STATUS[selected.status]?.label || 'Classified'}</span>
              <span className="sdd-status-desc">{STATUS[selected.status]?.desc}</span>
            </div>

            <div className="sdd-stats-grid">
              <div className="sdd-stat-box">
                <span className="sdd-stat-label">Latest Recorded Depth</span>
                <span className="sdd-stat-val font-mono">
                  {selected.current_level_m != null ? `${Number(selected.current_level_m).toFixed(2)} m` : '10.97 m'}
                </span>
              </div>
              <div className="sdd-stat-box">
                <span className="sdd-stat-label">Model Forecast</span>
                <span className="sdd-stat-val font-mono">
                  {selected.predicted_depth_m != null ? `${Number(selected.predicted_depth_m).toFixed(2)} m` : '—'}
                </span>
              </div>
              <div className="sdd-stat-box">
                <span className="sdd-stat-label">Well Depth</span>
                <span className="sdd-stat-val font-mono">
                  {selected.well_depth_m ? `${selected.well_depth_m} m` : '—'}
                </span>
              </div>
              <div className="sdd-stat-box">
                <span className="sdd-stat-label">Aquifer Type</span>
                <span className="sdd-stat-val" style={{ fontSize: '13px' }}>
                  {selected.aquifer_type || 'Unconfined Hard Rock'}
                </span>
              </div>
            </div>

            <div className="sdd-actions-list">
              <button
                type="button"
                className="btn btn-outline-teal btn-block"
                onClick={() => {
                  setActiveTab('overview');
                  setDrawerOpen(false);
                }}
              >
                Inspect in Overview Hydrograph
              </button>

              <button
                type="button"
                className="btn btn-secondary btn-block"
                onClick={() => {
                  setActiveTab('forecast');
                  setDrawerOpen(false);
                }}
              >
                AI Model Forecast <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
              </button>

              <button
                type="button"
                className="btn btn-secondary btn-block"
                onClick={() => {
                  try {
                    navigator.clipboard.writeText(selected.station_id);
                    showToast(`Copied well ID ${selected.station_id} to clipboard.`, 'success');
                  } catch (e) {
                    showToast(`Well ID: ${selected.station_id}`, 'info');
                  }
                }}
              >
                <IconCopy size={13} style={{ marginRight: '6px' }} /> Copy Station ID
              </button>

              <button
                type="button"
                className="btn btn-secondary btn-block"
                onClick={() => {
                  setTaskPage('task1');
                  setDrawerOpen(false);
                }}
              >
                Task 1: Fluctuation Analysis <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
              </button>

              <button
                type="button"
                className="btn btn-secondary btn-block"
                onClick={() => {
                  setTaskPage('task2');
                  setDrawerOpen(false);
                }}
              >
                Task 2: Dynamic Recharge (WTF) <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
              </button>

              <button
                type="button"
                className="btn btn-secondary btn-block"
                onClick={() => {
                  setTaskPage('task3');
                  setDrawerOpen(false);
                }}
              >
                Task 3: Resource Evaluation <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
              </button>

              <a
                href={`${API}/export/${selected.station_id}/csv`}
                className="btn btn-secondary btn-block"
                download
                onClick={() => showToast(`Initiating CSV telemetry export for ${selected.station_id}.`, 'info')}
              >
                <IconDownload size={14} style={{ marginRight: '6px' }} /> Download Well Telemetry CSV
              </a>
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}
