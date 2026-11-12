import React, { useState, useEffect } from 'react';
import './TaskDetail.css';

/* ── Inline SVG Icon helpers ── */
const Icon = ({ children, size = 16, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    style={{ display: 'inline-block', verticalAlign: '-2px', flexShrink: 0 }}
    {...props}
  >
    {children}
  </svg>
);
const IconWater = (p) => <Icon {...p}><path d="M8 2C8 2 3 8 3 10.5C3 13 5.2 15 8 15C10.8 15 13 13 13 10.5C13 8 8 2 8 2z"/></Icon>;
const IconClock = (p) => <Icon {...p}><circle cx="8" cy="8" r="6.5"/><polyline points="8,4 8,8 11,9.5"/></Icon>;
const IconCalendar = (p) => <Icon {...p}><rect x="2" y="3" width="12" height="12" rx="1"/><line x1="2" y1="7" x2="14" y2="7"/><line x1="5" y1="1" x2="5" y2="4"/><line x1="11" y1="1" x2="11" y2="4"/></Icon>;
const IconWave = (p) => <Icon {...p}><path d="M1 8C3 5 5 5 7 8C9 11 11 11 13 8C14 6.5 15 6 15 6"/></Icon>;
const IconAlert = (p) => <Icon {...p}><path d="M8 1L1 13h14L8 1z"/><path d="M8 6v3M8 11v.5" strokeWidth="1.6"/></Icon>;
const IconChart = (p) => <Icon {...p}><rect x="2" y="9" width="3" height="6"/><rect x="6.5" y="5" width="3" height="10"/><rect x="11" y="1" width="3" height="14"/></Icon>;
const IconTrend = (p) => <Icon {...p}><polyline points="1,13 5,8 8,11 11,5 15,9"/></Icon>;
const IconTarget = (p) => <Icon {...p}><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="3"/><circle cx="8" cy="8" r="0.5" fill="currentColor"/></Icon>;
const IconSearch = (p) => <Icon {...p}><circle cx="7" cy="7" r="4.5"/><line x1="10.5" y1="10.5" x2="14" y2="14"/></Icon>;
const IconClipboard = (p) => <Icon {...p}><rect x="2" y="1" width="12" height="14" rx="1"/><line x1="5" y1="5" x2="11" y2="5"/><line x1="5" y1="8" x2="11" y2="8"/><line x1="5" y1="11" x2="9" y2="11"/></Icon>;
const IconPin = (p) => <Icon {...p}><path d="M8 1C5 1 3 3.5 3 6C3 9.5 8 15 8 15C8 15 13 9.5 13 6C13 3.5 11 1 8 1z"/><circle cx="8" cy="6" r="2"/></Icon>;
const IconRock = (p) => <Icon {...p}><path d="M3 14L1 9L5 4L8 2L11 4L15 9L13 14Z"/></Icon>;
const IconRain = (p) => <Icon {...p}><path d="M12 8a4 4 0 10-8 0 4 4 0 008 0z"/><path d="M4 11l-1 3M8 11l-1 4M12 11l-1 3"/></Icon>;
const IconLightning = (p) => <Icon {...p}><polyline points="9,1 5,8 8,8 7,15 12,7 9,7"/></Icon>;
const IconWeather = (p) => <Icon {...p}><path d="M5 10A4 4 0 119 5a3 3 0 013 5H5z"/><path d="M4 13l-1 2M8 13v3M12 13l1 2"/></Icon>;
const IconHourglass = (p) => <Icon {...p}><path d="M4 1h8M4 15h8M5 1v3l3 4-3 4v3M11 1v3L8 8l3 4v3"/></Icon>;
const IconFolder = (p) => <Icon {...p}><path d="M2 4h4l2-2h6v12H2V4z"/></Icon>;
const IconBuilding = (p) => <Icon {...p}><path d="M8 1L2 5v1h12V5L8 1z"/><line x1="3" y1="7" x2="3" y2="13"/><line x1="6" y1="7" x2="6" y2="13"/><line x1="10" y1="7" x2="10" y2="13"/><line x1="13" y1="7" x2="13" y2="13"/><line x1="1" y1="13" x2="15" y2="13"/></Icon>;
const IconCheck = (p) => <Icon {...p}><circle cx="8" cy="8" r="6.5"/><polyline points="5,8 7.5,10.5 11,5.5"/></Icon>;
const IconSiren = (p) => <Icon {...p}><circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M8 4v5M8 11v.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></Icon>;
const IconArrowLeft = (p) => <Icon {...p}><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></Icon>;

const API_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API = `${API_BASE}/api`;

function PieChart({ slices, size = 120 }) {
  const r = size / 2 - 8, cx = size / 2, cy = size / 2;
  let cum = 0;
  const total = slices.reduce((s, sl) => s + sl.value, 0);
  if (!total) return null;
  const paths = slices.map((sl, i) => {
    const s = (cum / total) * 2 * Math.PI - Math.PI / 2;
    cum += sl.value;
    const e = (cum / total) * 2 * Math.PI - Math.PI / 2;
    const x1 = cx + r * Math.cos(s), y1 = cy + r * Math.sin(s);
    const x2 = cx + r * Math.cos(e), y2 = cy + r * Math.sin(e);
    const large = e - s > Math.PI ? 1 : 0;
    return (
      <path
        key={i}
        d={`M${cx} ${cy} L${x1} ${y1} A${r} ${r} 0 ${large} 1 ${x2} ${y2}Z`}
        fill={sl.color}
        opacity={0.92}
        stroke="#ffffff"
        strokeWidth={2}
      />
    );
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r + 4} fill="#f1f5f9" />
      {paths}
      <circle cx={cx} cy={cy} r={r * 0.48} fill="#ffffff" stroke="#e2e8f0" strokeWidth={1} />
    </svg>
  );
}

function LineChart({ data, xKey, yKey, color = '#0284c7', label = '', height = 180 }) {
  if (!data || data.length < 2) return <div className="chart-empty">Insufficient temporal readings to plot trend</div>;
  const vals = data.map(d => parseFloat(d[yKey]) || 0);
  const labels = data.map(d => d[xKey]);
  const min = Math.min(...vals), max = Math.max(...vals), range = max - min || 1;
  const W = 520, H = height, pad = { t: 20, b: 32, l: 50, r: 16 };
  const iW = W - pad.l - pad.r, iH = H - pad.t - pad.b;
  const pts = vals.map((v, i) => [pad.l + (i / (vals.length - 1)) * iW, pad.t + (1 - (v - min) / range) * iH]);
  const polyline = pts.map(p => p.join(',')).join(' ');
  const area = `${pad.l},${pad.t + iH} ${polyline} ${pad.l + iW},${pad.t + iH}`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(t => ({ y: pad.t + (1 - t) * iH, val: (min + t * range).toFixed(2) }));
  const step = Math.max(1, Math.floor(labels.length / 6));
  const xLabels = labels.filter((_, i) => i % step === 0 || i === labels.length - 1);
  const gId = `lg${color.replace(/[^a-zA-Z0-9]/g, '')}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="line-chart">
      <defs>
        <linearGradient id={gId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.12" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={pad.l} y1={t.y} x2={pad.l + iW} y2={t.y} stroke="#e2e8f0" strokeWidth={1} strokeDasharray="3,4" />
          <text x={pad.l - 8} y={t.y + 3.5} textAnchor="end" fill="#64748b" fontSize="9.5" fontFamily="'IBM Plex Mono', monospace">{t.val}</text>
        </g>
      ))}
      <polygon points={area} fill={`url(#${gId})`} />
      <polyline points={polyline} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={2.5} fill="#ffffff" stroke={color} strokeWidth={1.5} />
      ))}
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={4.5} fill={color} stroke="#ffffff" strokeWidth={2} />
      {xLabels.map((lbl, i) => {
        const idx = labels.indexOf(lbl);
        const x = pad.l + (idx / (labels.length - 1)) * iW;
        return <text key={i} x={x} y={H - 10} textAnchor="middle" fill="#64748b" fontSize="8.5" fontFamily="'IBM Plex Mono', monospace">{String(lbl).slice(-5)}</text>;
      })}
      <line x1={pad.l} y1={pad.t} x2={pad.l} y2={pad.t + iH} stroke="#cbd5e1" strokeWidth={1} />
      <line x1={pad.l} y1={pad.t + iH} x2={pad.l + iW} y2={pad.t + iH} stroke="#cbd5e1" strokeWidth={1} />
      {label && <text x={pad.l + iW / 2} y={pad.t - 7} textAnchor="middle" fill="#475569" fontSize="9.5" fontWeight="500" fontFamily="'Inter', sans-serif">{label}</text>}
    </svg>
  );
}

function BarChart({ data, xKey, yKey, color = '#0284c7', height = 160 }) {
  if (!data || !data.length) return <div className="chart-empty">No comparative readings available</div>;
  const vals = data.map(d => parseFloat(d[yKey]) || 0);
  const labels = data.map(d => d[xKey]);
  const max = Math.max(...vals, 0.1);
  const W = 500, H = height, pad = { t: 14, b: 30, l: 45, r: 12 };
  const iW = W - pad.l - pad.r, iH = H - pad.t - pad.b;
  const bw = Math.max(8, Math.min(48, iW / vals.length - 10));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="bar-chart">
      {vals.map((v, i) => {
        const x = pad.l + (i / vals.length) * iW + (iW / vals.length - bw) / 2;
        const bh = (v / max) * iH, y = pad.t + iH - bh;
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={bh} fill={color} opacity={0.88} rx={3} />
            <text x={x + bw / 2} y={H - 10} textAnchor="middle" fill="#64748b" fontSize="9" fontFamily="'Inter', sans-serif">{String(labels[i])}</text>
          </g>
        );
      })}
      <line x1={pad.l} y1={pad.t + iH} x2={pad.l + iW} y2={pad.t + iH} stroke="#cbd5e1" strokeWidth={1} />
    </svg>
  );
}

function Gauge({ value, max = 100, color = '#0284c7', label = '' }) {
  const pct = Math.min(1, Math.max(0, (value || 0) / (max || 100)));
  const angle = pct * Math.PI;
  const r = 70, cx = 100, cy = 90;
  const endX = cx + r * Math.cos(Math.PI - angle);
  const endY = cy - r * Math.sin(angle);
  const displayVal = typeof value === 'number' ? (value > 999 ? value.toFixed(0) : value.toFixed(1)) : '—';
  return (
    <svg viewBox="0 0 200 110" className="gauge-chart">
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`} fill="none" stroke="#f1f5f9" strokeWidth={12} strokeLinecap="round" />
      {pct > 0 && (
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${endX} ${endY}`} fill="none" stroke={color} strokeWidth={12} strokeLinecap="round" />
      )}
      <text x={cx} y={cy - 12} textAnchor="middle" fill="#0f172a" fontSize="22" fontWeight="700" fontFamily="'Inter', sans-serif" className="tabular-nums">{displayVal}</text>
      <text x={cx} y={cy + 8} textAnchor="middle" fill="#64748b" fontSize="9" fontFamily="'IBM Plex Mono', monospace">{label}</text>
    </svg>
  );
}

function StatCard({ icon, label, value, unit, color = '#0284c7', sub }) {
  return (
    <div className="stat-card">
      <div className="sc-header">
        <span className="sc-label">{label}</span>
        <span className="sc-icon">{icon}</span>
      </div>
      <div className="sc-val tabular-nums" style={{ color }}>
        {value}
        {unit && <span className="sc-unit">{unit}</span>}
      </div>
      {sub && <div className="sc-sub">{sub}</div>}
    </div>
  );
}

const STATUS = {
  safe:           { label: 'Safe',           color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' },
  semi_critical:  { label: 'Semi-Critical',  color: '#d97706', bg: '#fffbeb', border: '#fde68a' },
  critical:       { label: 'Critical',       color: '#ea580c', bg: '#fff7ed', border: '#fed7aa' },
  over_exploited: { label: 'Over-Exploited', color: '#dc2626', bg: '#fef2f2', border: '#fecaca' },
  unknown:        { label: 'Unknown',        color: '#64748b', bg: '#f1f5f9', border: '#cbd5e1' },
};

// ══════════════════════════════════════════════════════════════
// TASK 1 DETAIL: Fluctuation Analysis
// ══════════════════════════════════════════════════════════════
export function Task1Detail({ station, onBack }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [hours, setHours]     = useState(720);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/task1/${station.station_id}?hours=${hours}`)
      .then(r => r.json())
      .then(d => { setData(d.error ? null : d); setLoading(false); })
      .catch(() => { setData(null); setLoading(false); });
  }, [station.station_id, hours]);

  const isRecovering = data?.trend_direction === 'falling';
  const trendColor = isRecovering ? '#16a34a' : data?.trend_direction === 'rising' ? '#dc2626' : '#d97706';
  const anomalyTypes = (data?.anomalies || []).reduce((acc, a) => ({ ...acc, [a.type]: (acc[a.type] || 0) + 1 }), {});

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>
          <IconArrowLeft size={14} style={{ marginRight: '6px' }} /> Return to Well Dossier
        </button>
        <div className="tdp-title-row">
          <div className="tdp-tag task1-tag">Task 1</div>
          <div>
            <h1 className="tdp-title">Water Level Fluctuation &amp; Derivative Analysis</h1>
            <p className="tdp-sub">{station.station_name || station.station_id} · {station.district}, {station.state} · Transducer Frequency: Continuous Telemetry</p>
          </div>
        </div>
      </div>

      <div className="window-selector">
        <span className="ws-label">Analysis window:</span>
        {[
          { label: '24 Hours', val: 24 },
          { label: '7 Days', val: 168 },
          { label: '30 Days', val: 720 },
          { label: '1 Year', val: 8760 },
        ].map(w => (
          <button
            key={w.val}
            className={`ws-btn ${hours === w.val ? 'active' : ''}`}
            onClick={() => setHours(w.val)}
          >
            {w.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="tdp-loading">
          <div className="tdp-spinner" />
          <span>Executing first-derivative fluctuation analysis and moving average filter...</span>
        </div>
      ) : !data ? (
        <div className="tdp-empty">
          No telemetry readings available for this station in the selected window.
          <br />Try selecting a wider observation interval above.
        </div>
      ) : (
        <>
          <div className="kpi-row">
            <StatCard
              icon={<IconWater size={15} />}
              label="Static Water Depth"
              value={data.current_level_m != null ? Number(data.current_level_m).toFixed(2) : '—'}
              unit="m bgl"
              color="#0f172a"
              sub={data.as_of ? `Synced: ${data.as_of.slice(0, 10)}` : 'Continuous series'}
            />
            <StatCard
              icon={<IconClock size={15} />}
              label="Hourly Velocity"
              value={`${data.rate_per_hour > 0 ? '+' : ''}${(data.rate_per_hour || 0).toFixed(4)}`}
              unit="m/hr"
              color={data.rate_per_hour > 0 ? '#dc2626' : '#16a34a'}
              sub={data.rate_per_hour > 0 ? 'Water table deepening' : 'Water table recovering'}
            />
            <StatCard
              icon={<IconCalendar size={15} />}
              label="Daily Rate"
              value={`${data.rate_per_day > 0 ? '+' : ''}${(data.rate_per_day || 0).toFixed(3)}`}
              unit="m/day"
              color={data.rate_per_day > 0 ? '#dc2626' : '#16a34a'}
              sub="First-derivative metric"
            />
            <StatCard
              icon={<IconCalendar size={15} />}
              label="Weekly Rate"
              value={`${data.rate_per_week > 0 ? '+' : ''}${(data.rate_per_week || 0).toFixed(3)}`}
              unit="m/wk"
              color={data.rate_per_week > 0 ? '#dc2626' : '#16a34a'}
              sub="Rolling 7-day velocity"
            />
            <StatCard
              icon={<IconWave size={15} />}
              label="Hydrological Phase"
              value={data.seasonal_phase ? data.seasonal_phase.replace(/_/g, ' ') : '—'}
              unit=""
              color="#0d9488"
              sub="Seasonal baseline"
            />
            <StatCard
              icon={<IconAlert size={15} />}
              label="Active Anomalies"
              value={data.anomalies?.length ?? 0}
              unit=""
              color={data.anomalies?.length > 0 ? '#dc2626' : '#16a34a'}
              sub="3σ statistical breaches"
            />
          </div>

          <div className="charts-row">
            <div className="chart-card wide">
              <div className="cc-title"><IconTrend style={{ marginRight: '6px' }} /> 30-Day Centered Moving Average Trend</div>
              <div className="cc-sub">Daily average static water level (metres below ground level) filtered for high-frequency transducer noise</div>
              <LineChart data={data.moving_average || []} xKey="date" yKey="avg_level_m" color="#0284c7" label="Water Level (m bgl)" height={210} />
            </div>

            <div className="chart-card">
              <div className="cc-title"><IconTarget style={{ marginRight: '6px' }} /> Hydrograph Trajectory</div>
              <Gauge value={Math.abs(data.trend_magnitude || 0)} max={5} color={trendColor} label="7-day change (m)" />
              <div className="trend-pill" style={{ background: `${trendColor}12`, color: trendColor, borderColor: `${trendColor}35` }}>
                {data.trend_direction === 'rising' && 'Deepening — water table drawdown'}
                {data.trend_direction === 'falling' && 'Recovering — static level rising'}
                {data.trend_direction === 'stable' && 'Equilibrium — stable head'}
                {(!data.trend_direction || data.trend_direction === 'unknown') && 'Telemetry baseline pending'}
              </div>
              <div
                className="status-pill-large"
                style={{
                  background: data.status === 'recovering' ? '#f0fdf4' : '#fef2f2',
                  color: data.status === 'recovering' ? '#166534' : '#991b1b',
                  borderColor: data.status === 'recovering' ? '#bbf7d0' : '#fecaca',
                }}
              >
                {(data.status || 'unknown').replace(/_/g, ' ').toUpperCase()}
              </div>
            </div>
          </div>

          <div className="charts-row">
            <div className="chart-card">
              <div className="cc-title"><IconChart style={{ marginRight: '6px' }} /> Rate-of-Change Velocity Comparison</div>
              <BarChart
                data={[
                  { period: 'Hourly', rate: Math.abs(data.rate_per_hour || 0) },
                  { period: 'Daily',  rate: Math.abs(data.rate_per_day || 0) },
                  { period: 'Weekly', rate: Math.abs(data.rate_per_week || 0) }
                ]}
                xKey="period"
                yKey="rate"
                color="#0284c7"
                height={150}
              />
            </div>

            <div className="chart-card">
              <div className="cc-title"><IconSearch style={{ marginRight: '6px' }} /> Anomaly Distribution</div>
              {data.anomalies?.length > 0 ? (
                <>
                  <PieChart
                    slices={[
                      { label: 'Sudden Drop', value: anomalyTypes.sudden_drop || 0, color: '#dc2626' },
                      { label: 'Statistical 3σ', value: anomalyTypes.statistical || 0, color: '#d97706' },
                    ]}
                    size={130}
                  />
                  <div className="pie-legend">
                    <div className="pl-item"><span style={{ background: '#dc2626' }} /> Sudden Drawdown ({anomalyTypes.sudden_drop || 0})</div>
                    <div className="pl-item"><span style={{ background: '#d97706' }} /> Statistical 3σ ({anomalyTypes.statistical || 0})</div>
                  </div>
                </>
              ) : (
                <div className="no-anomaly">
                  <IconCheck size={16} style={{ marginRight: '6px', color: '#16a34a' }} />
                  <span>All readings nominal within 3σ baseline</span>
                </div>
              )}
            </div>

            <div className="chart-card">
              <div className="cc-title"><IconClipboard style={{ marginRight: '6px' }} /> Analytical Summary</div>
              <div className="summary-stats">
                <div className="ss-item">
                  <span className="ss-val font-mono">{(data.total_readings || 0).toLocaleString()}</span>
                  <span className="ss-lbl">Recorded telemetry steps</span>
                </div>
                <div className="ss-item">
                  <span className="ss-val font-mono">{(data.trend_magnitude || 0).toFixed(3)} m</span>
                  <span className="ss-lbl">7-day net displacement</span>
                </div>
                <div className="ss-item">
                  <span className="ss-val">{(data.seasonal_phase || '—').replace(/_/g, ' ')}</span>
                  <span className="ss-lbl">Seasonal cycle</span>
                </div>
              </div>
              <div className="summary-text">{data.summary || 'Analytical computation concluded.'}</div>
            </div>
          </div>

          {data.anomalies?.length > 0 && (
            <div className="anomaly-table">
              <div className="at-title"><IconAlert style={{ marginRight: '6px', color: '#dc2626' }} /> Telemetry Anomaly Log</div>
              <div className="at-grid">
                <div className="at-head">Timestamp</div>
                <div className="at-head">Type</div>
                <div className="at-head">Displacement</div>
                <div className="at-head">Anomaly Trigger Rule</div>
                {data.anomalies.map((a, i) => (
                  <React.Fragment key={i}>
                    <div className="at-cell mono">{a.timestamp ? a.timestamp.slice(0, 16) : '—'}</div>
                    <div className="at-cell">
                      <span className={`at-type ${a.type}`}>{(a.type || '').replace(/_/g, ' ')}</span>
                    </div>
                    <div className="at-cell mono">{(a.magnitude_m || 0).toFixed(3)} m</div>
                    <div className="at-cell text2">{a.reason}</div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TASK 2 DETAIL: Dynamic Recharge Estimation (WTF Method)
// ══════════════════════════════════════════════════════════════
export function Task2Detail({ station, onBack }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/task2/${station.station_id}?days=365`)
      .then(r => r.json())
      .then(d => { setData(d.error ? null : d); setLoading(false); })
      .catch(() => { setData(null); setLoading(false); });
  }, [station.station_id]);

  const zoneColors = {
    good_recharge:       '#16a34a',
    moderate_recharge:   '#d97706',
    stressed:            '#ea580c',
    critically_stressed: '#dc2626',
    insufficient_data:   '#64748b'
  };
  const zoneColor = zoneColors[data?.zone_status] || '#64748b';

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>
          <IconArrowLeft size={14} style={{ marginRight: '6px' }} /> Return to Well Dossier
        </button>
        <div className="tdp-title-row">
          <div className="tdp-tag task2-tag">Task 2</div>
          <div>
            <h1 className="tdp-title">Dynamic Groundwater Recharge Estimation (WTF Method)</h1>
            <p className="tdp-sub">{station.station_name || station.station_id} · {station.district}, {station.state} · Correlation: IMD Rainfall &amp; Water Table Recovery</p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="tdp-loading">
          <div className="tdp-spinner" />
          <span>Evaluating precipitation events, hydraulic lag, and aquifer specific yield...</span>
        </div>
      ) : !data ? (
        <div className="tdp-empty">
          No precipitation correlation data available for this station.
          <br />Task 2 requires synchronized IMD rainfall observations and water table levels.
        </div>
      ) : (
        <>
          <div className="kpi-row">
            <StatCard
              icon={<IconWater size={15} />}
              label="Recharge Velocity"
              value={(data.recharge_rate_m_per_day || 0).toFixed(4)}
              unit="m/day"
              color="#0f172a"
              sub="Water Table Fluctuation"
            />
            <StatCard
              icon={<IconClock size={15} />}
              label="Hydraulic Lag"
              value={(data.lag_hours || 0).toFixed(1)}
              unit="hrs"
              color="#0d9488"
              sub="Rainfall peak to water response"
            />
            <StatCard
              icon={<IconRain size={15} />}
              label="Net Seasonal Recharge"
              value={data.net_recharge_m != null ? `${data.net_recharge_m > 0 ? '+' : ''}${data.net_recharge_m}` : '—'}
              unit="m"
              color={data.net_recharge_m > 0 ? '#16a34a' : '#dc2626'}
              sub="Post-monsoon minus pre-monsoon"
            />
            <StatCard
              icon={<IconPin size={15} />}
              label="Pre-Monsoon Level"
              value={data.pre_monsoon_level_m?.toFixed(2) ?? '—'}
              unit="m bgl"
              color="#64748b"
              sub="May baseline"
            />
            <StatCard
              icon={<IconPin size={15} />}
              label="Post-Monsoon Level"
              value={data.post_monsoon_level_m?.toFixed(2) ?? '—'}
              unit="m bgl"
              color="#0284c7"
              sub="November baseline"
            />
            <StatCard
              icon={<IconRock size={15} />}
              label="Aquifer Classification"
              value={data.aquifer_type || 'Unclassified'}
              unit=""
              color="#1e3a8a"
              sub="Geological formation"
            />
          </div>

          <div className="charts-row">
            <div className="chart-card">
              <div className="cc-title"><IconTarget style={{ marginRight: '6px' }} /> Recharge Zone Classification</div>
              <Gauge value={(data.recharge_rate_m_per_day || 0) * 1000} max={200} color={zoneColor} label="recharge rate (mm/day)" />
              <div className="zone-badge-large" style={{ background: `${zoneColor}12`, color: zoneColor, borderColor: `${zoneColor}35` }}>
                {(data.zone_status || 'unknown').replace(/_/g, ' ').toUpperCase()}
              </div>
              <div className="zone-desc">
                {data.zone_status === 'good_recharge' && 'Aquifer demonstrates active seasonal replenishment. Abstraction within sustainable recharge capacity.'}
                {data.zone_status === 'moderate_recharge' && 'Measurable recovery observed but replenishment is below expected hydrological equilibrium.'}
                {data.zone_status === 'stressed' && 'Subdued aquifer recovery following rainfall events. Close surveillance advised.'}
                {data.zone_status === 'critically_stressed' && 'Zero or negative net recharge. Extraction outpaces natural replenishment.'}
                {data.zone_status === 'insufficient_data' && 'Precipitation series insufficient for full seasonal zone classification.'}
              </div>
            </div>

            <div className="chart-card wide">
              <div className="cc-title"><IconWeather style={{ marginRight: '6px' }} /> Pre- vs Post-Monsoon Hydrostatic Comparison</div>
              <div className="cc-sub">Depicts static water table recovery (shallower depth = higher water reserve)</div>
              {data.pre_monsoon_level_m != null && data.post_monsoon_level_m != null ? (
                <>
                  <BarChart
                    data={[
                      { period: 'Pre-Monsoon (May)',  level: data.pre_monsoon_level_m },
                      { period: 'Post-Monsoon (Nov)', level: data.post_monsoon_level_m }
                    ]}
                    xKey="period"
                    yKey="level"
                    color="#0284c7"
                    height={150}
                  />
                  <div className="monsoon-compare">
                    <div className="mc-item">
                      <span className="mc-label">Pre-Monsoon Level:</span>
                      <span className="mc-val font-mono">{data.pre_monsoon_level_m?.toFixed(3)} m bgl</span>
                    </div>
                    <div className="mc-arrow" style={{ color: data.net_recharge_m > 0 ? '#16a34a' : '#dc2626' }}>
                      {data.net_recharge_m > 0 ? 'Net Recovery: ' : 'Net Drawdown: '}
                      {Math.abs(data.net_recharge_m || 0).toFixed(3)} m
                    </div>
                    <div className="mc-item">
                      <span className="mc-label">Post-Monsoon Level:</span>
                      <span className="mc-val font-mono">{data.post_monsoon_level_m?.toFixed(3)} m bgl</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="chart-empty">
                  Seasonal monsoon pair not yet indexed for this station in TimescaleDB.
                  <br />Requires observations spanning pre-monsoon (April–May) and post-monsoon (October–November).
                </div>
              )}
            </div>
          </div>

          <div className="charts-row">
            <div className="chart-card wide">
              <div className="cc-title"><IconLightning style={{ marginRight: '6px' }} /> Precipitation &amp; Recharge Event History</div>
              <div className="cc-sub">Individual rainfall triggers (&gt; 10mm) and observed static water level recoveries</div>
              {data.recharge_events?.length > 0 ? (
                <>
                  <LineChart
                    data={[...data.recharge_events].reverse()}
                    xKey="date"
                    yKey="recovery_m"
                    color="#0d9488"
                    label="Recovery Displacement (m)"
                    height={160}
                  />
                  <div className="events-table">
                    <div className="et-head">Event Date</div>
                    <div className="et-head">Precipitation</div>
                    <div className="et-head">Observed Recovery</div>
                    <div className="et-head">Hydraulic Lag</div>
                    <div className="et-head">Recharge Rate</div>
                    {data.recharge_events.map((e, i) => (
                      <React.Fragment key={i}>
                        <div className="et-cell mono">{e.date}</div>
                        <div className="et-cell blue">{e.rainfall_mm} mm</div>
                        <div className="et-cell green">+{e.recovery_m} m</div>
                        <div className="et-cell">{e.lag_hours} hrs</div>
                        <div className="et-cell mono">{(e.recharge_rate_m_per_day || 0).toFixed(4)} m/d</div>
                      </React.Fragment>
                    ))}
                  </div>
                </>
              ) : (
                <div className="chart-empty">
                  No individual rainfall recharge events detected in the current window.
                  <br />Events require recorded rainfall &gt; 10mm followed by measurable hydrostatic recovery.
                </div>
              )}
            </div>

            <div className="chart-card">
              <div className="cc-title"><IconRock style={{ marginRight: '6px' }} /> Hydrogeological Formation Profile</div>
              <div className="aquifer-info">
                <div className="ai-type">{data.aquifer_type || 'Unclassified Formation'}</div>
                <div className="ai-desc">
                  {data.aquifer_type === 'Alluvial' && 'High permeability with fast hydraulic response (6–12h lag). High specific yield ensures rapid infiltration.'}
                  {data.aquifer_type === 'Hard Rock' && 'Fracture-dominated secondary porosity with slower recharge (24–48h lag). Permeability depends on fissure networks.'}
                  {data.aquifer_type === 'Basalt' && 'Vesicular basalt flow horizons support intermediate infiltration capacity and moderate specific yield.'}
                  {data.aquifer_type === 'Granite' && 'Relatively low primary porosity; relies on weathered saprolite zones for seasonal moisture storage.'}
                  {data.aquifer_type === 'Limestone' && 'Karstic conduits facilitate rapid localized infiltration with minimal surface runoff loss.'}
                  {!['Alluvial', 'Hard Rock', 'Basalt', 'Granite', 'Limestone'].includes(data.aquifer_type) && 'Aquifer response conditioned by localized lithological strata and regional weathering profile.'}
                </div>
                {data.lag_hours > 0 && (
                  <div className="ai-lag">
                    <span>Calibrated Hydraulic Lag:</span>
                    <span className="font-mono">{data.lag_hours?.toFixed(1)} hours</span>
                  </div>
                )}
                {data.recharge_capacity_m != null && (
                  <div className="ai-lag">
                    <span>Available Vadose Storage:</span>
                    <span className="font-mono text-positive">{data.recharge_capacity_m?.toFixed(2)} m</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TASK 3 DETAIL: CGWB Resource Evaluation & Sustainability Index
// ══════════════════════════════════════════════════════════════
export function Task3Detail({ station, onBack }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/task3/${station.station_id}?days=365`)
      .then(r => r.json())
      .then(d => { setData(d.error ? null : d); setLoading(false); })
      .catch(() => { setData(null); setLoading(false); });
  }, [station.station_id]);

  const s = STATUS[data?.status] || STATUS.unknown;
  const cgwbZones = [
    { key: 'safe',           pct: 40, label: 'Safe Depth (< 8m)' },
    { key: 'semi_critical',  pct: 25, label: 'Semi-Critical Depth (8–15m)' },
    { key: 'critical',       pct: 20, label: 'Critical Depth (15–25m)' },
    { key: 'over_exploited', pct: 15, label: 'Over-Exploited Depth (> 25m)' },
  ];

  const deplRate = data?.annual_depletion_rate_m;
  const deplDisplay = deplRate != null ? `${deplRate > 0 ? '+' : ''}${deplRate.toFixed(3)}` : '—';
  const deplColor = deplRate != null ? (deplRate > 0 ? '#dc2626' : '#16a34a') : '#64748b';

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>
          <IconArrowLeft size={14} style={{ marginRight: '6px' }} /> Return to Well Dossier
        </button>
        <div className="tdp-title-row">
          <div className="tdp-tag task3-tag">Task 3</div>
          <div>
            <h1 className="tdp-title">Aquifer Resource Evaluation &amp; Sustainability Index</h1>
            <p className="tdp-sub">{station.station_name || station.station_id} · {station.district}, {station.state} · CGWB Resource Availability Index (RAI)</p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="tdp-loading">
          <div className="tdp-spinner" />
          <span>Computing Resource Availability Index and projected depletion velocity...</span>
        </div>
      ) : !data ? (
        <div className="tdp-empty">No resource evaluation indices available for this station.</div>
      ) : (
        <>
          {data.alert_required && (
            <div className="alert-banner">
              <IconSiren size={16} style={{ marginRight: '8px' }} />
              <div>
                <strong>CRITICAL RESOURCE NOTIFICATION:</strong> Static water level ({data.current_level_m}m bgl) has breached CGWB critical depletion thresholds. Mandatory regulatory intervention required.
              </div>
            </div>
          )}

          <div className="kpi-row">
            <StatCard
              icon={<IconWater size={15} />}
              label="Static Level"
              value={data.current_level_m?.toFixed(2) ?? '—'}
              unit="m bgl"
              color="#0f172a"
              sub="Current measurement"
            />
            <StatCard
              icon={<IconTarget size={15} />}
              label="RAI Sustainability Score"
              value={data.resource_availability_index?.toFixed(1) ?? '—'}
              unit="/100"
              color={s.color}
              sub="Resource Availability Index"
            />
            <StatCard
              icon={<IconTrend size={15} />}
              label="Annual Depletion"
              value={deplDisplay}
              unit="m/yr"
              color={deplColor}
              sub="Multi-year velocity"
            />
            <StatCard
              icon={<IconHourglass size={15} />}
              label="Longevity Horizon"
              value={data.years_to_depletion != null ? data.years_to_depletion : '∞'}
              unit={data.years_to_depletion != null ? 'yrs' : ''}
              color={data.years_to_depletion != null && data.years_to_depletion < 15 ? '#dc2626' : '#16a34a'}
              sub="Years to critical boundary"
            />
            <StatCard
              icon={<IconFolder size={15} />}
              label="Stage of Extraction"
              value={data.stage_of_development_pct != null ? data.stage_of_development_pct.toFixed(1) : '—'}
              unit={data.stage_of_development_pct != null ? '%' : ''}
              color="#d97706"
              sub="Draft / Recharge ratio"
            />
            <StatCard
              icon={<IconRock size={15} />}
              label="Aquifer System"
              value={data.aquifer_type || 'Unclassified'}
              unit=""
              color="#1e3a8a"
              sub="Lithology profile"
            />
          </div>

          <div className="charts-row">
            <div className="chart-card">
              <div className="cc-title"><IconBuilding style={{ marginRight: '6px' }} /> Depth Tier &amp; RAI Score</div>
              <Gauge value={data.resource_availability_index || 0} max={100} color={s.color} label="Resource Availability Index" />
              <div className="status-display" style={{ borderColor: `${s.color}35`, background: `${s.color}08` }}>
                <div className="sd-dot" style={{ background: s.color }} />
                <div>
                  <div className="sd-status" style={{ color: s.color }}>{s.label}</div>
                  <div className="sd-level">Observed Depth: {data.current_level_m}m bgl</div>
                </div>
              </div>
            </div>

            <div className="chart-card">
              <div className="cc-title"><IconChart style={{ marginRight: '6px' }} /> Depth Indicator Tiers &amp; GEC Matrix</div>
              <div className="cc-sub">Exploratory well depth ranges vs. statutory GEC-2015 extraction guidelines</div>
              <PieChart slices={cgwbZones.map(z => ({ label: z.label, value: z.pct, color: STATUS[z.key].color }))} size={140} />
              <div className="pie-legend">
                {cgwbZones.map(z => (
                  <div key={z.key} className="pl-item">
                    <span style={{ background: STATUS[z.key].color }} />
                    {z.label} — {z.pct}%
                  </div>
                ))}
              </div>
            </div>

            <div className="chart-card wide">
              <div className="cc-title"><IconHourglass style={{ marginRight: '6px' }} /> Multi-Year Aquifer Longevity Projection</div>
              <div className="cc-sub">Depletion trajectory extrapolated at annual velocity of {deplDisplay} m/year</div>
              {deplRate != null && deplRate > 0 && data.current_level_m != null ? (
                <>
                  <LineChart
                    data={Array.from({ length: Math.min(30, Math.ceil(data.years_to_depletion || 30)) }, (_, i) => ({
                      year: new Date().getFullYear() + i,
                      level: parseFloat((data.current_level_m + deplRate * i).toFixed(2)),
                    }))}
                    xKey="year"
                    yKey="level"
                    color="#dc2626"
                    label="Projected Static Water Depth (m bgl)"
                    height={180}
                  />
                  <div className="depletion-note">
                    {data.years_to_depletion != null && data.years_to_depletion < 50 ? (
                      <>
                        <IconAlert size={14} style={{ marginRight: '6px', color: '#dc2626' }} />
                        <span>At current extraction rate, aquifer reaches critical threshold within {Math.round(data.years_to_depletion)} years ({new Date().getFullYear() + Math.round(data.years_to_depletion)}).</span>
                      </>
                    ) : (
                      <>
                        <IconCheck size={14} style={{ marginRight: '6px', color: '#16a34a' }} />
                        <span>Depletion horizon exceeds 50 years under existing extraction velocity.</span>
                      </>
                    )}
                  </div>
                </>
              ) : (
                <div className="recovering-note">
                  <IconCheck size={16} style={{ marginRight: '6px', color: '#16a34a' }} />
                  <span>Static water table is recovering at {Math.abs(deplRate || 0).toFixed(3)} m/year. Aquifer reserve is in sustainable balance.</span>
                </div>
              )}
            </div>
          </div>

          <div className="charts-row">
            <div className="chart-card wide">
              <div className="cc-title"><IconCalendar style={{ marginRight: '6px' }} /> Historical Multi-Year Trend Hydrograph</div>
              <div className="cc-sub">Annual pre-monsoon baseline — {(data.historical_trend?.long_term_direction || 'stable').replace(/_/g, ' ')} trajectory</div>
              {data.historical_trend?.data?.length > 1 ? (
                <LineChart
                  data={data.historical_trend.data}
                  xKey="year"
                  yKey="avg_level_m"
                  color={s.color}
                  label="Annual Average Static Level (m bgl)"
                  height={180}
                />
              ) : (
                <div className="chart-empty">Insufficient longitudinal historical readings (requires ≥ 2 calendar years).</div>
              )}
            </div>

            <div className="chart-card">
              <div className="cc-title"><IconClipboard style={{ marginRight: '6px' }} /> Depth Indicators &amp; GEC-2015 Criteria</div>
              <div className="thresholds">
                {[
                  { label: 'Safe',           range: '< 8m',   stage: '< 70%',   color: '#16a34a', key: 'safe' },
                  { label: 'Semi-Critical',  range: '8–15m',  stage: '70–90%',  color: '#d97706', key: 'semi_critical' },
                  { label: 'Critical',       range: '15–25m', stage: '90–100%', color: '#ea580c', key: 'critical' },
                  { label: 'Over-Exploited', range: '> 25m',  stage: '> 100%',  color: '#dc2626', key: 'over_exploited' },
                ].map(t => (
                  <div key={t.key} className={`threshold-row ${data.status === t.key ? 'active' : ''}`}>
                    <div className="tr-dot" style={{ background: t.color }} />
                    <div className="tr-label" style={{ color: data.status === t.key ? t.color : undefined }}>{t.label}</div>
                    <div className="tr-range">{t.range}</div>
                    <div className="tr-stage">{t.stage}</div>
                    {data.status === t.key && <div className="tr-you">WELL STATUS</div>}
                  </div>
                ))}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.4 }}>
                *Note: Depth thresholds (&lt;8m, 8–15m, 15–25m, &gt;25m) are operational depth indicators. Official CGWB/GEC-2015 assessment requires assessment-unit volumetric extraction and recharge accounting.
              </div>
              <div className="summary-text" style={{ marginTop: '0.75rem' }}>{data.summary || 'Resource evaluation complete.'}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
