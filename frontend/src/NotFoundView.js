import React from 'react';
import { IconHome, IconMap, IconTable } from './icons';

export default function NotFoundView({ onNavigate }) {
  return (
    <div className="not-found-page" role="main" aria-label="Page Not Found">
      <div className="not-found-code">404</div>
      <h1 className="not-found-title">Aquifer Node Not Found</h1>
      <p className="not-found-desc">
        The requested observation route or station telemetry coordinates could not be resolved in the national groundwater registry. The aquifer telemetry node may have been decommissioned or the URL path may be inaccurate.
      </p>
      <div className="not-found-actions">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => onNavigate('overview')}
          aria-label="Return to National Overview"
        >
          <IconHome size={14} style={{ marginRight: '6px' }} />
          Return to National Overview
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onNavigate('map')}
          aria-label="Open Interactive Groundwater Map"
        >
          <IconMap size={14} style={{ marginRight: '6px' }} />
          Open Groundwater Map
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onNavigate('stations')}
          aria-label="Open Monitoring Wells Directory"
        >
          <IconTable size={14} style={{ marginRight: '6px' }} />
          Monitoring Stations Directory
        </button>
      </div>
    </div>
  );
}
