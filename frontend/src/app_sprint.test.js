// JalDrishti 20-Point Front-End Refinement Test Suite
// Standard Node/Jest test without external test-library dependencies

const React = require('react');
const ReactDOMServer = require('react-dom/server');
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const NotFoundView = require('./NotFoundView').default;
const ApplicationFooter = require('./ApplicationFooter').default;
const UnifiedOverview = require('./UnifiedOverview').default;
const AIForecastModule = require('./AIForecastPanel');
const AIForecastPanel = AIForecastModule.default;
const { ForecastTimeSeriesChart, getBaselineAndDisplacement, getOperationalDepthBand } = AIForecastModule;

describe('JalDrishti 20-Point Front-End Refinement Tests', () => {
  test('Item 4: Favicon files exist and are valid sizes in public directory', () => {
    const pubDir = path.resolve(__dirname, '../public');
    const svgFavicon = path.join(pubDir, 'favicon.svg');
    const icoFavicon = path.join(pubDir, 'favicon.ico');

    assert(fs.existsSync(svgFavicon), 'favicon.svg must exist in public directory');
    assert(fs.existsSync(icoFavicon), 'favicon.ico must exist in public directory');

    const svgContent = fs.readFileSync(svgFavicon, 'utf8');
    assert(svgContent.includes('<svg'), 'favicon.svg must be a valid SVG document');

    const icoStats = fs.statSync(icoFavicon);
    assert(icoStats.size > 100, 'favicon.ico must be a valid binary file');
  });

  test('Item 8: Custom 404 NotFoundView renders correctly with return triggers', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(NotFoundView, { onNavigate: () => {} })
    );

    assert(html.includes('404'), 'Must mention 404');
    assert(html.includes('Aquifer Node Not Found'), 'Must display custom aquifer 404 title');
    assert(html.includes('Return to National Overview'), 'Must have Return to Overview button');
    assert(html.includes('Open Groundwater Map'), 'Must have Open Groundwater Map button');
  });

  test('Items 7, 9, 18, 19: ApplicationFooter renders clickable phone, email, and 2026 copyright', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(ApplicationFooter, { onNavigate: () => {}, activeTab: 'overview' })
    );

    // Dynamic current year (2026)
    const currentYear = new Date().getFullYear().toString();
    assert(html.includes(currentYear), `Footer must render current year ${currentYear}`);
    assert(html.includes('Abhishek Jayagond'), 'Footer must attribute Abhishek Jayagond');

    // Clickable phone number (+91 94495 12887)
    assert(html.includes('href="tel:+919449512887"'), 'Phone must be clickable with tel:+919449512887 URI');
    assert(html.includes('+91 94495 12887'), 'Phone number text +91 94495 12887 must be visible');

    // Clickable email
    assert(html.includes('href="mailto:abhishekjayagond@gmail.com"'), 'Email must be clickable with mailto: URI');
    assert(html.includes('abhishekjayagond@gmail.com'), 'Email text must be visible');

    // All 6 Navigation items
    assert(html.includes('Overview Dashboard'), 'Must contain Overview');
    assert(html.includes('Groundwater Map'), 'Must contain Groundwater Map');
    assert(html.includes('Monitoring Stations'), 'Must contain Monitoring Stations');
    assert(html.includes('AI Forecast Panel'), 'Must contain AI Forecast');
    assert(html.includes('Depletion Alerts'), 'Must contain Depletion Alerts');
    assert(html.includes('CGWB Methodology'), 'Must contain CGWB Methodology');

    // Authoritative sources
    assert(html.includes('https://cgwb.gov.in/'), 'Must link to CGWB');
    assert(html.includes('https://indiawris.gov.in/'), 'Must link to India-WRIS');
    assert(html.includes('https://imdaws.imd.gov.in/'), 'Must link to IMD');
  });

  test('Item 10: Compressed image sizes verified', () => {
    const outlineSvg = path.resolve(__dirname, 'assets/India_outline.svg');
    assert(fs.existsSync(outlineSvg), 'India_outline.svg must exist');
    const outlineStats = fs.statSync(outlineSvg);
    assert(outlineStats.size < 8000, `India_outline.svg must be compressed (got ${outlineStats.size} bytes, expected < 8000)`);
  });

  test('Item 14 & 15: No placeholder dummy text in public HTML', () => {
    const indexHtml = fs.readFileSync(path.resolve(__dirname, '../public/index.html'), 'utf8');
    assert(!indexHtml.includes('Lorem ipsum'), 'index.html must not contain Lorem ipsum');
    assert(!indexHtml.includes('TODO'), 'index.html must not contain TODO');
  });

  test('Overview: Renders depth distribution, structured screening metric, and populated station lookup', () => {
    const mockStations = [
      { station_id: 's1', station_name: 'Station 1', state: 'Karnataka', district: 'Bengaluru', block: 'North', current_level_m: 5.2, predicted_depth_m: 5.2, data_provenance: 'historical_annual', status: 'safe' },
      { station_id: 's2', station_name: 'Station 2', state: 'Karnataka', district: 'Mysuru', block: 'South', current_level_m: 12.1, predicted_depth_m: 12.1, data_provenance: 'historical_annual', status: 'semi_critical' },
      { station_id: 's3', station_name: 'Station 3', state: 'Maharashtra', district: 'Pune', block: 'Central', current_level_m: 32.0, predicted_depth_m: null, data_provenance: 'benchmark_telemetry', status: 'over_exploited' },
    ];

    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(UnifiedOverview, {
        stations: mockStations,
        selectedStation: null,
        onSelectStation: () => {},
        loadingStations: false,
        onNavigate: () => {},
      })
    );

    // 1. Chart title and depth bands
    assert(html.includes('Operational Groundwater Depth Distribution'), 'Chart heading must be visible');
    assert(html.includes('0–8 m bgl'), '0–8 m bgl band must be present');
    assert(html.includes('8–15 m bgl'), '8–15 m bgl band must be present');
    assert(html.includes('15–25 m bgl'), '15–25 m bgl band must be present');
    assert(html.includes('Greater than 25 m bgl'), 'Greater than 25 m bgl band must be present in chart');
    assert(html.includes('&gt;25 m bgl') || html.includes('>25 m bgl'), '>25 m bgl badge must be present on summary card');

    // 2. Structured Screening Metric Card
    assert(html.includes('screening-metric-card'), 'Screening Metric Card must be present');
    assert(html.includes('Screening Metric'), 'Screening Metric label must be present');
    assert(html.includes('Mean Depth'), 'Mean Depth label must be present');
    assert(html.includes('m bgl'), 'm bgl unit must be present');
    assert(html.includes('390 evaluated field stations'), '390 evaluated field stations must be present');

    // 3. Station lookup area
    assert(html.includes('Inspect Specific Monitoring Well'), 'Station lookup header must be present');
    assert(html.includes('Station 1'), 'Real station 1 must be rendered');
    assert(html.includes('Station 2'), 'Real station 2 must be rendered');
    assert(html.includes('Station 3'), 'Real station 3 must be rendered');
    assert(html.includes('Bengaluru, Karnataka'), 'Administrative location must be rendered');
  });

  test('Overview: Renders loading state when loadingStations is true and stations are empty', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(UnifiedOverview, {
        stations: [],
        selectedStation: null,
        onSelectStation: () => {},
        loadingStations: true,
        onNavigate: () => {},
      })
    );

    assert(html.includes('Loading monitoring station telemetry...'), 'Must render loading telemetry indicator');
  });

  test('Forecast: Baseline & displacement handles valid 2025 and missing 2025 safely without NaNs', () => {
    // Case 1: Valid 2025 observation present
    const historyWith2025 = [
      { date: '1994-05-25', avg_level_m: 10.60 },
      { date: '2024-05-10', avg_level_m: 11.00 },
      { date: '2025-05-25', avg_level_m: 10.97 },
    ];
    const res1 = getBaselineAndDisplacement(historyWith2025, 10.32);
    assert.strictEqual(res1.baselineValue, 10.97, 'Baseline value must be 10.97');
    assert.strictEqual(res1.baselineYear, 2025, 'Baseline year must be 2025');
    assert.strictEqual(res1.displacement, -0.65, 'Net displacement must be -0.65 m');
    assert.strictEqual(res1.status, 'valid_2025', 'Status must be valid_2025');

    // Case 2: Missing 2025 observation (ended in 2023)
    const historyWithout2025 = [
      { date: '1994-05-25', avg_level_m: 8.50 },
      { date: '2023-05-01', avg_level_m: 9.20 },
    ];
    const res2 = getBaselineAndDisplacement(historyWithout2025, 10.32);
    assert.strictEqual(res2.baselineValue, 9.20, 'Baseline value must be 9.20');
    assert.strictEqual(res2.baselineYear, 2023, 'Baseline year must be 2023');
    assert.strictEqual(res2.displacement, null, 'Displacement must be null when 2025 is missing');
    assert.strictEqual(res2.status, 'prior_year', 'Status must be prior_year');
    assert(!String(res2.baselineValue).includes('NaN'), 'Must never return NaN');

    // Case 3: Empty history
    const res3 = getBaselineAndDisplacement([], 10.32);
    assert.strictEqual(res3.baselineValue, null, 'Empty history must yield null baseline');
    assert.strictEqual(res3.displacement, null, 'Empty history must yield null displacement');
    assert.strictEqual(res3.status, 'unavailable', 'Status must be unavailable');

    // Case 4: Null forecast depth
    const res4 = getBaselineAndDisplacement(historyWith2025, null);
    assert.strictEqual(res4.displacement, null, 'Displacement must be null if forecast is null');
  });

  test('Forecast: Operational depth bands are point-level screening metrics without administrative labels', () => {
    const shallow = getOperationalDepthBand(5.2);
    assert.strictEqual(shallow.band, '0–8 m bgl');
    assert(shallow.label.includes('0–8 m bgl'));
    assert(!shallow.label.includes('Safe Category'), 'Must not use administrative category labels');

    const moderate = getOperationalDepthBand(10.32);
    assert.strictEqual(moderate.band, '8–15 m bgl');
    assert(moderate.label.includes('8–15 m bgl'));

    const deep = getOperationalDepthBand(18.5);
    assert.strictEqual(deep.band, '15–25 m bgl');
    assert(deep.label.includes('15–25 m bgl'));

    const veryDeep = getOperationalDepthBand(29.1);
    assert.strictEqual(veryDeep.band, 'Greater than 25 m bgl');
    assert(veryDeep.label.includes('Greater than 25 m bgl'));

    const unavail = getOperationalDepthBand(null);
    assert.strictEqual(unavail.band, 'Unavailable');
  });

  test('Forecast: ForecastTimeSeriesChart renders inverted depth axis, separated 2025/2027 ticks, and high-contrast markers', () => {
    const mockHistory = [
      { date: '1995-05-25', avg_level_m: 10.6 },
      { date: '2000-05-25', avg_level_m: 10.2 },
      { date: '2005-05-25', avg_level_m: 14.1 },
      { date: '2010-05-25', avg_level_m: 11.6 },
      { date: '2015-05-25', avg_level_m: 10.2 },
      { date: '2020-05-25', avg_level_m: 9.8 },
      { date: '2025-05-25', avg_level_m: 10.97 },
    ];
    const mockForecast = {
      forecast_year: 2026,
      forecast_mbgl: 10.32,
      multi_year_projections: [
        { target_year: 2026, predicted_depth_mbgl: 10.32 },
        { target_year: 2027, predicted_depth_mbgl: 10.26 },
      ],
    };

    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(ForecastTimeSeriesChart, {
        historyPoints: mockHistory,
        forecast: mockForecast,
        targetYear: 2027,
        targetType: 'future_projection',
        predictedValue: 10.26,
      })
    );

    // 1. Heading terminology
    assert(html.includes('Water Level History &amp; 2027 Projection'), 'Chart must render 2027 projection heading');

    // 2. Physical depth axis convention
    assert(html.includes('Groundwater depth (m bgl)'), 'Depth axis must be labeled Groundwater depth (m bgl)');

    // 3. 2025 observation tick and 2027 projection annotation
    assert(html.includes('2025 (Measured)'), '2025 (Measured) tick must be present');
    assert(html.includes('2027 Projection'), '2027 Projection top badge must be present');

    // 4. Forecast annotation badge
    assert(html.includes('10.26 m'), 'Forecast annotation badge must display 10.26 m');

    // 5. High-contrast marker colors
    assert(html.includes('fill="#ffffff"'), 'Observed data markers must be high-contrast white');
    assert(html.includes('fill="#f59e0b"'), 'Forecast marker must be distinct amber');
    assert(!html.includes('NaN'), 'Chart must never render NaN');
  });

  test('Forecast: AIForecastPanel renders simplified farmer view with 3 primary sections and collapsed advanced details', () => {
    const html = ReactDOMServer.renderToStaticMarkup(
      React.createElement(AIForecastPanel, {
        selectedStation: {
          station_id: '0098c762f561',
          station_name: 'Ferozabad Monitoring Well',
          village: 'Ferozabad',
          block: 'Kalaburagi',
          district: 'Kalaburagi',
          state: 'Karnataka',
          latitude: 17.0833,
          longitude: 76.7958,
          data_provenance: 'historical_annual',
        },
        onSelectStation: () => {},
        onToast: () => {},
      })
    );

    // 1. Section 1: Header and location selection
    assert(html.includes('Groundwater Forecast for Farmers'), 'Page title must be rendered in farmer-friendly language');
    assert(html.includes('Estimated groundwater depth for your selected location.'), 'Farmer subtitle must be present');
    assert(html.includes('Ferozabad Monitoring Well'), 'Selected well name must be rendered');
    assert(html.includes('Kalaburagi District'), 'District must be rendered');
    assert(html.includes('Data source: Central Ground Water Board (CGWB) records'), 'Data source indicator must be present');

    // 2. Section 2 & 3: Farmer-friendly terminology and collapsed details
    assert(html.includes('Advanced Details &amp; Scientific Methodology'), 'Collapsed advanced details must be present');
    assert(!html.includes('NaN m'), 'Page must never render NaN m');
    assert(!html.includes('undefined'), 'Page must never render undefined');
    assert(!html.includes('Autoregressive projections for verified CGWB'), 'Technical jargon must not be in primary view');
  });

  test('Drawer Removal: No right-side station detail popup or drawer exists; station details render inline', () => {
    const mockStation = {
      station_id: '0098c762f561',
      station_name: 'Ferozabad Monitoring Well',
      village: 'Ferozabad',
      block: 'Kalaburagi',
      district: 'Kalaburagi',
      state: 'Karnataka',
      current_level_m: 10.97,
      predicted_depth_m: 10.26,
      data_provenance: 'historical_annual',
      status: 'semi_critical',
    };

    // Render Overview with selectedStation
    const overviewHtml = ReactDOMServer.renderToStaticMarkup(
      React.createElement(UnifiedOverview, {
        stations: [mockStation],
        selectedStation: mockStation,
        onSelectStation: () => {},
        loadingStations: false,
        onNavigate: () => {},
      })
    );

    // Verify Overview renders inline information without drawer
    assert(overviewHtml.includes('Ferozabad Monitoring Well'), 'Overview must render selected station name inline');
    assert(overviewHtml.includes('Kalaburagi'), 'Overview must render selected district inline');
    assert(!overviewHtml.includes('station-dossier-drawer'), 'Overview must never render right-side station drawer');
    assert(!overviewHtml.includes('sdd-close-btn'), 'Overview must never render drawer close button');

    // Render Forecast with selectedStation
    const forecastHtml = ReactDOMServer.renderToStaticMarkup(
      React.createElement(AIForecastPanel, {
        selectedStation: mockStation,
        onSelectStation: () => {},
        onToast: () => {},
      })
    );

    // Verify Forecast communicates selected station via existing location selector without extra drawer
    assert(forecastHtml.includes('Ferozabad'), 'Forecast must display selected station in location selector');
    assert(!forecastHtml.includes('station-dossier-drawer'), 'Forecast must never render right-side station drawer');
    assert(!forecastHtml.includes('sdd-close-btn'), 'Forecast must never render drawer close button');
  });
});
