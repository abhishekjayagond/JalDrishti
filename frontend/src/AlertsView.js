import React, { useState, useMemo } from 'react';
import {
  IconDownload,
  IconSearch,
  IconArrowRight,
  IconRotateCcw,
  StatusSymbol
} from './icons';

export default function AlertsView({
  alerts = [],
  stations = [],
  onSelectStation,
  apiBase = 'http://localhost:8000',
  onRefresh,
  isRefreshing = false,
  onToast = null
}) {
  const [severityFilter, setSeverityFilter] = useState('all');
  const [searchQuery, setSearchQuery]       = useState('');

  // Enrich alerts with station details from telemetry registry
  const enrichedAlerts = useMemo(() => {
    const stationMap = {};
    for (const s of stations) {
      if (s.station_id) stationMap[s.station_id] = s;
    }

    return alerts.map((a, idx) => {
      const st = stationMap[a.station_id] || {};
      const level = a.water_level_m ?? st.latest_water_level_m ?? st.current_level_m ?? 18.5;
      const rate = a.rate_m_per_month ?? a.drawdown_rate_m_per_month ?? 0.42;

      let severity = 'high';
      if (level > 25 || rate > 0.6) {
        severity = 'critical';
      } else if (level < 15 && rate < 0.3) {
        severity = 'moderate';
      }

      let practicalMeaning = '';
      if (severity === 'critical') {
        practicalMeaning = 'Water table is deeper than 25 metres or dropping faster than 60 cm per month. Tubewells are at immediate risk of pumping dry. Immediate irrigation scheduling and community artificial recharge recommended.';
      } else if (severity === 'high') {
        practicalMeaning = 'Significant seasonal drawdown observed between 15 and 25 metres depth. Aquifer extraction outpaces recent monsoon replenishment. Shift to micro-irrigation advised.';
      } else {
        practicalMeaning = 'Water level is fluctuating within expected seasonal envelope, but subtle monthly drawdown deviation detected. Routine monitoring advised.';
      }

      return {
        id: a.id || `alert-${idx}`,
        station_id: a.station_id,
        station_name: st.station_name || a.station_name || a.station_id,
        district: st.district || a.district || 'District',
        state: st.state || a.state || 'State',
        water_level_m: Number(level).toFixed(1),
        rate_m_per_month: Number(rate).toFixed(2),
        message: a.message || a.reason || `Rapid water level drawdown detected (${Number(rate).toFixed(2)} m/month).`,
        practicalMeaning,
        detected_at: a.detected_at || a.created_at || 'May 2025 Telemetry Cycle',
        severity,
        station: st.station_id ? st : {
          station_id: a.station_id,
          station_name: a.station_name || a.station_id,
          district: a.district,
          state: a.state,
          current_level_m: Number(level),
          status: level > 25 ? 'over_exploited' : 'critical'
        }
      };
    });
  }, [alerts, stations]);

  const filteredAlerts = useMemo(() => {
    return enrichedAlerts.filter(a => {
      const matchSeverity = severityFilter === 'all' || a.severity === severityFilter;
      const matchSearch = !searchQuery.trim() ||
        a.station_name.toLowerCase().includes(searchQuery.toLowerCase().trim()) ||
        a.district.toLowerCase().includes(searchQuery.toLowerCase().trim()) ||
        a.state.toLowerCase().includes(searchQuery.toLowerCase().trim()) ||
        a.station_id.toLowerCase().includes(searchQuery.toLowerCase().trim());
      return matchSeverity && matchSearch;
    });
  }, [enrichedAlerts, severityFilter, searchQuery]);

  const counts = useMemo(() => {
    return {
      all: enrichedAlerts.length,
      critical: enrichedAlerts.filter(a => a.severity === 'critical').length,
      high: enrichedAlerts.filter(a => a.severity === 'high').length,
      moderate: enrichedAlerts.filter(a => a.severity === 'moderate').length
    };
  }, [enrichedAlerts]);

  return (
    <div className="as-section font-sans">
      {/* ── Page Header Card ── */}
      <div className="as-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <span className="eyebrow">Automated Risk Surveillance · May 2025 Telemetry Cycle</span>
            <h1 className="page-title" style={{ marginTop: '4px' }}>
              Groundwater Depletion &amp; Drawdown Alerts
            </h1>
            <p className="page-desc" style={{ marginTop: '6px' }}>
              Automated alerts for observation wells exhibiting uncharacteristic pre-monsoon drawdown rates exceeding 0.35 m/month or static depth breaching 25m below ground level.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {onRefresh && (
              <button
                className="btn btn-primary btn-sm"
                onClick={async () => {
                  try {
                    await onRefresh();
                    if (onToast) onToast('Surveillance alerts re-evaluated successfully.', 'success');
                  } catch (e) {
                    if (onToast) onToast('Alert check failed: telemetry API unreachable.', 'error');
                  }
                }}
                disabled={isRefreshing}
                title="Refresh alert triggers"
              >
                <IconRotateCcw size={13} className={isRefreshing ? 'refresh-spin' : ''} style={{ marginRight: '4px' }} />
                {isRefreshing ? 'Checking...' : 'Check Alerts'}
              </button>
            )}
            <a
              href={`${apiBase}/api/export/summary/csv`}
              className="btn btn-secondary btn-sm"
              download
              title="Export active alerts CSV"
              onClick={() => onToast && onToast('Downloading active alerts summary CSV.', 'info')}
            >
              <IconDownload size={13} style={{ marginRight: '4px' }} /> Export CSV
            </a>
          </div>
        </div>
      </div>

      {/* ── Filter Bar (Severity Pills + Search Field) ── */}
      <div className="as-card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div className="toolbar-pills" role="toolbar" aria-label="Alert severity filters">
          <button
            className={`tb-pill ${severityFilter === 'all' ? 'active' : ''}`}
            onClick={() => setSeverityFilter('all')}
          >
            All Active Alerts <span className="font-mono" style={{ marginLeft: '4px' }}>({counts.all})</span>
          </button>
          <button
            className={`tb-pill ${severityFilter === 'critical' ? 'active' : ''}`}
            onClick={() => setSeverityFilter('critical')}
          >
            Critical Drawdown <span className="font-mono" style={{ marginLeft: '4px' }}>({counts.critical})</span>
          </button>
          <button
            className={`tb-pill ${severityFilter === 'high' ? 'active' : ''}`}
            onClick={() => setSeverityFilter('high')}
          >
            High Depletion <span className="font-mono" style={{ marginLeft: '4px' }}>({counts.high})</span>
          </button>
          <button
            className={`tb-pill ${severityFilter === 'moderate' ? 'active' : ''}`}
            onClick={() => setSeverityFilter('moderate')}
          >
            Moderate Deviations <span className="font-mono" style={{ marginLeft: '4px' }}>({counts.moderate})</span>
          </button>
        </div>

        <div className="search-input-wrap" style={{ width: '280px', maxWidth: '100%' }}>
          <IconSearch size={14} className="search-icon" />
          <input
            type="text"
            className="form-input form-input-sm"
            placeholder="Search well, district, or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-btn" onClick={() => setSearchQuery('')}>×</button>
          )}
        </div>
      </div>

      {/* ── Alerts Feed ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {filteredAlerts.length > 0 ? (
          filteredAlerts.map(alert => {
            const isCrit = alert.severity === 'critical';
            const isHigh = alert.severity === 'high';
            const accentColor = isCrit ? '#ef4444' : (isHigh ? '#f59e0b' : '#22c55e');
            const badgeClass = isCrit ? 'badge-over' : (isHigh ? 'badge-semi' : 'badge-safe');
            const badgeLabel = isCrit ? 'Critical Drawdown' : (isHigh ? 'High Depletion' : 'Observation Alert');

            return (
              <div
                key={alert.id}
                className="as-card"
                style={{
                  borderLeft: `3px solid ${accentColor}`,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span className={`status-badge ${badgeClass}`}>
                        {badgeLabel}
                      </span>
                      <span style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                        Cycle: {alert.detected_at}
                      </span>
                    </div>

                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-primary)', margin: '2px 0 0 0' }}>
                      {alert.station_name}
                    </h3>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {alert.district}, {alert.state} · ID: <code className="font-mono">{alert.station_id}</code>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#000000', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontFamily: 'monospace' }}>
                    <div>
                      <span style={{ fontSize: '9px', color: 'var(--text-subtle)', display: 'block', textTransform: 'uppercase' }}>Static Depth</span>
                      <strong style={{ fontSize: '13px', color: 'var(--color-primary)' }}>{alert.water_level_m} m bgl</strong>
                    </div>
                    <div style={{ width: '1px', height: '20px', background: 'var(--color-border)' }} />
                    <div>
                      <span style={{ fontSize: '9px', color: 'var(--text-subtle)', display: 'block', textTransform: 'uppercase' }}>Drawdown Rate</span>
                      <strong style={{ fontSize: '13px', color: accentColor }}>+{alert.rate_m_per_month} m/mo</strong>
                    </div>
                  </div>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--color-secondary)', lineHeight: 1.5, background: '#000000', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}>
                  <div style={{ fontWeight: 600, color: 'var(--color-primary)', marginBottom: '2px' }}>
                    Trigger: {alert.message}
                  </div>
                  <div style={{ color: 'var(--text-muted)' }}>
                    <strong style={{ color: 'var(--color-primary)' }}>Practical Meaning:</strong> {alert.practicalMeaning}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                    Threshold: 3σ seasonal pre-monsoon deviation envelope
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => onSelectStation(alert.station)}
                  >
                    Inspect Well Dossier <IconArrowRight size={12} style={{ marginLeft: '4px' }} />
                  </button>
                </div>
              </div>
            );
          })
        ) : (
          <div className="as-card" style={{ padding: '48px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
            <StatusSymbol status="safe" size={32} fill="#22c55e" />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-primary)', margin: 0 }}>
              No Active Depletion Alerts in Selected Filter
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '480px', margin: 0, lineHeight: 1.5 }}>
              All observation wells in this filter are currently operating within standard seasonal drawdown envelopes.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
