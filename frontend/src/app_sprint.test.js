// JalDrishti 20-Point Front-End Refinement Test Suite
// Standard Node/Jest test without external test-library dependencies

const React = require('react');
const ReactDOMServer = require('react-dom/server');
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const NotFoundView = require('./NotFoundView').default;
const ApplicationFooter = require('./ApplicationFooter').default;

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
});
