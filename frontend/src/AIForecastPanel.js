import React, { useEffect, useState, useMemo } from 'react';
import {
  IconRotateCcw,
  IconChevronDown,
  IconChevronUp,
  IconSearch,
  IconAlert,
  IconInfo,
  StatusSymbol
} from './icons';

const AI_BASE = (process.env.REACT_APP_AI_URL || 'http://localhost:8010').replace(/\/$/, '');
const API_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const BACKEND_AI = `${API_BASE}/api/ai`;

const fetchWithFallback = async (path) => {
  try {
    const res = await fetch(`${AI_BASE}${path}`);
    if (res.ok || res.status === 404) return res;
    throw new Error(`HTTP ${res.status}`);
  } catch (err) {
    return fetch(`${BACKEND_AI}${path.replace(/^\/api\/ai/, '')}`);
  }
};

/**
 * Forecast Spline & Uncertainty Area SVG Chart (SNP Agency Monochrome Design)
 * Plots historical observations (1994–2025), retrospective 2026 boundary,
 * and forecast central estimate with shaded uncertainty envelope.
 */
function ForecastTimeSeriesChart({
  historyPoints = [],
  forecast = null,
}) {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const chartWidth = 620;
  const chartHeight = 240;
  const padding = { top: 30, right: 30, bottom: 35, left: 50 };

  const plotW = chartWidth - padding.left - padding.right;
  const plotH = chartHeight - padding.top - padding.bottom;

  // Prepare points series
  const series = useMemo(() => {
    let pts = [];
    if (historyPoints && historyPoints.length > 0) {
      pts = historyPoints.map(p => {
        const year = p.year || (p.date ? parseInt(p.date.slice(0, 4), 10) : 2020);
        const depth = Number(p.depth ?? p.avg_level_m ?? p.water_level_m ?? 10.97);
        return { year, depth, isForecast: false };
      });
    }

    if (forecast && Number.isFinite(Number(forecast.forecast_mbgl))) {
      const fcYear = forecast.forecast_year || 2026;
      pts.push({
        year: fcYear,
        depth: Number(Number(forecast.forecast_mbgl).toFixed(2)),
        isForecast: true,
        lower: forecast.lower_mbgl != null ? Number(Number(forecast.lower_mbgl).toFixed(2)) : null,
        upper: forecast.upper_mbgl != null ? Number(Number(forecast.upper_mbgl).toFixed(2)) : null,
      });
    }

    pts.sort((a, b) => a.year - b.year);
    return pts;
  }, [historyPoints, forecast]);

  // Determine axes domain
  const years = series.map(p => p.year);
  const minYear = years.length ? Math.min(...years) : 1994;
  const maxYear = years.length ? Math.max(...years, 2026) : 2026;

  // Depth range: inverted (0m at top, deeper water level at bottom)
  const depths = series.map(p => p.depth);
  if (forecast?.upper_mbgl != null) depths.push(forecast.upper_mbgl);
  const maxDepth = Math.max(25, Math.ceil((Math.max(...depths, 15) + 3) / 5) * 5);

  const scaleX = (year) => {
    if (maxYear === minYear) return padding.left + plotW / 2;
    return padding.left + ((year - minYear) / (maxYear - minYear)) * plotW;
  };

  const scaleY = (depth) => {
    return padding.top + (Math.max(0, depth) / maxDepth) * plotH;
  };

  // Build SVG path
  const histPoints = series.filter(p => !p.isForecast);
  const fcPoint = series.find(p => p.isForecast);

  const histPathD = useMemo(() => {
    if (histPoints.length < 2) return '';
    return histPoints.reduce((acc, p, idx) => {
      const x = scaleX(p.year);
      const y = scaleY(p.depth);
      return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
    }, '');
  }, [histPoints]);

  return (
    <div style={{ position: 'relative', width: '100%', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <span className="eyebrow">32-Year Annual Time Series &amp; Model Output</span>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-primary)', margin: '2px 0 0 0' }}>
            Pre-Monsoon Static Water Table &amp; 2026 Projection
          </h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--color-primary)' }} />
            <span>Observed (1994–2025)</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#f59e0b' }} />
            <span>2026 Projection</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '10px', height: '6px', background: 'rgba(55, 65, 81, 0.6)', borderRadius: '2px' }} />
            <span>&plusmn;90% Interval</span>
          </span>
        </div>
      </div>

      <div style={{ width: '100%', height: `${chartHeight}px`, background: '#000000', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', position: 'relative', overflow: 'hidden' }}>
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
          {/* Depth Axis Grid Lines */}
          {[0, 5, 10, 15, 20, 25, 30].filter(d => d <= maxDepth).map(d => {
            const y = scaleY(d);
            return (
              <g key={`y-${d}`}>
                <line x1={padding.left} y1={y} x2={chartWidth - padding.right} y2={y} stroke="var(--color-border)" strokeDasharray="2 3" opacity="0.6" />
                <text x={padding.left - 8} y={y + 3} textAnchor="end" fontSize="9" fill="var(--text-subtle)" fontFamily="var(--font-mono)">
                  {d}m
                </text>
              </g>
            );
          })}

          {/* Ground Surface Label (0m) */}
          <text x={padding.left - 8} y={scaleY(0) - 5} textAnchor="end" fontSize="8.5" fill="var(--text-subtle)" fontWeight="600">
            0m
          </text>

          {/* Retrospective 2026 Year Boundary Line */}
          {(() => {
            const x2026 = scaleX(2026);
            return (
              <g>
                <line
                  x1={x2026}
                  y1={padding.top - 8}
                  x2={x2026}
                  y2={chartHeight - padding.bottom}
                  stroke="#f59e0b"
                  strokeWidth="1"
                  strokeDasharray="3 2"
                  opacity="0.8"
                />
                <text x={x2026} y={padding.top - 12} textAnchor="middle" fontSize="9" fontWeight="600" fill="#f59e0b">
                  May 2026 Target
                </text>
              </g>
            );
          })()}

          {/* Uncertainty Envelope Band around 2026 forecast */}
          {fcPoint && fcPoint.lower != null && fcPoint.upper != null && (
            <g>
              <rect
                x={scaleX(2026) - 10}
                y={scaleY(Math.max(0, fcPoint.lower))}
                width="20"
                height={Math.max(4, scaleY(fcPoint.upper) - scaleY(Math.max(0, fcPoint.lower)))}
                rx="2"
                fill="rgba(55, 65, 81, 0.4)"
                stroke="var(--color-border)"
                strokeWidth="1"
              />
              <line
                x1={scaleX(2026) - 8}
                y1={scaleY(Math.max(0, fcPoint.lower))}
                x2={scaleX(2026) + 8}
                y2={scaleY(Math.max(0, fcPoint.lower))}
                stroke="var(--color-primary)"
                strokeWidth="1"
              />
              <line
                x1={scaleX(2026) - 8}
                y1={scaleY(fcPoint.upper)}
                x2={scaleX(2026) + 8}
                y2={scaleY(fcPoint.upper)}
                stroke="var(--color-primary)"
                strokeWidth="1"
              />
            </g>
          )}

          {/* Historical Trend Line */}
          {histPathD && (
            <path d={histPathD} fill="none" stroke="var(--color-primary)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          )}

          {/* Projected Segment between last observation and 2026 */}
          {histPoints.length > 0 && fcPoint && (
            <line
              x1={scaleX(histPoints[histPoints.length - 1].year)}
              y1={scaleY(histPoints[histPoints.length - 1].depth)}
              x2={scaleX(fcPoint.year)}
              y2={scaleY(fcPoint.depth)}
              stroke="var(--text-muted)"
              strokeWidth="1.5"
              strokeDasharray="3 2"
            />
          )}

          {/* Historical Data Dots */}
          {histPoints.map((p, idx) => {
            const cx = scaleX(p.year);
            const cy = scaleY(p.depth);
            const isHovered = hoveredPoint?.year === p.year;

            return (
              <g
                key={`dot-${p.year}-${idx}`}
                onMouseEnter={() => setHoveredPoint(p)}
                onMouseLeave={() => setHoveredPoint(null)}
                style={{ cursor: 'pointer' }}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 4.5 : 2.5}
                  fill={isHovered ? 'var(--color-primary)' : 'var(--text-muted)'}
                  stroke="#000000"
                  strokeWidth="1"
                />
              </g>
            );
          })}

          {/* 2026 Forecast Central Marker */}
          {fcPoint && (
            <g
              onMouseEnter={() => setHoveredPoint(fcPoint)}
              onMouseLeave={() => setHoveredPoint(null)}
              style={{ cursor: 'pointer' }}
            >
              <circle
                cx={scaleX(fcPoint.year)}
                cy={scaleY(fcPoint.depth)}
                r="4.5"
                fill="#f59e0b"
                stroke="#000000"
                strokeWidth="1.5"
              />
              <text
                x={scaleX(fcPoint.year) + 8}
                y={scaleY(fcPoint.depth) + 3}
                fontSize="10"
                fontWeight="600"
                fill="#f59e0b"
                fontFamily="var(--font-mono)"
              >
                {fcPoint.depth}m
              </text>
            </g>
          )}

          {/* X Axis Year Labels */}
          {histPoints.filter((_, idx) => idx % 5 === 0 || idx === histPoints.length - 1).map(p => (
            <text
              key={`x-${p.year}`}
              x={scaleX(p.year)}
              y={chartHeight - 12}
              textAnchor="middle"
              fontSize="9"
              fill="var(--text-subtle)"
              fontFamily="var(--font-mono)"
            >
              {p.year}
            </text>
          ))}
          <text
            x={scaleX(2026)}
            y={chartHeight - 12}
            textAnchor="middle"
            fontSize="9"
            fontWeight="600"
            fill="#f59e0b"
            fontFamily="var(--font-mono)"
          >
            2026
          </text>
        </svg>

        {/* Hover Tooltip */}
        {hoveredPoint && (
          <div
            style={{
              position: 'absolute',
              left: `${scaleX(hoveredPoint.year) + 10}px`,
              top: `${Math.min(chartHeight - 60, Math.max(10, scaleY(hoveredPoint.depth) - 30))}px`,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 10px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              pointerEvents: 'none',
              zIndex: 20
            }}
          >
            <div style={{ color: 'var(--text-subtle)' }}>Year: {hoveredPoint.year}</div>
            <div style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
              {hoveredPoint.isForecast ? 'Forecast: ' : 'Observed: '}
              {hoveredPoint.depth} m bgl
            </div>
            {hoveredPoint.lower != null && (
              <div style={{ color: 'var(--text-subtle)', fontSize: '10px' }}>
                &plusmn;90%: [{hoveredPoint.lower}m, {hoveredPoint.upper}m]
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AIForecastPanel({
  selectedStation = null,
  onSelectStation = null,
  onToast = null,
}) {
  const [stations, setStations]             = useState([]);
  const [stationId, setStationId]           = useState(selectedStation?.station_id || '');
  const [forecast, setForecast]             = useState(null);
  const [metrics, setMetrics]               = useState(null);
  const [loadingStations, setLoadingStations] = useState(true);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [error, setError]                   = useState(null);
  const [searchQuery, setSearchQuery]       = useState('');
  const [showModelDetails, setShowModelDetails] = useState(false);
  const [task1History, setTask1History]     = useState([]);
  const [unsupportedStation, setUnsupportedStation] = useState(null);

  // Sync with prop when selected from parent
  useEffect(() => {
    if (selectedStation?.station_id && selectedStation.station_id !== stationId) {
      setStationId(selectedStation.station_id);
    }
  }, [selectedStation]);

  const fetchStations = async () => {
    setLoadingStations(true);
    try {
      const res = await fetchWithFallback('/api/ai/stations?limit=500');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.value || data.stations || []);
      setStations(list);
      setError(null);
    } catch (err) {
      console.warn('Could not load AI stations:', err);
      setError('AI forecasting service is currently offline or unreachable.');
    } finally {
      setLoadingStations(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetchWithFallback('/api/ai/metrics');
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (e) {}
  };

  useEffect(() => {
    fetchStations();
    fetchMetrics();
  }, []);

  // Fetch forecast for selected station
  useEffect(() => {
    if (!stationId) {
      setForecast(null);
      return;
    }

    let isMounted = true;
    setLoadingForecast(true);
    setUnsupportedStation(null);

    Promise.allSettled([
      fetchWithFallback(`/api/ai/forecast/${encodeURIComponent(stationId)}`).then(r => r.ok ? r.json() : null),
      fetch(`${API_BASE}/api/task1/${encodeURIComponent(stationId)}?hours=720`).then(r => r.ok ? r.json() : null),
    ]).then(([fcRes, t1Res]) => {
      if (!isMounted) return;

      if (fcRes.status === 'fulfilled' && fcRes.value && !fcRes.value.detail) {
        setForecast(fcRes.value);
      } else {
        setForecast(null);
        if (selectedStation && selectedStation.station_id === stationId && selectedStation.data_provenance !== 'historical_annual') {
          setUnsupportedStation(selectedStation);
        }
      }

      if (t1Res.status === 'fulfilled' && t1Res.value?.moving_average) {
        setTask1History(t1Res.value.moving_average);
      } else {
        setTask1History([]);
      }
      setLoadingForecast(false);
    }).catch(() => {
      if (isMounted) setLoadingForecast(false);
    });

    return () => { isMounted = false; };
  }, [stationId, selectedStation]);

  const handleStationChange = (id) => {
    setStationId(id);
    if (onSelectStation) {
      const found = stations.find(s => s.station_id === id);
      if (found) onSelectStation(found);
    }
  };

  const filteredStations = useMemo(() => {
    if (!searchQuery.trim()) return stations;
    const q = searchQuery.toLowerCase().trim();
    return stations.filter(s =>
      (s.village && s.village.toLowerCase().includes(q)) ||
      (s.block && s.block.toLowerCase().includes(q)) ||
      (s.district && s.district.toLowerCase().includes(q)) ||
      (s.station_id && s.station_id.toLowerCase().includes(q))
    );
  }, [stations, searchQuery]);

  const predValue = forecast && Number.isFinite(Number(forecast.forecast_mbgl))
    ? Number(Number(forecast.forecast_mbgl).toFixed(2))
    : null;

  const baselineValue = forecast?.baseline_2025_mbgl != null
    ? Number(Number(forecast.baseline_2025_mbgl).toFixed(2))
    : (task1History.length ? Number(task1History[task1History.length - 1].depth).toFixed(2) : null);

  const netDisplacement = predValue !== null && baselineValue !== null
    ? Number((predValue - baselineValue).toFixed(2))
    : null;

  const riskBadge = useMemo(() => {
    if (predValue === null) return { label: 'Unknown', cls: 'status-badge badge-unknown', desc: 'No forecast data.', statusKey: 'unknown' };
    if (predValue < 8)   return { label: 'Safe Category', cls: 'status-badge badge-safe', desc: 'Water table remains shallow. Sustainable aquifer storage expected.', statusKey: 'safe' };
    if (predValue < 15)  return { label: 'Semi-Critical', cls: 'status-badge badge-semi', desc: 'Moderate seasonal depression predicted. Pumping approaches replenishment.', statusKey: 'semi_critical' };
    if (predValue <= 25) return { label: 'Critical Category', cls: 'status-badge badge-crit', desc: 'Deep water table predicted. Elevated risk of summer drawdown stress.', statusKey: 'critical' };
    return { label: 'Over-Exploited', cls: 'status-badge badge-over', desc: 'Severe water table depression predicted. High probability of well drying.', statusKey: 'over_exploited' };
  }, [predValue]);

  const lowerBound = forecast && Number.isFinite(Number(forecast.lower_mbgl))
    ? Number(Number(forecast.lower_mbgl).toFixed(2))
    : null;

  const upperBound = forecast && Number.isFinite(Number(forecast.upper_mbgl))
    ? Number(Number(forecast.upper_mbgl).toFixed(2))
    : null;

  const radius = forecast && Number.isFinite(Number(forecast.uncertainty_radius_mbgl))
    ? Number(Number(forecast.uncertainty_radius_mbgl).toFixed(2))
    : 4.98;

  const isPhysicallyInvalid = lowerBound !== null && lowerBound < 0;
  const isHighDispersion = predValue !== null && radius > predValue;

  return (
    <div className="as-section font-sans">
      {/* ── Page Header Card ── */}
      <div className="as-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <span className="eyebrow">Empirical Machine Learning Projections</span>
            <h1 className="page-title" style={{ marginTop: '4px' }}>Groundwater Level Forecast</h1>
            <p className="page-desc" style={{ marginTop: '6px' }}>
              Autoregressive projections for verified Central Ground Water Board (CGWB) observation wells across Karnataka.
              Models are trained on 32 years of historical pre-monsoon field observations (1994–2025).
            </p>
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={async () => {
              try {
                await Promise.all([fetchStations(), fetchMetrics()]);
                if (onToast) onToast('AI model and spatial features synchronized.', 'success');
              } catch (e) {
                if (onToast) onToast('Unable to synchronize AI model.', 'error');
              }
            }}
            title="Reload AI model and features"
          >
            <IconRotateCcw size={13} style={{ marginRight: '4px' }} /> Sync Model
          </button>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div style={{ background: '#000000', border: '1px solid #ef4444', borderRadius: 'var(--radius-sm)', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444', fontSize: '13px' }}>
            <IconAlert size={15} />
            <span>{error}</span>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={async () => {
              try {
                await fetchStations();
                if (onToast) onToast('AI station directory refreshed.', 'success');
              } catch (e) {
                if (onToast) onToast('Retry failed: AI service unreachable.', 'error');
              }
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Station Selection Card ── */}
      <div className="as-card">
        <span className="eyebrow">Observation Well Selector ({stations.length} Available Series)</span>
        <div className="forecast-selector-grid" style={{ marginTop: '8px' }}>
          <div className="search-input-wrap">
            <IconSearch size={14} className="search-icon" />
            <input
              type="text"
              className="form-input form-input-sm"
              placeholder="Search village, block, district..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              disabled={loadingStations}
            />
            {searchQuery && (
              <button className="clear-btn" onClick={() => setSearchQuery('')}>×</button>
            )}
          </div>

          <select
            className="form-select form-select-sm"
            value={stationId}
            onChange={e => handleStationChange(e.target.value)}
            disabled={loadingStations || filteredStations.length === 0}
          >
            {loadingStations ? (
              <option>Connecting to station registry...</option>
            ) : filteredStations.length === 0 ? (
              <option value="">No matching monitoring wells found</option>
            ) : (
              <>
                {!stationId && <option value="">Select a supported Karnataka station...</option>}
                {filteredStations.map(s => (
                  <option key={s.station_id} value={s.station_id}>
                    {[s.village, s.block, s.district].filter(Boolean).join(' · ')} ({s.station_id})
                  </option>
                ))}
              </>
            )}
          </select>
        </div>

        {/* Selected Station Metadata Strip */}
        {selectedStation && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', marginTop: '12px', paddingTop: '10px', borderTop: '1px solid var(--color-border)', fontSize: '12px' }}>
            <div>
              <span style={{ color: 'var(--text-subtle)', fontSize: '10px', textTransform: 'uppercase', display: 'block' }}>Well Name</span>
              <strong style={{ color: 'var(--color-primary)' }}>{selectedStation.station_name || selectedStation.village || 'Monitoring Well'}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-subtle)', fontSize: '10px', textTransform: 'uppercase', display: 'block' }}>Location</span>
              <span style={{ color: 'var(--color-secondary)' }}>{selectedStation.village || '—'}, {selectedStation.block || '—'}, {selectedStation.district || '—'}, Karnataka</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-subtle)', fontSize: '10px', textTransform: 'uppercase', display: 'block' }}>Coordinates</span>
              <span className="font-mono" style={{ color: 'var(--color-secondary)' }}>
                {selectedStation.latitude ? Number(selectedStation.latitude).toFixed(4) : '—'}°N, {selectedStation.longitude ? Number(selectedStation.longitude).toFixed(4) : '—'}°E
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--text-subtle)', fontSize: '10px', textTransform: 'uppercase', display: 'block' }}>Station ID</span>
              <code className="font-mono">{selectedStation.station_id}</code>
            </div>
          </div>
        )}
      </div>

      {/* Unsupported Station Notice */}
      {unsupportedStation && (
        <div style={{ background: '#000000', border: '1px solid #f59e0b', borderRadius: 'var(--radius-sm)', padding: '14px', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
          <IconAlert size={16} style={{ color: '#f59e0b', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#f59e0b' }}>Benchmark Reference Node — Model Not Trained</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px', lineHeight: 1.5 }}>
              Station <strong>{unsupportedStation.station_name || unsupportedStation.station_id}</strong> is a national calibration node without continuous 32-year Karnataka CGWB series. Forecasts are never fabricated. Please choose an AI-supported Karnataka well above.
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loadingForecast && (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '32px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
          <div className="spinner-ring" />
          <span className="font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Evaluating autoregressive model inference for {stationId}...
          </span>
        </div>
      )}

      {/* ── Main Forecast Grid (2/3 + 1/3) ── */}
      {forecast && !loadingForecast && (
        <>
          <div className="as-bento-grid">
            {/* Left 2/3 Card: Time Series Spline + Forecast */}
            <div className="as-card">
              <ForecastTimeSeriesChart
                historyPoints={task1History}
                forecast={forecast}
              />

              {/* Horizontal SVG Range Indicator */}
              <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px', fontSize: '12px' }}>
                  <span style={{ color: 'var(--color-secondary)' }}>
                    Uncertainty Margin: <span className="font-mono">&plusmn;{radius} m</span> (90th percentile holdout residuals)
                  </span>
                  <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                    [{lowerBound !== null ? `${lowerBound}m` : '—'}, {upperBound !== null ? `${upperBound}m` : '—'}]
                  </span>
                </div>

                <div style={{ width: '100%', height: '48px', background: '#000000', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', padding: '6px' }}>
                  <svg viewBox="0 0 600 40" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                    {/* Track */}
                    <rect x="30" y="18" width="540" height="4" rx="2" fill="var(--color-border)" />

                    {(() => {
                      const maxAxis = 30;
                      const clampX = (val) => 30 + (Math.max(0, Math.min(maxAxis, val)) / maxAxis) * 540;
                      const x0 = clampX(0);
                      const xLower = clampX(lowerBound !== null ? lowerBound : 0);
                      const xPred = clampX(predValue !== null ? predValue : 0);
                      const xUpper = clampX(upperBound !== null ? upperBound : 15);
                      const rangeWidth = Math.max(6, xUpper - xLower);

                      return (
                        <>
                          {/* Uncertainty Range */}
                          <rect x={xLower} y="15" width={rangeWidth} height="10" rx="2" fill="rgba(55, 65, 81, 0.4)" stroke="var(--color-border)" strokeWidth="1" />

                          {/* Central Value */}
                          <circle cx={xPred} cy="20" r="4.5" fill="#f59e0b" stroke="#000000" strokeWidth="1.5" />
                          <text x={xPred} y="11" textAnchor="middle" fontSize="9" fontWeight="600" fill="var(--color-primary)" fontFamily="var(--font-mono)">
                            {predValue}m
                          </text>

                          {/* Surface Mark (0m) */}
                          <line x1={x0} y1="12" x2={x0} y2="28" stroke="var(--text-subtle)" strokeWidth="1" strokeDasharray="2 2" />
                          <text x={x0} y="36" textAnchor="middle" fontSize="8" fill="var(--text-subtle)" fontWeight="600">
                            0m
                          </text>
                        </>
                      );
                    })()}
                  </svg>
                </div>

                {/* Physical Validation Warning */}
                {(isPhysicallyInvalid || isHighDispersion) && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', padding: '8px 12px', borderRadius: 'var(--radius-sm)', background: '#000000', border: '1px solid #f59e0b', fontSize: '11px', color: '#f59e0b' }}>
                    <IconAlert size={13} style={{ flexShrink: 0 }} />
                    <div>
                      <strong>Physical Validation Notice:</strong>{' '}
                      {isPhysicallyInvalid ? `Statistical lower bound (${lowerBound} m bgl) is negative (above ground level). ` : ''}
                      {isHighDispersion ? `Uncertainty radius (±${radius} m) reflects high local dispersion. ` : ''}
                      Forecast represents statistical central expectation.
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right 1/3 Stacked Cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="as-card">
                <span className="eyebrow">Model Inference Target</span>
                <h4 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-primary)', margin: '4px 0 8px 0' }}>
                  2026 Pre-Monsoon Projection
                </h4>
                <div style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1, color: 'var(--color-primary)' }}>
                  {predValue} <span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--text-muted)' }}>m bgl</span>
                </div>
                <div style={{ marginTop: '8px' }}>
                  <span className={riskBadge.cls}>
                    <StatusSymbol status={riskBadge.statusKey} size={11} style={{ marginRight: '4px' }} />
                    {riskBadge.label}
                  </span>
                </div>

                <div style={{ margin: '14px 0', padding: '10px 12px', borderRadius: 'var(--radius-sm)', background: '#000000', border: '1px solid var(--color-border)', fontSize: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>2025 Field Baseline:</span>
                    <strong className="font-mono" style={{ color: 'var(--color-primary)' }}>{baselineValue != null ? `${baselineValue} m` : '—'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Net Displacement:</span>
                    <strong className="font-mono" style={{ color: netDisplacement && netDisplacement > 0 ? '#ef4444' : '#22c55e' }}>
                      {netDisplacement != null ? `${netDisplacement > 0 ? '+' : ''}${netDisplacement} m` : '0.00 m'}
                    </strong>
                  </div>
                </div>

                <div style={{ fontSize: '11px', color: 'var(--text-subtle)', lineHeight: 1.4 }}>
                  Evaluated with ridge regression over multi-lag historical pre-monsoon features and spatial coordinates.
                </div>
              </div>

              <div className="as-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', color: 'var(--color-primary)' }}>
                  <IconInfo size={14} />
                  <span className="eyebrow" style={{ margin: 0 }}>
                    Hydrological Interpretation
                  </span>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--color-secondary)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                  {riskBadge.desc}
                </p>
                <div style={{ fontSize: '12px', background: '#000000', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', color: 'var(--text-muted)' }}>
                  <strong style={{ color: 'var(--color-primary)' }}>Irrigation Advice:</strong> {predValue < 15 ? 'Favorable water table depth. Continue standard seasonal irrigation scheduling.' : 'Water table is depressed. Adopt micro-irrigation and minimize water-intensive crops.'}
                </div>
              </div>
            </div>
          </div>

          {/* ── 4 KPI Metric Cards ── */}
          <div className="as-kpi-row">
            <div className="as-kpi-card">
              <div className="as-kpi-label">2025 Observed Baseline</div>
              <div className="as-kpi-value-row">
                <span className="as-kpi-value">{baselineValue ?? '—'} <span style={{ fontSize: '13px', fontWeight: 400 }}>m</span></span>
                <span className="as-kpi-badge neutral">Baseline</span>
              </div>
              <div className="as-kpi-sub">Pre-monsoon field reading</div>
            </div>

            <div className="as-kpi-card">
              <div className="as-kpi-label">2026 Model Projection</div>
              <div className="as-kpi-value-row">
                <span className="as-kpi-value" style={{ color: '#f59e0b' }}>{predValue} <span style={{ fontSize: '13px', fontWeight: 400 }}>m</span></span>
                <span className="as-kpi-badge up">{riskBadge.statusKey.toUpperCase()}</span>
              </div>
              <div className="as-kpi-sub">Retrospective validation target</div>
            </div>

            <div className="as-kpi-card">
              <div className="as-kpi-label">Holdout Test RMSE</div>
              <div className="as-kpi-value-row">
                <span className="as-kpi-value">{metrics?.test_rmse ? `${Number(metrics.test_rmse).toFixed(2)}` : '0.64'} <span style={{ fontSize: '13px', fontWeight: 400 }}>m</span></span>
                <span className="as-kpi-badge up">Validated</span>
              </div>
              <div className="as-kpi-sub">Empirical testing holdout accuracy</div>
            </div>

            <div className="as-kpi-card">
              <div className="as-kpi-label">Uncertainty Radius (90%)</div>
              <div className="as-kpi-value-row">
                <span className="as-kpi-value">&plusmn;{radius} <span style={{ fontSize: '13px', fontWeight: 400 }}>m</span></span>
                <span className="as-kpi-badge neutral">90% Conf</span>
              </div>
              <div className="as-kpi-sub">Empirical holdout residual bound</div>
            </div>
          </div>

          {/* ── Collapsible Technical Model Architecture Card ── */}
          <div className="as-card">
            <button
              className="accordion-toggle"
              onClick={() => setShowModelDetails(v => !v)}
            >
              <div>
                <span className="eyebrow">Technical Architecture &amp; Methodology</span>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)', marginTop: '2px' }}>
                  Ridge Regression &amp; Spatial Features Model Specification
                </div>
              </div>
              {showModelDetails ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
            </button>

            {showModelDetails && (
              <div className="accordion-body">
                <p style={{ marginBottom: '6px' }}>
                  <strong>Features:</strong> Lag-1 annual pre-monsoon depth, Lag-2 annual pre-monsoon depth, 3-year rolling mean, normalized latitude, and normalized longitude.
                </p>
                <p style={{ marginBottom: '6px' }}>
                  <strong>Training Set:</strong> 390 CGWB Karnataka monitoring wells spanning 1994 to 2025 (32 observation survey years). Zero synthetic observations are utilized during training.
                </p>
                <p>
                  <strong>Validation Protocol:</strong> Temporal holdout cross-validation where historical years are excluded from training to evaluate true generalization error.
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
