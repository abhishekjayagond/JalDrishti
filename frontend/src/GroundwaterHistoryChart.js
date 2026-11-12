import React, { useState, useMemo } from 'react';

export default function GroundwaterHistoryChart({
  station,
  historyData = [],
  loading = false,
  wellDepth = null,
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  // Extract the actual 5 most recent available annual pre-monsoon observations
  const { observations, trendSummary, gapYears, hasGaps } = useMemo(() => {
    if (!historyData || historyData.length === 0) {
      return { observations: [], trendSummary: null, gapYears: [], hasGaps: false };
    }

    const sorted = [...historyData].sort((a, b) => {
      const da = new Date(a.date || a.timestamp || a.year).getTime();
      const db = new Date(b.date || b.timestamp || b.year).getTime();
      return da - db;
    });

    const recent = sorted.slice(-5).map(item => {
      const dateStr = item.date || item.timestamp || `${item.year}-05-01`;
      const year = new Date(dateStr).getFullYear() || parseInt(String(dateStr).slice(0, 4), 10);
      const depth = Number(item.avg_level_m ?? item.water_level_m ?? item.depth ?? 0);
      return {
        year,
        depth: Number(depth.toFixed(2)),
        date: dateStr,
      };
    });

    if (recent.length === 0) {
      return { observations: [], trendSummary: null, gapYears: [], hasGaps: false };
    }

    const gaps = [];
    for (let i = 1; i < recent.length; i++) {
      const diff = recent[i].year - recent[i - 1].year;
      if (diff > 1) {
        gaps.push({ from: recent[i - 1].year, to: recent[i].year, gapSize: diff - 1 });
      }
    }

    let summary = '';
    if (recent.length >= 2) {
      const earliest = recent[0];
      const latest = recent[recent.length - 1];
      const delta = Number((latest.depth - earliest.depth).toFixed(2));
      const absDelta = Math.abs(delta);

      if (delta > 0.05) {
        summary = `Groundwater depth increased by ${absDelta} m between ${earliest.year} and ${latest.year} (water table declined farther underground).`;
      } else if (delta < -0.05) {
        summary = `Groundwater depth decreased by ${absDelta} m between ${earliest.year} and ${latest.year} (water table recovered closer to surface).`;
      } else {
        summary = `Groundwater depth remained stable at ${latest.depth} m bgl between ${earliest.year} and ${latest.year}.`;
      }
    }

    return {
      observations: recent,
      trendSummary: summary,
      gapYears: gaps,
      hasGaps: gaps.length > 0,
    };
  }, [historyData]);

  if (loading) {
    return (
      <div style={{ padding: '32px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
        <div className="spinner-ring" />
        <span className="font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Loading historical observations from database...
        </span>
      </div>
    );
  }

  if (observations.length === 0) {
    return (
      <div style={{ padding: '32px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
        <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
          Historical Annual Series Unavailable
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '420px', lineHeight: 1.5 }}>
          Continuous multi-year pre-monsoon observations (1994–2025) are recorded for 390 verified Central Ground Water Board (CGWB) observation wells across Karnataka.
          {station?.is_benchmark && (
            <span> This station is a national calibration benchmark reference node.</span>
          )}
        </p>
      </div>
    );
  }

  const svgWidth = 660;
  const svgHeight = 260;
  const marginLeft = 70;
  const marginRight = 35;
  const marginTop = 25;
  const marginBottom = 45;

  const plotWidth = svgWidth - marginLeft - marginRight;
  const plotHeight = svgHeight - marginTop - marginBottom;

  const depths = observations.map(o => o.depth);
  const minObs = Math.min(...depths);
  const maxObs = Math.max(...depths);
  const span = maxObs - minObs;
  const pad = Math.max(1.0, span * 0.25);

  const yMin = Math.max(0, Math.floor(minObs - pad));
  const yMax = Math.ceil(maxObs + pad);
  const yRange = yMax - yMin || 5;

  const getY = (depth) => {
    return marginTop + ((depth - yMin) / yRange) * plotHeight;
  };

  const getX = (index) => {
    if (observations.length === 1) return marginLeft + plotWidth / 2;
    return marginLeft + (index / (observations.length - 1)) * plotWidth;
  };

  const yTicks = [
    yMin,
    Number((yMin + yRange * 0.33).toFixed(1)),
    Number((yMin + yRange * 0.67).toFixed(1)),
    yMax,
  ];

  const points = observations.map((obs, idx) => ({
    ...obs,
    x: getX(idx),
    y: getY(obs.depth),
    index: idx,
  }));

  const activeObs = hoveredIndex != null ? points[hoveredIndex] : points[points.length - 1];

  return (
    <div className="gwh-chart-wrap font-sans">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <span className="eyebrow">5-Year Historical Groundwater Telemetry</span>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-primary)', margin: '2px 0 0 0' }}>
            Annual Pre-Monsoon Static Water Level History
          </h3>
        </div>
        {activeObs && (
          <div className="font-mono" style={{ fontSize: '12px', background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '4px 10px', display: 'flex', gap: '6px' }}>
            <span style={{ color: 'var(--text-muted)' }}>{activeObs.year} Reading:</span>
            <strong style={{ color: 'var(--color-primary)' }}>{activeObs.depth} m bgl</strong>
          </div>
        )}
      </div>

      {trendSummary && (
        <div style={{ fontSize: '12px', color: 'var(--color-secondary)', background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', lineHeight: 1.5 }}>
          <span>{trendSummary}</span>
          {hasGaps && (
            <span style={{ color: 'var(--text-subtle)', marginLeft: '6px' }}>
              (Dashed segment indicates years with no recorded field survey).
            </span>
          )}
        </div>
      )}

      <div style={{ width: '100%', height: `${svgHeight}px`, background: '#000000', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', position: 'relative', overflow: 'hidden' }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height: '100%' }}
          role="img"
          aria-label="5-year groundwater level history chart"
        >
          {/* Y Axis Grid Lines & Labels */}
          {yTicks.map((val, idx) => {
            const yPos = getY(val);
            const isTop = idx === 0;
            const isBottom = idx === yTicks.length - 1;
            return (
              <g key={`ytick-${idx}`}>
                <line
                  x1={marginLeft}
                  y1={yPos}
                  x2={marginLeft + plotWidth}
                  y2={yPos}
                  stroke="var(--color-border)"
                  strokeWidth="0.8"
                  strokeDasharray="2 3"
                  opacity="0.6"
                />
                <text
                  x={marginLeft - 8}
                  y={yPos + 3}
                  textAnchor="end"
                  fontSize="9.5"
                  fill="var(--text-subtle)"
                  fontFamily="var(--font-mono)"
                >
                  {val}m
                </text>
                {isTop && (
                  <text
                    x={marginLeft - 8}
                    y={yPos - 8}
                    textAnchor="end"
                    fontSize="8.5"
                    fill="#22c55e"
                    fontWeight="600"
                  >
                    Shallower ↑
                  </text>
                )}
                {isBottom && (
                  <text
                    x={marginLeft - 8}
                    y={yPos + 15}
                    textAnchor="end"
                    fontSize="8.5"
                    fill="#ef4444"
                    fontWeight="600"
                  >
                    Deeper ↓
                  </text>
                )}
              </g>
            );
          })}

          {/* Connecting Line Segments */}
          {points.map((pt, i) => {
            if (i === 0) return null;
            const prev = points[i - 1];
            const isGap = pt.year - prev.year > 1;
            return (
              <line
                key={`line-${i}`}
                x1={prev.x}
                y1={prev.y}
                x2={pt.x}
                y2={pt.y}
                stroke="var(--color-primary)"
                strokeWidth="2"
                strokeDasharray={isGap ? "4 3" : "none"}
                strokeLinecap="round"
                opacity={isGap ? 0.6 : 1}
              />
            );
          })}

          {/* Points */}
          {points.map((pt, i) => {
            const isHovered = hoveredIndex === i;
            return (
              <g
                key={`point-${i}`}
                onMouseEnter={() => setHoveredIndex(i)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: 'pointer' }}
              >
                {isHovered && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r="8"
                    fill="none"
                    stroke="var(--color-primary)"
                    strokeWidth="1"
                    opacity="0.5"
                  />
                )}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isHovered ? "5" : "3.5"}
                  fill="#000000"
                  stroke="var(--color-primary)"
                  strokeWidth="2"
                />
              </g>
            );
          })}

          {/* X Axis Labels */}
          {points.map((pt, i) => (
            <text
              key={`xlabel-${i}`}
              x={pt.x}
              y={svgHeight - 14}
              textAnchor="middle"
              fontSize="10"
              fill={hoveredIndex === i ? 'var(--color-primary)' : 'var(--text-subtle)'}
              fontWeight={hoveredIndex === i ? '600' : '400'}
              fontFamily="var(--font-mono)"
            >
              {pt.year}
            </text>
          ))}
        </svg>

        {/* Hover Tooltip */}
        {hoveredIndex !== null && points[hoveredIndex] && (
          <div
            style={{
              position: 'absolute',
              left: `${points[hoveredIndex].x - 45}px`,
              top: `${Math.max(10, points[hoveredIndex].y - 45)}px`,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              padding: '4px 8px',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              pointerEvents: 'none',
              zIndex: 10,
              whiteSpace: 'nowrap'
            }}
          >
            <span style={{ color: 'var(--text-subtle)' }}>{points[hoveredIndex].year}: </span>
            <strong style={{ color: 'var(--color-primary)' }}>{points[hoveredIndex].depth} m</strong>
          </div>
        )}
      </div>
    </div>
  );
}
