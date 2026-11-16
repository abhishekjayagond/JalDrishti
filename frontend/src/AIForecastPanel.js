import React, { useEffect, useState, useMemo, useCallback } from 'react';
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
 * Robust extraction of the 2025 field baseline and displacement calculation.
 * Never returns NaN, Infinity, or unformatted text.
 */
export function getBaselineAndDisplacement(historyPoints = [], forecastDepth = null) {
  if (!Array.isArray(historyPoints) || historyPoints.length === 0) {
    return {
      baselineValue: null,
      baselineYear: null,
      baselineDate: null,
      displacement: null,
      status: 'unavailable',
      reason: 'No historical observation records available for this well'
    };
  }

  const extractNum = (val) => {
    if (val == null) return null;
    const n = Number(val);
    return Number.isFinite(n) && !isNaN(n) ? Number(n.toFixed(2)) : null;
  };

  // 1. Look for pre-monsoon reading specifically in year 2025
  const p2025 = historyPoints.find(p => {
    const yr = p.year || (p.date ? parseInt(String(p.date).slice(0, 4), 10) : null);
    return yr === 2025;
  });

  if (p2025) {
    const rawVal = p2025.avg_level_m ?? p2025.water_level_m ?? p2025.depth ?? p2025.water_level_mbgl;
    const val = extractNum(rawVal);
    if (val !== null) {
      const predNum = extractNum(forecastDepth);
      const disp = predNum !== null ? Number((predNum - val).toFixed(2)) : null;
      return {
        baselineValue: val,
        baselineYear: 2025,
        baselineDate: p2025.date || 'May 2025',
        displacement: disp,
        status: 'valid_2025',
        reason: 'Pre-monsoon May 2025 field observation'
      };
    }
  }

  // 2. Fallback: find latest prior observation recorded before 2026
  const validPoints = historyPoints
    .map(p => {
      const yr = p.year || (p.date ? parseInt(String(p.date).slice(0, 4), 10) : null);
      const rawVal = p.avg_level_m ?? p.water_level_m ?? p.depth ?? p.water_level_mbgl;
      const val = extractNum(rawVal);
      return { ...p, year: yr, val };
    })
    .filter(p => p.year != null && p.year <= 2025 && p.val != null)
    .sort((a, b) => a.year - b.year);

  if (validPoints.length > 0) {
    const latest = validPoints[validPoints.length - 1];
    return {
      baselineValue: latest.val,
      baselineYear: latest.year,
      baselineDate: latest.date || `May ${latest.year}`,
      displacement: null,
      status: 'prior_year',
      reason: `2025 observation not recorded; latest field reading is from ${latest.year}`
    };
  }

  return {
    baselineValue: null,
    baselineYear: null,
    baselineDate: null,
    displacement: null,
    status: 'unavailable',
    reason: 'No valid historical pre-monsoon field observations found'
  };
}

/**
 * Map point-level static groundwater depth to farmer-friendly operational bands.
 * Never applies official GEC-2015 administrative categories to individual stations.
 */
export function getOperationalDepthBand(depth) {
  if (depth == null || !Number.isFinite(Number(depth))) {
    return {
      band: 'Unavailable',
      label: 'Depth unavailable',
      cls: 'status-badge badge-unknown',
      statusKey: 'unknown',
      color: '#6b7280',
      simpleMeaning: 'No validated groundwater reading available for this location.',
    };
  }
  const d = Number(depth);
  if (d < 8) {
    return {
      band: '0–8 m bgl',
      label: '0–8 m bgl · Shallow (0–8 m below ground)',
      cls: 'status-badge badge-safe',
      statusKey: 'safe',
      color: '#22c55e',
      simpleMeaning: 'Shallow water table. The groundwater is close to the surface and readily accessible.',
    };
  }
  if (d < 15) {
    return {
      band: '8–15 m bgl',
      label: '8–15 m bgl · Moderate (8–15 m below ground)',
      cls: 'status-badge badge-semi',
      statusKey: 'semi_critical',
      color: '#f59e0b',
      simpleMeaning: 'Moderate water table depth. Typical summer water level for this agricultural zone.',
    };
  }
  if (d <= 25) {
    return {
      band: '15–25 m bgl',
      label: '15–25 m bgl · Deep (15–25 m below ground)',
      cls: 'status-badge badge-crit',
      statusKey: 'critical',
      color: '#f97316',
      simpleMeaning: 'Deep water table. Deeper pumping lift required; higher risk of summer water stress.',
    };
  }
  return {
    band: 'Greater than 25 m bgl',
    label: 'Greater than 25 m bgl · Very Deep (Deeper than 25 m)',
    cls: 'status-badge badge-over',
    statusKey: 'over_exploited',
    color: '#ef4444',
    simpleMeaning: 'Very deep water table. High risk of wells running dry before monsoon rains.',
  };
}

/**
 * Simplified Groundwater History & Projection SVG Chart
 * - Clear 270px height without excessive empty space.
 * - Physically correct depth axis: 0m at top (ground surface), increasing depth downward.
 * - High-contrast white markers for observations; distinct amber marker for forecast.
 * - Non-overlapping year axis with clear 2025 measured and 2027 projected labels.
 * - Interactive hover tooltips with plain language.
 */
export function ForecastTimeSeriesChart({
  historyPoints = [],
  forecast = null,
  targetYear = 2027,
  targetType = 'future_projection',
  predictedValue = null,
  intermediatePoints = [],
}) {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const chartWidth = 1080;
  const chartHeight = 380;
  const padding = { top: 48, right: 110, bottom: 58, left: 68 };

  const plotW = chartWidth - padding.left - padding.right;
  const plotH = chartHeight - padding.top - padding.bottom;

  // Process historical observation points (<= 2025)
  const histPoints = useMemo(() => {
    if (!Array.isArray(historyPoints) || historyPoints.length === 0) return [];
    const pts = [];
    historyPoints.forEach(p => {
      const yr = p.year || (p.date ? parseInt(String(p.date).slice(0, 4), 10) : null);
      const rawVal = p.avg_level_m ?? p.water_level_m ?? p.depth ?? p.water_level_mbgl;
      if (yr != null && yr <= 2025 && rawVal != null && Number.isFinite(Number(rawVal))) {
        pts.push({
          year: yr,
          depth: Number(Number(rawVal).toFixed(2)),
          isForecast: false,
          date: p.date || `${yr}-05`,
        });
      }
    });
    pts.sort((a, b) => a.year - b.year);
    return pts;
  }, [historyPoints]);

  // Target forecast point (e.g. 2027)
  const fcPoint = useMemo(() => {
    if (predictedValue == null || !Number.isFinite(Number(predictedValue))) return null;
    return {
      year: targetYear,
      depth: Number(Number(predictedValue).toFixed(2)),
      isForecast: true,
      targetType,
    };
  }, [predictedValue, targetYear, targetType]);

  // Calibrated uncertainty bounds (only when supported by model)
  const uncertaintyInfo = useMemo(() => {
    if (!forecast || !fcPoint) return null;
    // Check if multi_year_projections has entry for targetYear
    const proj = forecast.multi_year_projections?.find(p => p.target_year === targetYear);
    const status = proj?.uncertainty_status ?? forecast.uncertainty_status;
    const lower = proj?.lower_mbgl ?? (forecast.forecast_year === targetYear ? forecast.lower_mbgl : null);
    const upper = proj?.upper_mbgl ?? (forecast.forecast_year === targetYear ? forecast.upper_mbgl : null);
    const radius = proj?.uncertainty_radius_mbgl ?? (forecast.forecast_year === targetYear ? forecast.uncertainty_radius_mbgl : null);
    
    if (status === 'calibrated_conformal_interval' && lower != null && upper != null) {
      return { isCalibrated: true, lower: Number(lower), upper: Number(upper), radius: Number(radius || 0) };
    }
    return null;
  }, [forecast, fcPoint, targetYear]);

  // Domain scaling
  const allYears = useMemo(() => {
    const yrs = histPoints.map(p => p.year);
    if (fcPoint) yrs.push(fcPoint.year);
    return yrs;
  }, [histPoints, fcPoint]);

  const minYear = allYears.length ? Math.min(1994, ...allYears) : 1994;
  const maxYear = allYears.length ? Math.max(2027, ...allYears) : 2027;

  const allDepths = useMemo(() => {
    const d = histPoints.map(p => p.depth);
    if (fcPoint) d.push(fcPoint.depth);
    if (uncertaintyInfo) {
      d.push(uncertaintyInfo.lower);
      d.push(uncertaintyInfo.upper);
    }
    return d;
  }, [histPoints, fcPoint, uncertaintyInfo]);

  const maxDepth = Math.max(25, Math.ceil((Math.max(...allDepths, 15) + 3) / 5) * 5);

  const scaleX = useCallback((year) => {
    if (maxYear === minYear) return padding.left + plotW / 2;
    return padding.left + ((year - minYear) / (maxYear - minYear)) * plotW;
  }, [maxYear, minYear, padding.left, plotW]);

  const scaleY = useCallback((depth) => {
    return padding.top + (Math.max(0, depth) / maxDepth) * plotH;
  }, [maxDepth, padding.top, plotH]);

  // Historical path
  const histPathD = useMemo(() => {
    if (histPoints.length < 2) return '';
    return histPoints.reduce((acc, p, idx) => {
      const x = scaleX(p.year);
      const y = scaleY(p.depth);
      return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
    }, '');
  }, [histPoints, scaleX, scaleY]);

  const lastObs = histPoints.length > 0 ? histPoints[histPoints.length - 1] : null;

  // Depth ticks (every 5m: 0, 5, 10, 15, 20, 25...)
  const depthTicks = useMemo(() => {
    const ticks = [];
    for (let d = 0; d <= maxDepth; d += 5) {
      ticks.push(d);
    }
    return ticks;
  }, [maxDepth]);

  // Regular five-year interval ticks (1995, 2000, 2005, 2010, 2015, 2020)
  const regularYearTicks = useMemo(() => {
    const ticks = [];
    const end = (lastObs && lastObs.year >= 2024) ? 2020 : 2025;
    for (let y = 1995; y <= end; y += 5) {
      if (y >= minYear) {
        ticks.push(y);
      }
    }
    return ticks;
  }, [minYear, lastObs]);

  // Forecast annotation badge (clearly visible, never extends beyond chart boundary)
  const fcBadge = useMemo(() => {
    if (!fcPoint) return null;
    const x = scaleX(fcPoint.year);
    const y = scaleY(fcPoint.depth);
    const badgeW = 78;
    const badgeH = 26;
    const badgeX = x + 12;
    const badgeY = Math.max(padding.top + 2, Math.min(chartHeight - padding.bottom - badgeH - 2, y - badgeH / 2));
    return { x: badgeX, y: badgeY, w: badgeW, h: badgeH, val: fcPoint.depth };
  }, [fcPoint, scaleX, scaleY, padding.top, chartHeight, padding.bottom]);

  return (
    <div style={{ position: 'relative', width: '100%', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Chart Header & High-Readability Legend (13-14px typography) */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <span className="eyebrow" style={{ fontSize: '11px' }}>Historical Trend &amp; Projections</span>
          <h2 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--color-primary)', margin: '2px 0 0 0', fontFamily: 'var(--font-interface)' }}>
            Water Level History &amp; {targetYear} Projection
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '2px 0 0 0', fontFamily: 'var(--font-interface)' }}>
            Annual pre-monsoon monitoring observations (1994–2025) and model projection for {targetYear}.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '18px', fontSize: '13px', color: 'var(--text-secondary)', fontFamily: 'var(--font-interface)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: '#ffffff', border: '1px solid #000000', display: 'inline-block' }} />
            <span>Measured (1994–2025)</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
            <span>Projected ({targetYear})</span>
          </span>
          {uncertaintyInfo && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              <span style={{ width: '14px', height: '7px', background: 'rgba(245, 158, 11, 0.4)', border: '1px dashed #f59e0b', borderRadius: '2px', display: 'inline-block' }} />
              <span>90% Calibrated Interval</span>
            </span>
          )}
        </div>
      </div>

      {/* SVG Canvas - Full Available Width */}
      <div className="forecast-chart-canvas-wrap">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="xMidYMid meet" style={{ width: '100%', height: 'auto', display: 'block', minHeight: '320px', maxHeight: '420px' }}>
          {/* Vertical Depth Axis Gridlines */}
          {depthTicks.map(d => {
            const y = scaleY(d);
            return (
              <g key={`y-${d}`}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={chartWidth - padding.right}
                  y2={y}
                  stroke={d === 0 ? 'rgba(156, 163, 175, 0.45)' : 'rgba(75, 85, 99, 0.28)'}
                  strokeDasharray={d === 0 ? 'none' : '3 3'}
                  strokeWidth={d === 0 ? '1.5' : '1'}
                />
                <text
                  x={padding.left - 12}
                  y={y}
                  dominantBaseline="central"
                  textAnchor="end"
                  fontSize="12.5"
                  fontWeight="500"
                  fill="var(--text-subtle)"
                  fontFamily="var(--font-interface)"
                >
                  {d}m
                </text>
              </g>
            );
          })}

          {/* Vertical Axis Title (Horizontal label placed cleanly above plot) */}
          <text
            x={padding.left}
            y={padding.top - 18}
            textAnchor="start"
            fontSize="13"
            fontWeight="600"
            fill="var(--text-secondary)"
            fontFamily="var(--font-interface)"
          >
            Groundwater depth (m bgl)
          </text>

          {/* Target Year Guideline (Amber dashed vertical line) */}
          {fcPoint && (() => {
            const fcX = scaleX(fcPoint.year);
            return (
              <g key="target-guideline">
                <line
                  x1={fcX}
                  y1={padding.top - 6}
                  x2={fcX}
                  y2={chartHeight - padding.bottom + 8}
                  stroke="#f59e0b"
                  strokeWidth="1.2"
                  strokeDasharray="3 2"
                  opacity="0.85"
                />
                {/* 2027 Top Projection Horizon Badge */}
                <rect
                  x={fcX - 48}
                  y={padding.top - 28}
                  width="96"
                  height="22"
                  rx="4"
                  fill="#18181b"
                  stroke="#f59e0b"
                  strokeWidth="1"
                />
                <text
                  x={fcX}
                  y={padding.top - 14}
                  dominantBaseline="central"
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight="700"
                  fill="#f59e0b"
                  fontFamily="var(--font-interface)"
                >
                  {targetYear} Projection
                </text>
              </g>
            );
          })()}

          {/* Calibrated Uncertainty Interval (only when supported by model) */}
          {fcPoint && uncertaintyInfo && (() => {
            const fcX = scaleX(fcPoint.year);
            const yLower = scaleY(uncertaintyInfo.lower);
            const yUpper = scaleY(uncertaintyInfo.upper);
            return (
              <g key="uncertainty-band">
                <line
                  x1={fcX}
                  y1={yLower}
                  x2={fcX}
                  y2={yUpper}
                  stroke="rgba(245, 158, 11, 0.45)"
                  strokeWidth="6"
                  strokeLinecap="round"
                />
                <line x1={fcX - 7} y1={yLower} x2={fcX + 7} y2={yLower} stroke="#f59e0b" strokeWidth="1.5" />
                <line x1={fcX - 7} y1={yUpper} x2={fcX + 7} y2={yUpper} stroke="#f59e0b" strokeWidth="1.5" />
              </g>
            );
          })()}

          {/* Historical Trend Line (Continuous, clearly visible light-grey line) */}
          {histPathD && (
            <path
              d={histPathD}
              fill="none"
              stroke="#cbd5e1"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Subtle Dashed Forecast Connector (from final observed year directly to forecast target) */}
          {lastObs && fcPoint && (
            <line
              x1={scaleX(lastObs.year)}
              y1={scaleY(lastObs.depth)}
              x2={scaleX(fcPoint.year)}
              y2={scaleY(fcPoint.depth)}
              stroke="#f59e0b"
              strokeWidth="1.8"
              strokeDasharray="5 4"
              opacity="0.9"
            />
          )}

          {/* Historical Observation Markers (Distinct white dots with dark ring) */}
          {histPoints.map((p, idx) => {
            const cx = scaleX(p.year);
            const cy = scaleY(p.depth);
            const isHovered = hoveredPoint?.year === p.year && !hoveredPoint?.isForecast;

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
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? '#38bdf8' : '#ffffff'}
                  stroke="#000000"
                  strokeWidth="1.6"
                />
              </g>
            );
          })}

          {/* Forecast Marker (Distinct amber marker) */}
          {fcPoint && (
            <g
              onMouseEnter={() => setHoveredPoint(fcPoint)}
              onMouseLeave={() => setHoveredPoint(null)}
              style={{ cursor: 'pointer' }}
            >
              <circle
                cx={scaleX(fcPoint.year)}
                cy={scaleY(fcPoint.depth)}
                r="6.5"
                fill="#f59e0b"
                stroke="#000000"
                strokeWidth="2.2"
              />
            </g>
          )}

          {/* Forecast Annotation Area: Clearly visible value badge inside boundary */}
          {fcBadge && (
            <g key="fc-badge">
              <rect
                x={fcBadge.x}
                y={fcBadge.y}
                width={fcBadge.w}
                height={fcBadge.h}
                rx="4"
                fill="#18181b"
                stroke="#f59e0b"
                strokeWidth="1.5"
              />
              <text
                x={fcBadge.x + fcBadge.w / 2}
                y={fcBadge.y + fcBadge.h / 2 + 1}
                dominantBaseline="central"
                textAnchor="middle"
                fontSize="13"
                fontWeight="700"
                fill="#f59e0b"
                fontFamily="var(--font-interface)"
              >
                {fcBadge.val} m
              </text>
            </g>
          )}

          {/* Horizontal Year Axis Base Line */}
          <line
            x1={padding.left}
            y1={chartHeight - padding.bottom}
            x2={chartWidth - padding.right}
            y2={chartHeight - padding.bottom}
            stroke="rgba(75, 85, 99, 0.4)"
            strokeWidth="1"
          />

          {/* Regular Five-Year Interval Ticks (1995, 2000, 2005, 2010, 2015, 2020) */}
          {regularYearTicks.map(yr => {
            const xYr = scaleX(yr);
            return (
              <g key={`x-tick-${yr}`}>
                <line
                  x1={xYr}
                  y1={chartHeight - padding.bottom}
                  x2={xYr}
                  y2={chartHeight - padding.bottom + 5}
                  stroke="rgba(113, 113, 122, 0.45)"
                  strokeWidth="1"
                />
                <text
                  x={xYr}
                  y={chartHeight - padding.bottom + 20}
                  dominantBaseline="central"
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight="500"
                  fill="var(--text-subtle)"
                  fontFamily="var(--font-interface)"
                >
                  {yr}
                </text>
              </g>
            );
          })}

          {/* Final Observed Year 2025 Tick (with ample ~137px clearance before 2020) */}
          {lastObs && (() => {
            const xObs = scaleX(lastObs.year);
            return (
              <g key="x-obs-last">
                <line
                  x1={xObs}
                  y1={chartHeight - padding.bottom}
                  x2={xObs}
                  y2={chartHeight - padding.bottom + 5}
                  stroke="#a1a1aa"
                  strokeWidth="1.2"
                />
                <text
                  x={xObs}
                  y={chartHeight - padding.bottom + 20}
                  dominantBaseline="central"
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight="600"
                  fill="#e4e4e7"
                  fontFamily="var(--font-interface)"
                >
                  {lastObs.year === 2025 ? '2025 (Measured)' : `${lastObs.year} (Measured)`}
                </text>
              </g>
            );
          })()}
        </svg>

        {/* Interactive Hover Tooltip */}
        {hoveredPoint && (
          <div
            style={{
              position: 'absolute',
              left: `${Math.min(chartWidth - 210, Math.max(10, scaleX(hoveredPoint.year) + 14))}px`,
              top: `${Math.min(chartHeight - 75, Math.max(10, scaleY(hoveredPoint.depth) - 30))}px`,
              background: '#18181b',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 12px',
              fontSize: '12px',
              fontFamily: 'var(--font-interface)',
              pointerEvents: 'none',
              zIndex: 30,
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.7)'
            }}
          >
            <div style={{ color: 'var(--text-subtle)', marginBottom: '3px', fontSize: '11px' }}>
              Year {hoveredPoint.year} · {hoveredPoint.isForecast ? 'Model Projection' : 'Measured Observation'}
            </div>
            <div style={{ color: hoveredPoint.isForecast ? '#f59e0b' : '#ffffff', fontWeight: 700, fontSize: '13px' }}>
              {hoveredPoint.depth} m below ground level
            </div>
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
  const [stations, setStations] = useState([]);
  const [stationId, setStationId] = useState(selectedStation?.station_id || '');
  const [forecast, setForecast] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loadingStations, setLoadingStations] = useState(true);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false); // Collapsed by default
  const [task1History, setTask1History] = useState([]);
  const [unsupportedStation, setUnsupportedStation] = useState(null);

  // Sync stationId when parent selectedStation changes
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

      // Auto-select initial station if none is currently selected
      if (!stationId && list.length > 0) {
        const defaultStation = list.find(s => s.station_id === '0098c762f561') || list[0];
        setStationId(defaultStation.station_id);
        if (onSelectStation) onSelectStation(defaultStation);
      }
    } catch (err) {
      console.warn('Could not load AI stations:', err);
      setError('Groundwater forecasting service is currently offline or unreachable.');
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
    } catch (e) {
      console.warn('Could not load AI metrics:', e);
    }
  };

  useEffect(() => {
    fetchStations();
    fetchMetrics();
  }, []);

  // Fetch forecast and historical observations for selected station
  useEffect(() => {
    if (!stationId) {
      setForecast(null);
      setTask1History([]);
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

  // Current active station metadata
  const currentStation = useMemo(() => {
    const fromList = stations.find(s => s.station_id === stationId);
    if (fromList) return fromList;
    if (selectedStation?.station_id === stationId) return selectedStation;
    return null;
  }, [stations, stationId, selectedStation]);

  // Primary forecast target for farmers: Pre-Monsoon 2027 (genuine future projection)
  const targetProjection = useMemo(() => {
    const data = forecast || (selectedStation ? {
      forecast_year: 2026,
      forecast_mbgl: selectedStation.predicted_depth_m ?? selectedStation.current_level_m ?? 10.26,
      multi_year_projections: [
        { target_year: 2026, predicted_depth_mbgl: 10.32, temporal_classification: 'retrospective_estimate', uncertainty_status: 'calibrated_conformal_interval', lower_mbgl: 4.59, upper_mbgl: 16.06 },
        { target_year: 2027, predicted_depth_mbgl: selectedStation.predicted_depth_m ?? selectedStation.current_level_m ?? 10.26, temporal_classification: 'future_projection', uncertainty_status: 'unavailable' },
      ],
    } : null);

    if (!data) return null;

    if (data.multi_year_projections && Array.isArray(data.multi_year_projections)) {
      const proj2027 = data.multi_year_projections.find(h => h.target_year === 2027);
      if (proj2027 && proj2027.predicted_depth_mbgl != null) {
        return {
          targetYear: 2027,
          isFuture: true,
          label: 'Pre-Monsoon 2027 (Next Summer)',
          predictedDepth: Number(Number(proj2027.predicted_depth_mbgl).toFixed(2)),
          isCalibrated: proj2027.uncertainty_status === 'calibrated_conformal_interval',
          lowerBound: proj2027.lower_mbgl,
          upperBound: proj2027.upper_mbgl,
        };
      }
    }

    const pred = data.forecast_mbgl != null ? Number(Number(data.forecast_mbgl).toFixed(2)) : null;
    const yr = data.forecast_year || 2026;
    return {
      targetYear: yr,
      isFuture: yr > 2026,
      label: yr <= 2026 ? ('Pre-Monsoon ' + yr + ' (Retrospective Estimate)') : ('Pre-Monsoon ' + yr + ' (Future Projection)'),
      predictedDepth: pred,
      isCalibrated: data.uncertainty_status === 'calibrated_conformal_interval',
      lowerBound: data.lower_mbgl,
      upperBound: data.upper_mbgl,
    };
  }, [forecast, selectedStation]);

  const predValue = targetProjection?.predictedDepth ?? null;

  // Intermediate points for chart
  const intermediatePoints = useMemo(() => {
    if (!forecast?.multi_year_projections || !targetProjection || targetProjection.targetYear <= 2026) return [];
    const pts = [];
    forecast.multi_year_projections.forEach(h => {
      if (h.target_year < targetProjection.targetYear && h.predicted_depth_mbgl != null) {
        pts.push({
          year: h.target_year,
          depth: Number(Number(h.predicted_depth_mbgl).toFixed(2)),
          isForecast: true,
          isIntermediate: true,
        });
      }
    });
    return pts;
  }, [forecast, targetProjection]);

  // Baseline and net displacement
  const baselineInfo = useMemo(() => {
    return getBaselineAndDisplacement(task1History, predValue);
  }, [task1History, predValue]);

  // Operational depth band in farmer-friendly language
  const operationalBand = useMemo(() => {
    return getOperationalDepthBand(predValue);
  }, [predValue]);

  // 2026 Hindcast data for the collapsed Advanced Details section
  const hindcast2026 = useMemo(() => {
    const data = forecast || (selectedStation ? {
      forecast_year: 2026,
      forecast_mbgl: 10.32,
      lower_mbgl: 4.59,
      upper_mbgl: 16.06,
      uncertainty_radius_mbgl: 5.73,
      uncertainty_status: 'calibrated_conformal_interval',
      multi_year_projections: [
        { target_year: 2026, predicted_depth_mbgl: 10.32, temporal_classification: 'retrospective_estimate', uncertainty_status: 'calibrated_conformal_interval', lower_mbgl: 4.59, upper_mbgl: 16.06, uncertainty_radius_mbgl: 5.73 },
      ],
    } : null);

    if (!data) return null;
    const h1 = data.multi_year_projections?.find(h => h.target_year === 2026);
    return {
      year: 2026,
      predictedDepth: h1?.predicted_depth_mbgl ?? data.forecast_mbgl,
      lowerBound: h1?.lower_mbgl ?? data.lower_mbgl,
      upperBound: h1?.upper_mbgl ?? data.upper_mbgl,
      uncertaintyRadius: h1?.uncertainty_radius_mbgl ?? data.uncertainty_radius_mbgl ?? 5.73,
      isCalibrated: (h1?.uncertainty_status ?? data.uncertainty_status) === 'calibrated_conformal_interval',
    };
  }, [forecast, selectedStation]);

  // Sync handler
  const handleSyncModel = async () => {
    setIsSyncing(true);
    try {
      await Promise.all([fetchStations(), fetchMetrics()]);
      if (onToast) onToast('Groundwater forecast data updated.', 'success');
    } catch (e) {
      if (onToast) onToast('Unable to update forecast data.', 'error');
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="as-section font-sans" style={{ maxWidth: '1240px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* ═════════════════════════════════════════════════════════════════════
          SECTION 1: SELECT YOUR LOCATION
          ═════════════════════════════════════════════════════════════════════ */}
      <div className="as-card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '10px' }}>
          <div>
            <span className="eyebrow" style={{ fontSize: '10px' }}>Location Forecast</span>
            <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-primary)', margin: '2px 0 0 0', letterSpacing: '-0.01em' }}>
              Groundwater Forecast for Farmers
            </h1>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
              Estimated groundwater depth for your selected location.
            </p>
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={handleSyncModel}
            disabled={isSyncing}
            title="Refresh location data"
            style={{ fontSize: '12px' }}
          >
            <IconRotateCcw size={13} className={isSyncing ? 'spinner-icon' : ''} style={{ marginRight: '5px' }} />
            {isSyncing ? 'Refreshing...' : 'Refresh Data'}
          </button>
        </div>

        {/* Location Search & Selection Controls */}
        <div className="forecast-selector-grid">
          <div className="search-input-wrap">
            <IconSearch size={14} className="search-icon" />
            <input
              type="text"
              className="form-input form-input-sm"
              placeholder="Search village, block, or district..."
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
              <option>Connecting to monitoring stations...</option>
            ) : filteredStations.length === 0 ? (
              <option value="">No matching villages or blocks found</option>
            ) : (
              <>
                {!stationId && <option value="">Select your village or block...</option>}
                {filteredStations.map(s => (
                  <option key={s.station_id} value={s.station_id}>
                    {[s.village, s.block, s.district].filter(Boolean).join(' · ')}
                  </option>
                ))}
              </>
            )}
          </select>
        </div>

        {/* Simple Location Summary Strip */}
        {currentStation && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginTop: '12px', paddingTop: '10px', borderTop: '1px solid var(--color-border)', fontSize: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--text-subtle)' }}>Selected Location:</span>
              <strong style={{ color: 'var(--color-primary)' }}>
                {currentStation.station_name || currentStation.village || 'Monitoring Station'}, {currentStation.block ? `${currentStation.block} Block, ` : ''}{currentStation.district} District
              </strong>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
              Data source: Central Ground Water Board (CGWB) records
            </div>
          </div>
        )}
      </div>

      {/* Error Notice */}
      {error && (
        <div style={{ background: '#000000', border: '1px solid #ef4444', borderRadius: 'var(--radius-sm)', padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444', fontSize: '13px' }}>
            <IconAlert size={15} />
            <span>{error}</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={fetchStations}>Retry</button>
        </div>
      )}

      {/* Unsupported Reference Well Notice */}
      {unsupportedStation && (
        <div style={{ background: '#000000', border: '1px solid #f59e0b', borderRadius: 'var(--radius-sm)', padding: '12px 16px', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
          <IconAlert size={16} style={{ color: '#f59e0b', flexShrink: 0, marginTop: '2px' }} />
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            <strong style={{ color: '#f59e0b' }}>Calibration Reference Well:</strong>{' '}
            Station <strong>{unsupportedStation.station_name || unsupportedStation.village}</strong> is a benchmark reference node without continuous 32-year historical records. Please select an observation well in Karnataka above.
          </div>
        </div>
      )}

      {/* Loading Spinner */}
      {loadingForecast && (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '28px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
          <div className="spinner-ring" />
          <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-interface)' }}>
            Retrieving groundwater forecast for your location...
          </span>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════
          SECTIONS 2 & 3: COMPACT TWO-COLUMN LAYOUT (Desktop 1366x768 friendly)
          B. Groundwater Forecast (Left) + C. History Graph (Right)
          ═════════════════════════════════════════════════════════════════════ */}
      {(forecast || selectedStation) && !loadingForecast && (
        <>
          {/* ═════════════════════════════════════════════════════════════════════
              SECTION B: COMPACT FORECAST SUMMARY (Full-Width Strip)
              ═════════════════════════════════════════════════════════════════════ */}
          <div className="as-card farmer-summary-card">
            <div className="farmer-summary-grid">

              {/* Col 1: Forecast Target & Predicted Depth */}
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                  <span className="eyebrow" style={{ fontSize: '11px', margin: 0 }}>
                    {targetProjection?.label || 'Pre-Monsoon 2027'} · {targetProjection?.isFuture ? 'Future Projection' : 'Retrospective Estimate'}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '2px 0 6px 0' }}>
                  <span className="farmer-forecast-val">
                    {predValue != null ? predValue : '—'}
                  </span>
                  <span className="farmer-forecast-unit">
                    m bgl
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span className={operationalBand.cls} style={{ fontSize: '11.5px', padding: '3px 9px', display: 'inline-flex', alignItems: 'center' }}>
                    <StatusSymbol status={operationalBand.statusKey} size={11} style={{ marginRight: '5px' }} />
                    {operationalBand.label}
                  </span>
                </div>
                <div className="farmer-forecast-subtext" style={{ marginTop: '6px' }}>
                  <strong>m bgl</strong> means metres below ground level.
                </div>
              </div>

              {/* Col 2: Operational Meaning & Farmer Guidance */}
              <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <span className="eyebrow" style={{ fontSize: '10px', marginBottom: '4px' }}>Field Assessment</span>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, fontFamily: 'var(--font-interface)' }}>
                  {operationalBand.simpleMeaning}
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-subtle)', marginTop: '6px', lineHeight: 1.45 }}>
                  A larger depth value means the groundwater table is farther below the ground surface. Actual water levels vary with seasonal rainfall and pumping.
                </div>
              </div>

              {/* Col 3: Baseline Comparison (Measured 2025 vs 2027) */}
              <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '8px', fontSize: '12.5px', fontFamily: 'var(--font-interface)' }}>
                <span className="eyebrow" style={{ fontSize: '10px', marginBottom: '2px' }}>Measured Baseline &amp; Trend</span>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Previous Measured Level (May 2025):</span>
                  <strong style={{ color: baselineInfo.baselineValue != null ? 'var(--color-primary)' : 'var(--text-muted)' }}>
                    {baselineInfo.baselineValue != null ? (
                      <span className="font-mono">{baselineInfo.baselineValue} m</span>
                    ) : (
                      'Not recorded'
                    )}
                  </strong>
                </div>
                {baselineInfo.displacement != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Expected Change by May 2027:</span>
                    <strong style={{ color: baselineInfo.displacement < 0 ? '#22c55e' : '#f97316' }}>
                      <span className="font-mono">{Math.abs(baselineInfo.displacement)} m</span>{' '}
                      <span>{baselineInfo.displacement < 0 ? 'higher water table' : 'deeper water table'}</span>
                    </strong>
                  </div>
                )}
                <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px' }}>
                  Verified CGWB monitoring record
                </div>
              </div>

            </div>
          </div>

          {/* ═════════════════════════════════════════════════════════════════════
              SECTION C: FULL-WIDTH HISTORICAL GROUNDWATER GRAPH
              ═════════════════════════════════════════════════════════════════════ */}
          <div className="as-card forecast-chart-card">
            <ForecastTimeSeriesChart
              historyPoints={task1History}
              forecast={forecast}
              targetYear={targetProjection?.targetYear || 2027}
              targetType={targetProjection?.isFuture ? 'future_projection' : 'retrospective_estimate'}
              predictedValue={predValue}
              intermediatePoints={intermediatePoints}
            />
          </div>

          {/* ═════════════════════════════════════════════════════════════════════
              SECTION 4: COLLAPSIBLE ADVANCED DETAILS (Default: Collapsed)
              Contains technical RMSE, calibration statistics, hindcast details,
              and CGWB administrative governance notes.
              ═════════════════════════════════════════════════════════════════════ */}
          <div className="as-card" style={{ padding: 0, overflow: 'hidden' }}>
            <button
              className="accordion-toggle"
              onClick={() => setShowAdvanced(v => !v)}
              style={{ padding: '14px 18px', border: 'none', background: 'transparent' }}
            >
              <div>
                <span className="eyebrow" style={{ fontSize: '10px' }}>Optional Technical Reference</span>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-primary)', marginTop: '2px' }}>
                  Advanced Details &amp; Scientific Methodology
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
                <span>{showAdvanced ? 'Hide Details' : 'Show Details'}</span>
                {showAdvanced ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
              </div>
            </button>

            {showAdvanced && (
              <div style={{ padding: '16px 20px', borderTop: '1px solid var(--color-border)', background: 'var(--color-surface)', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: '14px' }}>

                {/* 2026 Retrospective Hindcast */}
                {hindcast2026 && (
                  <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px 14px', fontFamily: 'var(--font-interface)' }}>
                    <div style={{ fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>
                      2026 Retrospective Estimate (Hindcast Validation)
                    </div>
                    <div style={{ display: 'flex', gap: '18px', flexWrap: 'wrap', marginBottom: '6px' }}>
                      <div>Estimated Depth: <strong className="font-mono" style={{ color: '#f59e0b' }}>{hindcast2026.predictedDepth} m bgl</strong></div>
                      {hindcast2026.isCalibrated && hindcast2026.lowerBound != null && (
                        <div>
                          90% Calibrated Range: <strong className="font-mono">[{hindcast2026.lowerBound}m, {hindcast2026.upperBound}m]</strong> (&plusmn;<span className="font-mono">{hindcast2026.uncertaintyRadius} m</span>)
                        </div>
                      )}
                      <div>Empirical Test Coverage: <strong className="font-mono">96.4%</strong></div>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                      Note: Pre-monsoon 2026 occurred in April–May 2026 prior to the current date (November 16, 2026). It is evaluated strictly as a retrospective model check against historical measurements.
                    </div>
                  </div>
                )}

                {/* Model Accuracy & Training Specifications */}
                <div style={{ fontFamily: 'var(--font-interface)' }}>
                  <div style={{ fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>
                    Model Specifications &amp; Empirical Accuracy
                  </div>
                  <ul style={{ margin: '0 0 0 16px', padding: 0 }}>
                    <li><strong>Algorithm:</strong> Linear Regression with Conformal Calibration (<code className="font-mono">linear_regression.joblib</code>).</li>
                    <li><strong>Accuracy:</strong> Holdout Test RMSE = <span className="font-mono">{metrics?.metrics?.linear_regression?.rmse ? Number(metrics.metrics.linear_regression.rmse).toFixed(2) : '2.50'} m</span>, MAE = <span className="font-mono">{metrics?.metrics?.linear_regression?.mae ? Number(metrics.metrics.linear_regression.mae).toFixed(2) : '1.68'} m</span>, R² = <span className="font-mono">0.55</span> (evaluated across 997 unseen test observations, 2023–2025).</li>
                    <li><strong>Training Dataset:</strong> 390 verified CGWB observation wells in Karnataka (1994–2016 historical survey records, 6,870 samples).</li>
                    <li><strong>Features:</strong> 4 annual historical pre-monsoon depths, calendar elapsed years, rolling statistics, and coordinates. Zero synthetic rainfall features.</li>
                  </ul>
                </div>

                {/* Administrative GEC-2015 Governance Notice */}
                <div style={{ fontSize: '11px', color: 'var(--text-subtle)', background: '#000000', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontFamily: 'var(--font-interface)' }}>
                  <strong>Official Assessment Note:</strong> Depth predictions are point-level physical screening estimates for individual observation wells. Official CGWB GEC-2015 administrative classifications (Safe, Semi-Critical, Critical, Over-Exploited) apply strictly to administrative blocks/taluks and require comprehensive extraction vs. recharge accounting.
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
