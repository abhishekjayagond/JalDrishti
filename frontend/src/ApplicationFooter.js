import React from 'react';
import {
  IconPhone,
  IconMail,
  IconExternal
} from './icons';

export default function ApplicationFooter({ onNavigate, activeTab }) {
  const currentYear = new Date().getFullYear();

  const handleNavClick = (tabId) => {
    if (onNavigate) {
      onNavigate(tabId);
    }
    try {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) {
      window.scrollTo(0, 0);
    }
  };

  return (
    <footer className="app-footer" role="contentinfo" aria-label="JalDrishti Site Footer">
      <div className="footer-grid">
        {/* Column 1: Brand & Overview */}
        <div className="footer-brand-col">
          <div
            className="brand-section"
            role="button"
            tabIndex={0}
            onClick={() => handleNavClick('overview')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleNavClick('overview');
              }
            }}
            style={{ cursor: 'pointer', margin: 0 }}
            title="Return to National Overview"
          >
            <span className="brand-title">JalDrishti</span>
          </div>
          <p className="footer-brand-desc">
            National Groundwater Intelligence &amp; AI Forecasting Platform. Engineered by Abhishek Jayagond to deliver real-time aquifer telemetry, water table fluctuation modeling, and dynamic recharge assessments across India.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-subtle)' }}>
            <span className="hmc-dot" />
            <span className="font-mono">468 Observation Wells Active</span>
          </div>
        </div>

        {/* Column 2: Navigation Links */}
        <div>
          <div className="footer-col-title">Platform Navigation</div>
          <div className="footer-nav-list">
            <button
              type="button"
              className="footer-nav-link"
              onClick={() => handleNavClick('overview')}
              style={activeTab === 'overview' ? { color: 'var(--color-primary)' } : {}}
            >
              Overview Dashboard
            </button>
            <button
              type="button"
              className="footer-nav-link"
              onClick={() => handleNavClick('map')}
              style={activeTab === 'map' ? { color: 'var(--color-primary)' } : {}}
            >
              Groundwater Map
            </button>
            <button
              type="button"
              className="footer-nav-link"
              onClick={() => handleNavClick('stations')}
              style={activeTab === 'stations' ? { color: 'var(--color-primary)' } : {}}
            >
              Monitoring Stations
            </button>
            <button
              type="button"
              className="footer-nav-link"
              onClick={() => handleNavClick('forecast')}
              style={activeTab === 'forecast' ? { color: 'var(--color-primary)' } : {}}
            >
              AI Forecast Panel
            </button>
            <button
              type="button"
              className="footer-nav-link"
              onClick={() => handleNavClick('alerts')}
              style={activeTab === 'alerts' ? { color: 'var(--color-primary)' } : {}}
            >
              Depletion Alerts
            </button>
            <button
              type="button"
              className="footer-nav-link"
              onClick={() => handleNavClick('methodology')}
              style={activeTab === 'methodology' ? { color: 'var(--color-primary)' } : {}}
            >
              CGWB Methodology
            </button>
          </div>
        </div>

        {/* Column 3: Data & Guidelines */}
        <div>
          <div className="footer-col-title">Hydrogeology Data</div>
          <div className="footer-nav-list">
            <a
              href="https://cgwb.gov.in/"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-contact-link"
            >
              <span>CGWB Portal</span>
              <IconExternal size={11} style={{ opacity: 0.6 }} />
            </a>
            <a
              href="https://indiawris.gov.in/"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-contact-link"
            >
              <span>India-WRIS Water Resources</span>
              <IconExternal size={11} style={{ opacity: 0.6 }} />
            </a>
            <a
              href="https://imdaws.imd.gov.in/"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-contact-link"
            >
              <span>IMD Weather Stations</span>
              <IconExternal size={11} style={{ opacity: 0.6 }} />
            </a>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-contact-link"
            >
              <span>Telemetry API (FastAPI)</span>
              <IconExternal size={11} style={{ opacity: 0.6 }} />
            </a>
          </div>
        </div>

        {/* Column 4: Contact & Verification */}
        <div>
          <div className="footer-col-title">Project Engineering</div>
          <div className="footer-contact-list">
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Created &amp; Maintained by
              <strong style={{ display: 'block', color: 'var(--color-primary)', marginTop: '2px' }}>Abhishek Jayagond</strong>
            </div>
            <a href="mailto:abhishekjayagond@gmail.com" className="footer-contact-link">
              <IconMail size={13} />
              <span>abhishekjayagond@gmail.com</span>
            </a>
            <a href="tel:+918000000000" className="footer-contact-link">
              <IconPhone size={13} />
              <span>+91 (800) 000-0000</span>
            </a>
            <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
              Karnataka, India · CGWB Series
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bottom">
        <div className="footer-copyright">
          © {currentYear} JalDrishti. All rights reserved. Created from scratch by Abhishek Jayagond.
        </div>
        <div className="footer-legal-links">
          <button
            type="button"
            className="footer-legal-link"
            onClick={() => handleNavClick('methodology')}
          >
            Scientific Framework
          </button>
          <span style={{ color: 'var(--color-border)' }}>·</span>
          <button
            type="button"
            className="footer-legal-link"
            onClick={() => handleNavClick('overview')}
          >
            System Status
          </button>
          <span style={{ color: 'var(--color-border)' }}>·</span>
          <span className="font-mono text-xs text-subtle">v2.4.0 (SNP)</span>
        </div>
      </div>
    </footer>
  );
}
