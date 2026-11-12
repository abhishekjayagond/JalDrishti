import React, { useState, useMemo } from 'react';
import GroundwaterHistoryChart from './GroundwaterHistoryChart';
import {
  IconSearch,
  IconMap,
  IconTable,
  IconChart,
  IconArrowRight,
  IconInfo,
  IconClose,
  StatusSymbol
} from './icons';

/**
 * National Aquifer Depth Distribution Chart (SNP Agency Stark Monochrome Design)
 * Renders the empirical distribution of observation wells across depth brackets:
 * Safe (<8m), Semi-Critical (8-15m), Critical (15-25m), Over-Exploited (>25m).
 */
function NationalAquiferDistributionChart({ stations = [], avgDepth = '10.42' }) {
  const [hoveredBracket, setHoveredBracket] = useState(null);

  const buckets = useMemo(() => {
    const list = [
      { id: 'safe', label: 'Safe (< 8m)', range: [0, 8], color: '#22c55e', count: 0, desc: 'Water table within 8m. Sustainable extraction envelope.' },
      { id: 'semi_critical', label: 'Semi-Critical (8–15m)', range: [8, 15], color: '#f59e0b', count: 0, desc: 'Water table 8–15m deep. Extraction nears annual recharge.' },
      { id: 'critical', label: 'Critical (15–25m)', range: [15, 25], color: '#f97316', count: 0, desc: 'Water table 15–25m deep. Multi-year replenishment deficit.' },
      { id: 'over_exploited', label: 'Over-Exploited (> 25m)', range: [25, 35], color: '#ef4444', count: 0, desc: 'Water table deeper than 25m. High risk of well desiccation.' },
    ];

    for (const s of stations) {
      const depth = Number(s.current_level_m ?? s.latest_water_level_m ?? s.predicted_depth_m ?? 10.97);
      if (depth < 8) list[0].count++;
      else if (depth < 15) list[1].count++;
      else if (depth <= 25) list[2].count++;
      else list[3].count++;
    }

    const total = stations.length || 1;
    return list.map(b => ({
      ...b,
      pct: Math.round((b.count / total) * 100),
    }));
  }, [stations]);

  const chartHeight = 200;
  const chartWidth = 560;
  const maxAxisDepth = 30; // 0m to 30m bgl

  const scaleY = (depth) => 24 + (Math.min(maxAxisDepth, Math.max(0, depth)) / maxAxisDepth) * (chartHeight - 48);

  return (
    <div className="national-distribution-chart-wrap">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <span className="eyebrow">Empirical Telemetry Distribution</span>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-primary)', letterSpacing: '0px' }}>
            National Aquifer Storage Categorization
          </h2>
        </div>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--color-surface)', padding: '4px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontSize: '12px' }}>
          <span style={{ color: 'var(--text-muted)' }}>Mean Depth:</span>
          <strong className="font-mono" style={{ color: 'var(--color-primary)' }}>{avgDepth} m bgl</strong>
        </div>
      </div>

      <div style={{ position: 'relative', width: '100%', height: `${chartHeight}px`, background: '#000000', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', padding: '6px', overflow: 'hidden' }}>
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
          {buckets.map(b => {
            const yStart = scaleY(b.range[0]);
            const yEnd = scaleY(Math.min(maxAxisDepth, b.range[1]));
            const bandHeight = yEnd - yStart;
            const isHovered = hoveredBracket === b.id;

            return (
              <g
                key={b.id}
                onMouseEnter={() => setHoveredBracket(b.id)}
                onMouseLeave={() => setHoveredBracket(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Zone Background Strip */}
                <rect
                  x="50"
                  y={yStart}
                  width={chartWidth - 60}
                  height={bandHeight}
                  fill={isHovered ? 'rgba(55, 65, 81, 0.25)' : 'transparent'}
                  stroke="var(--color-border)"
                  strokeWidth="0.5"
                  strokeDasharray="2 2"
                />

                {/* Y Axis Threshold Label */}
                <text x="42" y={yStart + 4} textAnchor="end" fontSize="10" fill="var(--text-subtle)" fontFamily="var(--font-mono)">
                  {b.range[0]}m
                </text>

                {/* Quantitative Bar */}
                <rect
                  x="56"
                  y={yStart + 4}
                  width={Math.max(8, ((chartWidth - 220) * b.pct) / 100)}
                  height={Math.max(6, bandHeight - 8)}
                  rx="2"
                  fill={b.color}
                  opacity={isHovered ? 1 : 0.85}
                />

                {/* Station Count */}
                <text
                  x={64 + Math.max(8, ((chartWidth - 220) * b.pct) / 100)}
                  y={yStart + bandHeight / 2 + 3}
                  fontSize="11"
                  fontWeight="600"
                  fill="var(--color-primary)"
                  fontFamily="var(--font-mono)"
                >
                  {b.count} wells ({b.pct}%)
                </text>

                {/* Zone Label */}
                <text
                  x={chartWidth - 16}
                  y={yStart + bandHeight / 2 + 3}
                  textAnchor="end"
                  fontSize="11"
                  fontWeight="500"
                  fill="var(--text-muted)"
                >
                  {b.label}
                </text>
              </g>
            );
          })}

          {/* National Mean Depth Reference Marker */}
          {(() => {
            const meanY = scaleY(parseFloat(avgDepth) || 10.42);
            return (
              <g>
                <line
                  x1="45"
                  y1={meanY}
                  x2={chartWidth - 10}
                  y2={meanY}
                  stroke="var(--color-primary)"
                  strokeWidth="1"
                  strokeDasharray="4 2"
                  opacity="0.8"
                />
                <rect
                  x="52"
                  y={meanY - 8}
                  width="116"
                  height="16"
                  rx="2"
                  fill="#000000"
                  stroke="var(--color-border)"
                  strokeWidth="1"
                />
                <text
                  x="58"
                  y={meanY + 3}
                  fontSize="9.5"
                  fontWeight="500"
                  fill="var(--color-primary)"
                  fontFamily="var(--font-mono)"
                >
                  Mean: {avgDepth}m bgl
                </text>
              </g>
            );
          })()}
        </svg>
      </div>

      {/* Bracket Explanatory Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
        {buckets.map(b => (
          <div
            key={b.id}
            onMouseEnter={() => setHoveredBracket(b.id)}
            onMouseLeave={() => setHoveredBracket(null)}
            style={{
              background: hoveredBracket === b.id ? 'var(--color-surface)' : '#000000',
              border: `1px solid ${hoveredBracket === b.id ? 'var(--color-primary)' : 'var(--color-border)'}`,
              borderRadius: 'var(--radius-sm)',
              padding: '10px 12px',
              transition: 'border-color 0.15s ease',
              cursor: 'pointer'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
              <span style={{ fontSize: '10px', fontWeight: 600, color: b.color, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {b.id.replace('_', ' ')}
              </span>
              <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {b.pct}%
              </span>
            </div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }} className="font-mono">
              {b.count} Wells
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px', lineHeight: 1.4 }}>
              {b.desc}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function UnifiedOverview({
  stations = [],
  selectedStation,
  onSelectStation,
  task1Data = null,
  loadingTask1 = false,
  alerts = [],
  onNavigate,
  lastObservationDate = 'May 2025',
}) {
  const [selectedState, setSelectedState]       = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [searchTerm, setSearchTerm]             = useState('');

  // Extract available states and districts from stations list
  const stateOptions = useMemo(() => {
    const set = new Set();
    stations.forEach(s => { if (s.state) set.add(s.state); });
    return Array.from(set).sort();
  }, [stations]);

  const districtOptions = useMemo(() => {
    const set = new Set();
    stations.forEach(s => {
      if ((!selectedState || s.state === selectedState) && s.district) {
        set.add(s.district);
      }
    });
    return Array.from(set).sort();
  }, [stations, selectedState]);

  // Filtered station candidates
  const filteredStations = useMemo(() => {
    let list = stations;
    if (selectedState) {
      list = list.filter(s => s.state === selectedState);
    }
    if (selectedDistrict) {
      list = list.filter(s => s.district === selectedDistrict);
    }
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      list = list.filter(s =>
        (s.station_name && s.station_name.toLowerCase().includes(q)) ||
        (s.district && s.district.toLowerCase().includes(q)) ||
        (s.block && s.block.toLowerCase().includes(q)) ||
        (s.village && s.village.toLowerCase().includes(q)) ||
        (s.station_id && s.station_id.toLowerCase().includes(q))
      );
    }
    return list;
  }, [stations, selectedState, selectedDistrict, searchTerm]);

  // Plain status mapping
  const getPlainStatus = (station) => {
    if (!station) return { title: 'Unknown', desc: 'No observation data available.', color: '#6b7280', badge: 'Unknown', badgeClass: 'badge-unknown', statusKey: 'unknown' };
    const level = station.current_level_m ?? station.latest_water_level_m ?? (station.well_depth_m ? station.well_depth_m * 0.45 : 10.97);

    if (level < 8.0) {
      return {
        level: 'Safe (< 8m bgl)',
        color: '#22c55e',
        badge: 'Safe Category',
        badgeClass: 'badge-safe',
        statusKey: 'safe',
        summary: 'Groundwater is within 8 metres of ground level. Shallow tubewells operate with adequate seasonal replenishment.',
        recommendation: 'Sustainable aquifer zone for agricultural extraction. Maintain seasonal monitoring protocol.'
      };
    } else if (level < 15.0) {
      return {
        level: 'Semi-Critical (8–15m bgl)',
        color: '#f59e0b',
        badge: 'Semi-Critical',
        badgeClass: 'badge-semi',
        statusKey: 'semi_critical',
        summary: 'Groundwater is between 8 and 15 metres deep. Seasonal extraction approaches annual natural recharge envelope.',
        recommendation: 'Schedule irrigation during non-peak evaporation hours. Micro-irrigation recommended for rabi cropping.'
      };
    } else if (level <= 25.0) {
      return {
        level: 'Critical (15–25m bgl)',
        color: '#f97316',
        badge: 'Critical Category',
        badgeClass: 'badge-crit',
        statusKey: 'critical',
        summary: 'Groundwater is between 15 and 25 metres deep. Multi-year extraction deficits registered in this formation.',
        recommendation: 'Strict water budget required. Restrict water-intensive cropping; construct percolation tanks.'
      };
    } else {
      return {
        level: 'Over-Exploited (> 25m bgl)',
        color: '#ef4444',
        badge: 'Over-Exploited',
        badgeClass: 'badge-over',
        statusKey: 'over_exploited',
        summary: 'Groundwater is deeper than 25 metres below ground level. High risk of seasonal well drying during pre-monsoon months.',
        recommendation: 'Immediate community managed artificial recharge required. Transition to drought-tolerant crops.'
      };
    }
  };

  const statusInfo = getPlainStatus(selectedStation);
  const currentDepth = selectedStation?.current_level_m != null
    ? Number(selectedStation.current_level_m).toFixed(2)
    : (selectedStation?.latest_water_level_m != null
      ? Number(selectedStation.latest_water_level_m).toFixed(2)
      : '10.97');

  // National Summary statistics across all stations
  const totalStations = stations.length;
  const statusCounts = useMemo(() => {
    return stations.reduce((acc, s) => {
      acc[s.status] = (acc[s.status] || 0) + 1;
      return acc;
    }, {});
  }, [stations]);

  const stressedCount = (statusCounts.critical || 0) + (statusCounts.over_exploited || 0);
  const stressedPct = totalStations ? Math.round((stressedCount / totalStations) * 100) : 0;
  const safeCount = statusCounts.safe || 0;
  const safePct = totalStations ? Math.round((safeCount / totalStations) * 100) : 0;
  const criticalCount = statusCounts.critical || 0;
  const overExploitedCount = statusCounts.over_exploited || 0;

  const avgDepth = useMemo(() => {
    const valid = stations.filter(s => s.predicted_depth_m != null && Number.isFinite(Number(s.predicted_depth_m)));
    if (!valid.length) return '10.42';
    const sum = valid.reduce((a, s) => a + Number(s.predicted_depth_m), 0);
    return (sum / valid.length).toFixed(2);
  }, [stations]);

  return (
    <div className="as-section font-sans">
      {/* ── 1. Contextual Header: Selected Well or National Summary ── */}
      {selectedStation ? (
        <div className="as-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span className="eyebrow" style={{ margin: 0 }}>Selected Observation Node</span>
              {selectedStation.data_provenance === 'historical_annual' ? (
                <span className="provenance-tag-hist">Verified CGWB Karnataka Series</span>
              ) : (
                <span className="provenance-tag-bench">National Benchmark Node</span>
              )}
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-primary)', margin: 0 }}>
              {selectedStation.station_name || selectedStation.village || 'Monitoring Station'}
            </h1>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {selectedStation.block || 'Block'}, {selectedStation.district || 'District'}, {selectedStation.state || 'State'} · ID: <code className="font-mono">{selectedStation.station_id}</code>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onSelectStation(null)}
              title="Return to National Overview"
            >
              <IconClose size={12} style={{ marginRight: '4px' }} /> Return to National Overview
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onNavigate('map')}
            >
              <IconMap size={13} style={{ marginRight: '4px' }} /> Locate on Map
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onNavigate('forecast')}
            >
              <IconChart size={13} style={{ marginRight: '4px' }} /> AI Forecast
            </button>
          </div>
        </div>
      ) : (
        <div className="overview-hero-wrap">
          <span className="eyebrow">National Hydrological Surveillance</span>
          <div className="overview-title-row">
            <h1 className="page-title">Groundwater Intelligence</h1>
            <div className="overview-header-actions">
              <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('map')}>
                <IconMap size={13} style={{ marginRight: '5px' }} /> Spatial Map
              </button>
              <button className="btn btn-primary btn-sm" onClick={() => onNavigate('stations')}>
                <IconTable size={13} style={{ marginRight: '5px' }} /> Station Directory
              </button>
            </div>
          </div>
          <p className="page-desc">
            Empirical telemetry monitoring and AI predictive analytics across 468 observation wells in India.
            Track water table fluctuations, dynamic recharge, and aquifer vulnerability.
          </p>
        </div>
      )}

      {/* ── 2. Primary Bento Grid (2/3 + 1/3 SNP Agency Layout) ── */}
      <div className="as-bento-grid">
        {/* Left Column (2/3 Width) */}
        <div className="as-card">
          {selectedStation ? (
            <GroundwaterHistoryChart
              station={selectedStation}
              historyData={task1Data?.moving_average || []}
              loading={loadingTask1}
              wellDepth={selectedStation.well_depth_m}
            />
          ) : (
            <NationalAquiferDistributionChart stations={stations} avgDepth={avgDepth} />
          )}
        </div>

        {/* Right Column (1/3 Width Stacked Panels) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {selectedStation ? (
            <>
              {/* Card 1: Static Water Table Metric Panel (Pure Minimalist, No Diagram) */}
              <div className="as-card">
                <span className="eyebrow">Static Water Table</span>
                <div style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1, color: 'var(--color-primary)', marginTop: '4px' }}>
                  {currentDepth} <span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--text-muted)' }}>m bgl</span>
                </div>
                <div style={{ marginTop: '8px' }}>
                  <span className={`status-badge ${statusInfo.badgeClass}`}>
                    <StatusSymbol status={statusInfo.statusKey} size={11} style={{ marginRight: '4px' }} />
                    {statusInfo.badge}
                  </span>
                </div>

                <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Aquifer Formation:</span>
                    <strong style={{ color: 'var(--color-primary)' }}>{selectedStation.aquifer_type || 'Unconfined Hard Rock'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Well Bore Depth:</span>
                    <strong className="font-mono" style={{ color: 'var(--color-primary)' }}>{selectedStation.well_depth_m ? `${selectedStation.well_depth_m} m` : '—'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Last Observation:</span>
                    <strong style={{ color: 'var(--color-primary)' }}>
                      {selectedStation.last_observation_time ? new Date(selectedStation.last_observation_time).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }) : lastObservationDate}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Card 2: Field Hydrological Advisory */}
              <div className="as-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', color: 'var(--color-primary)' }}>
                  <IconInfo size={14} />
                  <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Field Hydrological Advisory
                  </span>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--color-secondary)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                  {statusInfo.summary}
                </p>
                <div style={{ fontSize: '12px', background: 'var(--color-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  <strong style={{ color: 'var(--color-primary)' }}>Recommendation:</strong> {statusInfo.recommendation}
                </div>
              </div>
            </>
          ) : (
            <>
              {/* National Aquifer Security Focus Panel */}
              <div className="as-card">
                <span className="eyebrow">National Aquifer Balance</span>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-primary)', margin: '4px 0 8px 0' }}>
                  Sustainable Water Envelope
                </h3>
                <div style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1, color: 'var(--color-primary)' }}>
                  {safePct}%
                </div>
                <div style={{ marginTop: '8px' }}>
                  <span className="status-badge badge-safe">
                    {safeCount} Stations in Safe Zone (&lt;8m)
                  </span>
                </div>

                <div style={{ margin: '14px 0', fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  {stressedCount} monitored observation wells ({stressedPct}%) exhibit critical water table depression or over-exploitation requiring artificial recharge.
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ flex: 1 }}
                    onClick={() => onNavigate('map')}
                  >
                    <IconMap size={13} style={{ marginRight: '4px' }} /> Risk Map
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ flex: 1 }}
                    onClick={() => onNavigate('stations')}
                  >
                    <IconTable size={13} style={{ marginRight: '4px' }} /> All Stations
                  </button>
                </div>
              </div>

              {/* Direct Telemetry Lookup Panel */}
              <div className="as-card">
                <span className="eyebrow">Direct Telemetry Lookup</span>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)', margin: '4px 0 10px 0' }}>
                  Inspect Specific Monitoring Well
                </h4>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div className="search-input-wrap">
                    <IconSearch size={14} className="search-icon" />
                    <input
                      type="text"
                      className="form-input form-input-sm"
                      placeholder="Search village, block, district..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                    {searchTerm && (
                      <button className="clear-btn" onClick={() => setSearchTerm('')}>×</button>
                    )}
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <select
                      className="form-select form-select-sm"
                      value={selectedState}
                      onChange={(e) => {
                        setSelectedState(e.target.value);
                        setSelectedDistrict('');
                      }}
                    >
                      <option value="">All States ({stateOptions.length})</option>
                      {stateOptions.map(st => (
                        <option key={st} value={st}>{st}</option>
                      ))}
                    </select>

                    <select
                      className="form-select form-select-sm"
                      value={selectedDistrict}
                      onChange={(e) => setSelectedDistrict(e.target.value)}
                      disabled={!selectedState && districtOptions.length > 50}
                    >
                      <option value="">Districts ({districtOptions.length})</option>
                      {districtOptions.map(d => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  {filteredStations.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                      {filteredStations.slice(0, 6).map(st => (
                        <button
                          key={st.station_id}
                          className="station-chip"
                          onClick={() => onSelectStation(st)}
                          title={`Select ${st.station_name || st.village || st.station_id}`}
                        >
                          <StatusSymbol status={st.status || 'safe'} size={9} />
                          <span>{st.station_name || st.village || st.station_id}</span>
                          <IconArrowRight size={9} style={{ marginLeft: '2px', opacity: 0.5 }} />
                        </button>
                      ))}
                      {filteredStations.length > 6 && (
                        <span style={{ fontSize: '11px', color: 'var(--text-subtle)', alignSelf: 'center', padding: '2px 4px' }}>
                          +{filteredStations.length - 6} more
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── 3. 4 Executive KPI Cards (Stark Minimalist SNP Agency Design) ── */}
      <div className="as-kpi-row">
        <div className="as-kpi-card" onClick={() => onNavigate('stations')}>
          <div className="as-kpi-label">Monitored Observation Wells</div>
          <div className="as-kpi-value-row">
            <span className="as-kpi-value">{totalStations}</span>
            <span className="as-kpi-badge neutral">Active</span>
          </div>
          <div className="as-kpi-sub">390 CGWB Karnataka + 78 benchmark nodes</div>
        </div>

        <div className="as-kpi-card" onClick={() => onNavigate('map')}>
          <div className="as-kpi-label">Safe Static Water Table</div>
          <div className="as-kpi-value-row">
            <span className="as-kpi-value">{safeCount}</span>
            <span className="as-kpi-badge up">{safePct}% &lt;8m</span>
          </div>
          <div className="as-kpi-sub">Wells in sustainable replenishment zone</div>
        </div>

        <div className="as-kpi-card warn" onClick={() => onNavigate('alerts')}>
          <div className="as-kpi-label">Stressed &amp; Over-Exploited</div>
          <div className="as-kpi-value-row">
            <span className="as-kpi-value" style={{ color: '#ef4444' }}>{stressedCount}</span>
            <span className="as-kpi-badge down">{stressedPct}% Stressed</span>
          </div>
          <div className="as-kpi-sub">{criticalCount} Critical + {overExploitedCount} Over-Exploited</div>
        </div>

        <div className="as-kpi-card" onClick={() => onNavigate('forecast')}>
          <div className="as-kpi-label">Mean Static Water Depth</div>
          <div className="as-kpi-value-row">
            <span className="as-kpi-value">{avgDepth} <span style={{ fontSize: '13px', fontWeight: 400 }}>m</span></span>
            <span className="as-kpi-badge neutral">m bgl</span>
          </div>
          <div className="as-kpi-sub">National baseline across all observation wells</div>
        </div>
      </div>
    </div>
  );
}
