import React, { useState } from 'react';
import {
  IconInfo,
  IconAlert,
  IconCheck,
  IconMap,
  IconCpu,
  IconDatabase,
  IconDroplet,
  IconLayers,
  IconTrendUp,
  IconChevronDown,
  IconChevronUp,
  IconArrowRight,
  IconArrowLeft,
  StatusSymbol
} from './icons';

export default function MethodologyView() {
  const [activeSection, setActiveSection] = useState('monitoring');

  const [expandedDetails, setExpandedDetails] = useState({
    wtfMath: false,
    aiModel: false,
    dataAudit: false,
    mercatorMath: false,
  });

  const toggleDetail = (key) => {
    setExpandedDetails(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const sections = [
    { id: 'monitoring', title: '1. Groundwater Monitoring', shortTitle: 'Monitoring Basics', icon: IconDroplet },
    { id: 'trends', title: '2. Groundwater Trend Analysis', shortTitle: 'Trend Analysis', icon: IconTrendUp },
    { id: 'classification', title: '3. Resource Classification', shortTitle: 'Resource Classification', icon: IconLayers },
    { id: 'forecasting', title: '4. AI Forecasting', shortTitle: 'AI Forecasting', icon: IconCpu },
    { id: 'provenance', title: '5. Data Sources & Reliability', shortTitle: 'Data Sources & Reliability', icon: IconDatabase },
    { id: 'mapping', title: '6. Map & Geographic Accuracy', shortTitle: 'Map & Geospatial', icon: IconMap },
  ];

  const currentSectionIdx = sections.findIndex(s => s.id === activeSection);

  const goToPrev = () => {
    if (currentSectionIdx > 0) {
      setActiveSection(sections[currentSectionIdx - 1].id);
      window.scrollTo({ top: 80, behavior: 'smooth' });
    }
  };

  const goToNext = () => {
    if (currentSectionIdx < sections.length - 1) {
      setActiveSection(sections[currentSectionIdx + 1].id);
      window.scrollTo({ top: 80, behavior: 'smooth' });
    }
  };

  return (
    <div className="as-section font-sans">
      {/* ── Page Header Card ── */}
      <div className="as-card">
        <span className="eyebrow">Documentation &amp; Hydrogeological Framework</span>
        <h1 className="page-title" style={{ marginTop: '4px' }}>Scientific Methodology</h1>
        <p className="page-desc" style={{ marginTop: '6px' }}>
          Standardized telemetry processing, Water Table Fluctuation (WTF) analysis, statutory GEC-2015 alignment, and predictive regression architecture.
        </p>

        {/* ── Navigation Tabs ── */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '18px' }}>
          {sections.map((sec) => {
            const IconComp = sec.icon;
            const isActive = activeSection === sec.id;
            return (
              <button
                key={sec.id}
                className={`tb-pill ${isActive ? 'active' : ''}`}
                onClick={() => setActiveSection(sec.id)}
              >
                <IconComp size={13} />
                <span>{sec.shortTitle}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Main Content Area ── */}
      <main>
        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 1: GROUNDWATER MONITORING
            ═════════════════════════════════════════════════════════════════════ */}
        {activeSection === 'monitoring' && (
          <article className="as-card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <span className="eyebrow">Section 1</span>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Groundwater Telemetry Monitoring
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
                How static groundwater depth is measured by observation wells and reported across India.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Understanding Static Water Depth &amp; Units
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--color-secondary)', lineHeight: 1.6 }}>
                Groundwater levels in India are officially reported in <strong>metres below ground level (m bgl)</strong>.
                This value represents the vertical distance from the ground surface down to the static water table inside an observation well.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '6px' }}>
                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', color: '#22c55e', fontSize: '12px', fontWeight: 600 }}>
                    <IconDroplet size={14} />
                    <span>Smaller Depth Number = Shallower Water</span>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    A reading of <code className="font-mono">4.5 m bgl</code> means the water table is only 4.5 metres under the surface. Water is accessible with shallow pumps and open dug wells.
                  </p>
                </div>

                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', color: '#f59e0b', fontSize: '12px', fontWeight: 600 }}>
                    <IconAlert size={14} />
                    <span>Larger Depth Number = Deeper Water</span>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    A reading of <code className="font-mono">22.0 m bgl</code> means groundwater is 22 metres deep. Tubewells must be drilled significantly deeper, requiring submersible pumps and higher power.
                  </p>
                </div>
              </div>
            </div>

            {/* How Government Observation Wells Work */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Central Ground Water Board (CGWB) Observation Wells
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--color-secondary)', lineHeight: 1.6 }}>
                The Central Ground Water Board (CGWB) and state groundwater departments maintain a national network of monitoring stations comprising dug wells, piezometers, and Digital Water Level Recorders (DWLR):
              </p>
              <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', color: 'var(--color-secondary)' }}>
                <li>
                  <strong style={{ color: 'var(--color-primary)' }}>Static Water Level:</strong> Readings are taken when the well is idle (no active pumping nearby) to measure the true hydrostatic water table rather than localized pumping cones.
                </li>
                <li>
                  <strong style={{ color: 'var(--color-primary)' }}>Annual Pre-Monsoon Survey (April/May):</strong> The most crucial survey of the hydrological year. It captures the aquifer at its seasonal lowest level (maximum drawdown) before monsoon replenishment.
                </li>
                <li>
                  <strong style={{ color: 'var(--color-primary)' }}>Annual Post-Monsoon Survey (November):</strong> Captures the aquifer at its seasonal peak replenishment after monsoon infiltration.
                </li>
              </ul>
            </div>

            {/* Navigation Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>Step 1 of 6</span>
              <button className="btn btn-primary btn-sm" onClick={goToNext}>
                Next: Trend Analysis <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
              </button>
            </div>
          </article>
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 2: GROUNDWATER TREND ANALYSIS
            ═════════════════════════════════════════════════════════════════════ */}
        {activeSection === 'trends' && (
          <article className="as-card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <span className="eyebrow">Section 2</span>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Groundwater Trend Analysis
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
                Multi-year dry season measurements, physical fluctuations, and missing observation policies.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Multi-Year Trend Evaluation
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--color-secondary)', lineHeight: 1.6 }}>
                Groundwater trends cannot be evaluated from short-term fluctuations because rainfall causes temporary seasonal swings.
                JalDrishti analyzes annual pre-monsoon observations over 5-year and 32-year windows to identify structural aquifer trajectory:
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#ef4444', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Increasing Depth (Water Falling)
                  </div>
                  <div className="font-mono" style={{ fontSize: '12px', color: 'var(--color-primary)', marginBottom: '6px' }}>
                    h_2025 (12.6m) &gt; h_2020 (9.8m)
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    Groundwater depth increased by +2.8m. The water table dropped deeper underground, indicating extraction exceeded cumulative replenishment.
                  </p>
                </div>

                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#22c55e', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Decreasing Depth (Water Rising)
                  </div>
                  <div className="font-mono" style={{ fontSize: '12px', color: 'var(--color-primary)', marginBottom: '6px' }}>
                    h_2025 (8.2m) &lt; h_2020 (11.4m)
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    Groundwater depth decreased by -3.2m. The water table recovered closer to the surface, indicating favorable monsoon recharge or reduced pumping.
                  </p>
                </div>
              </div>
            </div>

            {/* Missing Data Policy */}
            <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', color: 'var(--color-primary)', fontSize: '13px', fontWeight: 600 }}>
                <IconCheck size={14} style={{ color: '#22c55e' }} />
                <span>Missing Observation Policy: Verifiable Gaps, Zero Fabrication</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                Historical field records occasionally contain years where a well was dry, inaccessible, or unmonitored.
                Unlike platforms that silently interpolate fabricated numbers, JalDrishti displays survey gaps as distinct dashed line segments on hydrographs and alerts the user explicitly.
              </p>
            </div>

            {/* Expandable WTF Formula Section */}
            <div>
              <button
                className="accordion-toggle"
                onClick={() => toggleDetail('wtfMath')}
              >
                <span>Technical Details: Water Table Fluctuation (WTF) Formulation</span>
                {expandedDetails.wtfMath ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
              </button>

              {expandedDetails.wtfMath && (
                <div className="accordion-body">
                  <p style={{ marginBottom: '8px' }}>
                    The statutory Water Table Fluctuation (WTF) methodology estimates net monsoon recharge (R)
                    by multiplying seasonal water rise (&Delta;h) by the formation specific yield (S<sub>y</sub>) and assessment unit area (A):
                  </p>
                  <div className="method-math-block">
                    R = &Delta;h &times; S_y &times; A
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
                    <div><code>&Delta;h = h_pre - h_post</code> : Seasonal water table fluctuation between May and November (m)</div>
                    <div><code>S_y</code> : Specific yield of unconfined aquifer (0.015 to 0.03 for weathered granite/gneiss hard rock)</div>
                    <div><code>A</code> : Assessment unit area (km&sup2;)</div>
                  </div>
                </div>
              )}
            </div>

            {/* Navigation Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <button className="btn btn-secondary btn-sm" onClick={goToPrev}>
                <IconArrowLeft size={13} style={{ marginRight: '4px' }} /> Previous
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>Step 2 of 6</span>
                <button className="btn btn-primary btn-sm" onClick={goToNext}>
                  Next: Resource Classification <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
                </button>
              </div>
            </div>
          </article>
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 3: GROUNDWATER RESOURCE CLASSIFICATION
            ═════════════════════════════════════════════════════════════════════ */}
        {activeSection === 'classification' && (
          <article className="as-card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <span className="eyebrow">Section 3</span>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Groundwater Resource Classification
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
                Distinguishing project-specific depth screening from official statutory GEC-2015 methodology.
              </p>
            </div>

            <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', color: '#f59e0b', fontSize: '13px', fontWeight: 600 }}>
                <IconAlert size={14} />
                <span>Essential Scientific Distinction</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                Depth screening and statutory GEC-2015 assessment are two distinct concepts.
                A single observation well depth reading does NOT make an entire aquifer officially Safe, Critical, or Over-Exploited.
                Official statutory assessments require unit-wide extraction accounting across all wells.
              </p>
            </div>

            {/* Part A: Project-Specific Depth Screening */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="eyebrow" style={{ margin: 0 }}>Part A · Well-Level Heuristic</span>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
                  JalDrishti Depth Screening Bands
                </h3>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px' }}>
                    <StatusSymbol status="safe" size={10} fill="#22c55e" />
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#22c55e' }}>Safe Band</span>
                  </div>
                  <div className="font-mono" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>&lt; 8.00 m bgl</div>
                  <p style={{ fontSize: '11px', color: 'var(--text-subtle)', lineHeight: 1.4 }}>Shallow static water table accessible by open wells and centrifugal pumps.</p>
                </div>

                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px' }}>
                    <StatusSymbol status="semi_critical" size={10} fill="#f59e0b" />
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#f59e0b' }}>Semi-Critical</span>
                  </div>
                  <div className="font-mono" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>8.00 – 15.00 m</div>
                  <p style={{ fontSize: '11px', color: 'var(--text-subtle)', lineHeight: 1.4 }}>Moderate depth; standard submersible equipment required.</p>
                </div>

                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px' }}>
                    <StatusSymbol status="critical" size={10} fill="#f97316" />
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#f97316' }}>Critical Band</span>
                  </div>
                  <div className="font-mono" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>15.00 – 25.00 m</div>
                  <p style={{ fontSize: '11px', color: 'var(--text-subtle)', lineHeight: 1.4 }}>Significant multi-year extraction deficit registered.</p>
                </div>

                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px' }}>
                    <StatusSymbol status="over_exploited" size={10} fill="#ef4444" />
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#ef4444' }}>Over-Exploited</span>
                  </div>
                  <div className="font-mono" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>&gt; 25.00 m bgl</div>
                  <p style={{ fontSize: '11px', color: 'var(--text-subtle)', lineHeight: 1.4 }}>Severe water table depression with acute drying risk.</p>
                </div>
              </div>
            </div>

            {/* Part B: Official GEC-2015 Methodology */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="eyebrow" style={{ margin: 0 }}>Part B · Statutory Benchmark</span>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
                  Official Central Ground Water Board GEC-2015 Framework
                </h3>
              </div>

              <div className="method-math-block">
                Stage of Groundwater Extraction (SOE %) =<br />
                (Annual Gross Groundwater Draft for All Uses / Annual Extractable Resource) &times; 100
              </div>

              <div className="table-responsive-wrapper">
                <table className="accessible-station-table">
                  <thead>
                    <tr>
                      <th>Official Category</th>
                      <th>Stage of Extraction (SOE)</th>
                      <th>Long-Term Trend</th>
                      <th>Assessment Scope</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>Safe</strong></td>
                      <td className="font-mono">&le; 70%</td>
                      <td>No significant long-term decline</td>
                      <td>Entire Taluk / Watershed</td>
                    </tr>
                    <tr>
                      <td><strong>Semi-Critical</strong></td>
                      <td className="font-mono">&gt; 70% to 90%</td>
                      <td>Decline in pre- or post-monsoon</td>
                      <td>Entire Taluk / Watershed</td>
                    </tr>
                    <tr>
                      <td><strong>Critical</strong></td>
                      <td className="font-mono">&gt; 90% to 100%</td>
                      <td>Decline in both pre and post-monsoon</td>
                      <td>Entire Taluk / Watershed</td>
                    </tr>
                    <tr>
                      <td><strong>Over-Exploited</strong></td>
                      <td className="font-mono">&gt; 100%</td>
                      <td>Significant long-term decline in both</td>
                      <td>Entire Taluk / Watershed</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Navigation Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <button className="btn btn-secondary btn-sm" onClick={goToPrev}>
                <IconArrowLeft size={13} style={{ marginRight: '4px' }} /> Previous
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>Step 3 of 6</span>
                <button className="btn btn-primary btn-sm" onClick={goToNext}>
                  Next: AI Forecasting <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
                </button>
              </div>
            </div>
          </article>
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 4: AI FORECASTING
            ═════════════════════════════════════════════════════════════════════ */}
        {activeSection === 'forecasting' && (
          <article className="as-card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <span className="eyebrow">Section 4</span>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-primary)' }}>
                AI Groundwater Level Forecasting
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
                Predictive regression modeling, annual cadence, uncertainty intervals, and physical bounds.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Prediction Target &amp; Hydrogeological Temporal Structure
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--color-secondary)', lineHeight: 1.6 }}>
                JalDrishti predicts static groundwater depth in metres below ground level (m bgl) for verified CGWB observation wells.
                Because aquifers possess multi-year hydrological memory, models learn temporal autoregressive structure from 32 years of historical pre-monsoon surveys (1994–2025).
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginTop: '6px' }}>
                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <span className="eyebrow">Target Metric</span>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-primary)' }}>Pre-Monsoon Depth</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px' }}>m below ground level</div>
                </div>
                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <span className="eyebrow">Forecast Target</span>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-primary)' }}>2026 Cycle</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px' }}>Annual validation year</div>
                </div>
                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <span className="eyebrow">Telemetry Cadence</span>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-primary)' }}>Annual Pre-Monsoon</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px' }}>May field surveys</div>
                </div>
                <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '12px' }}>
                  <span className="eyebrow">Uncertainty</span>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-primary)' }}>&plusmn;4.98 m</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px' }}>90th %ile residuals</div>
                </div>
              </div>
            </div>

            {/* Expandable Model Details & Benchmarks */}
            <div>
              <button
                className="accordion-toggle"
                onClick={() => toggleDetail('aiModel')}
              >
                <span>Technical Details: Multi-Lag Formulation &amp; Benchmark Performance</span>
                {expandedDetails.aiModel ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
              </button>

              {expandedDetails.aiModel && (
                <div className="accordion-body">
                  <p style={{ marginBottom: '8px' }}>
                    The deployed production model utilizes multi-lag autoregressive regression over 28,544 station-years:
                  </p>
                  <div className="method-math-block">
                    y_hat_t = &beta;_0 + &beta;_1 y_{`{t-1}`} + &beta;_2 y_{`{t-2}`} + &beta;_3 y_{`{t-3}`} + &beta;_4 Latitude + &beta;_5 Longitude
                  </div>

                  <div className="table-responsive-wrapper" style={{ marginTop: '12px' }}>
                    <table className="accessible-station-table">
                      <thead>
                        <tr>
                          <th>Model Architecture</th>
                          <th style={{ textAlign: 'right' }}>MAE (m)</th>
                          <th style={{ textAlign: 'right' }}>RMSE (m)</th>
                          <th style={{ textAlign: 'right' }}>R&sup2; Score</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td><strong>Linear Multi-Lag OLS</strong></td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>1.48 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>2.37 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>0.81</td>
                          <td><span className="status-badge badge-safe">Deployed</span></td>
                        </tr>
                        <tr>
                          <td>Deep LSTM Sequence Network</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>1.39 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>2.21 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>0.84</td>
                          <td><span className="status-badge badge-unknown">Benchmark</span></td>
                        </tr>
                        <tr>
                          <td>Random Forest Regressor</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>1.52 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>2.45 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>0.79</td>
                          <td><span className="status-badge badge-unknown">Benchmark</span></td>
                        </tr>
                        <tr>
                          <td>Persistence (Lag-1 Baseline)</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>1.84 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>2.89 m</td>
                          <td className="font-mono" style={{ textAlign: 'right' }}>0.72</td>
                          <td><span className="status-badge badge-unknown">Baseline</span></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Navigation Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <button className="btn btn-secondary btn-sm" onClick={goToPrev}>
                <IconArrowLeft size={13} style={{ marginRight: '4px' }} /> Previous
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>Step 4 of 6</span>
                <button className="btn btn-primary btn-sm" onClick={goToNext}>
                  Next: Data Sources <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
                </button>
              </div>
            </div>
          </article>
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 5: DATA SOURCES & RELIABILITY
            ═════════════════════════════════════════════════════════════════════ */}
        {activeSection === 'provenance' && (
          <article className="as-card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <span className="eyebrow">Section 5</span>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Data Sources &amp; Telemetry Provenance
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
                Reconciliation between 390 verified Karnataka CGWB observation wells and 78 national benchmark nodes.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span className="provenance-tag-hist">Verified Series</span>
                  <span className="font-mono" style={{ fontSize: '13px', fontWeight: 600, color: '#22c55e' }}>390 Wells</span>
                </div>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)', margin: '0 0 6px 0' }}>
                  Verified Karnataka CGWB Network
                </h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                  Authentic government observation wells across all 31 districts of Karnataka with 32 years of continuous pre-monsoon surveys (1994–2025).
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '11px', color: 'var(--text-subtle)' }}>
                  <div>✓ Actual surveyed latitude &amp; longitude coordinates</div>
                  <div>✓ Continuous 5-year and 32-year hydrograph records</div>
                  <div>✓ Verified AI regression forecasts available</div>
                </div>
              </div>

              <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span className="provenance-tag-bench">Calibration Reference</span>
                  <span className="font-mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>78 Nodes</span>
                </div>
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)', margin: '0 0 6px 0' }}>
                  National Benchmark Reference Nodes
                </h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                  Calibrated benchmark fallback stations (3 per state across 26 states/UTs) generated to validate national GIS map projection and multi-state UI continuity.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '11px', color: 'var(--text-subtle)' }}>
                  <div>• Placed at approximate district/state centroid coordinates</div>
                  <div>• Synthetic calibration baseline; no continuous historical series</div>
                  <div>• Clear disclosure tags displayed on table &amp; drawer</div>
                </div>
              </div>
            </div>

            <div style={{ background: '#000000', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', color: 'var(--color-primary)', fontSize: '13px', fontWeight: 600 }}>
                <IconCheck size={14} style={{ color: '#22c55e' }} />
                <span>Reconciled Database Inventory: Exactly 468 Stations</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                390 verified Karnataka series + 78 synthetic benchmark nodes = 468 total database stations. Every station record explicitly indicates its provenance tag.
              </p>
            </div>

            {/* Navigation Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <button className="btn btn-secondary btn-sm" onClick={goToPrev}>
                <IconArrowLeft size={13} style={{ marginRight: '4px' }} /> Previous
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>Step 5 of 6</span>
                <button className="btn btn-primary btn-sm" onClick={goToNext}>
                  Next: Geospatial Mapping <IconArrowRight size={13} style={{ marginLeft: '4px' }} />
                </button>
              </div>
            </div>
          </article>
        )}

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 6: MAP & GEOGRAPHIC ACCURACY
            ═════════════════════════════════════════════════════════════════════ */}
        {activeSection === 'mapping' && (
          <article className="as-card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <span className="eyebrow">Section 6</span>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Geospatial Mapping &amp; Projection Calibration
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
                Official Indian state boundary vectors, coordinate transformation mathematics, and ground-truth validation.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--color-primary)' }}>
                Conformal Web Mercator Projection Transformation
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--color-secondary)', lineHeight: 1.6 }}>
                The interactive map uses the official <code>india_map_with_state_borders.svg</code> vector layer.
                Geographic coordinates (latitude &phi; and longitude &lambda;) are converted into the 1000 &times; 1000 SVG viewBox using calibrated conformal projection formulas:
              </p>
              <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', color: 'var(--color-secondary)' }}>
                <li>
                  <strong style={{ color: 'var(--color-primary)' }}>Coordinate Order:</strong> Strict enforcement of (longitude, latitude) prevents axis transposition.
                </li>
                <li>
                  <strong style={{ color: 'var(--color-primary)' }}>Landmark Ground-Truth:</strong> Validated against known physical reference wells, such as Ferozabad, Kalaburagi (17.0833&deg;N, 76.7958&deg;E &rarr; SVG: 334.7, 723.1).
                </li>
                <li>
                  <strong style={{ color: 'var(--color-primary)' }}>Boundary Containment:</strong> Achieves 93.8% polygon containment across all 34 state vector paths without distortion.
                </li>
              </ul>
            </div>

            {/* Expandable Mercator Math */}
            <div>
              <button
                className="accordion-toggle"
                onClick={() => toggleDetail('mercatorMath')}
              >
                <span>Technical Details: Projection Transformation Equations</span>
                {expandedDetails.mercatorMath ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
              </button>

              {expandedDetails.mercatorMath && (
                <div className="accordion-body">
                  <p style={{ marginBottom: '8px' }}>
                    The projection evaluates conformal Mercator isometric latitude y_merc, then scales and translates into SVG coordinates:
                  </p>
                  <div className="method-math-block">
                    y_merc = ln( tan( &pi; / 4 + (&phi; &times; &pi; / 360) ) )<br /><br />
                    SVG_X = 27.31481 &times; &lambda; - 1762.88855<br />
                    SVG_Y = 1138.53371 - 1565.02338 &times; y_merc
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
                    <div><code>&lambda;</code> : Station longitude in decimal degrees east (e.g. 76.7958&deg;E)</div>
                    <div><code>&phi;</code> : Station latitude in decimal degrees north (e.g. 17.0833&deg;N)</div>
                    <div><code>SVG_X, SVG_Y</code> : Target coordinate within 1000 &times; 1000 SVG canvas</div>
                  </div>
                </div>
              )}
            </div>

            {/* Navigation Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
              <button className="btn btn-secondary btn-sm" onClick={goToPrev}>
                <IconArrowLeft size={13} style={{ marginRight: '4px' }} /> Previous
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>Step 6 of 6</span>
                <button className="btn btn-secondary btn-sm" onClick={() => window.scrollTo({ top: 80, behavior: 'smooth' })}>
                  Back to Top
                </button>
              </div>
            </div>
          </article>
        )}
      </main>
    </div>
  );
}
