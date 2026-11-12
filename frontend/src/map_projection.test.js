// Comprehensive Geographic Projection & Map Geometry Unit Test
// Validates: conformal Web Mercator projection for india_map_with_state_borders.svg (viewBox 0 0 1000 1000)

const assert = require('assert');

// Conformal Web Mercator projection matching india_map_with_state_borders.svg
function projectCoordinates(lat, lon) {
  if (lat == null || lon == null) return null;
  const nLat = Number(lat);
  const nLon = Number(lon);
  if (!Number.isFinite(nLat) || !Number.isFinite(nLon)) return null;
  if (nLat < 6.0 || nLat > 38.5 || nLon < 68.0 || nLon > 98.5) return null;

  const rad = (nLat * Math.PI) / 180;
  const yMerc = Math.log(Math.tan(Math.PI / 4 + rad / 2));
  const x = 27.31481 * nLon - 1762.88855;
  const y = 1138.53371 - 1565.02338 * yMerc;
  return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
}

function runAllValidationTests() {
  // Test 1: Ground-truth geographic extremities on 1000x1000 viewBox
  const extremities = [
    { name: 'Northernmost (Indira Col, Ladakh)', lat: 37.09, lon: 74.70, expBox: { minX: 260, maxX: 295, minY: 35, maxY: 60 } },
    { name: 'Southernmost (Kanyakumari, TN)', lat: 8.08, lon: 77.55, expBox: { minX: 340, maxX: 375, minY: 900, maxY: 935 } },
    { name: 'Westernmost (Ghuar Mota, Kutch, GJ)', lat: 23.71, lon: 68.12, expBox: { minX: 85, maxX: 115, minY: 455, maxY: 485 } },
    { name: 'Easternmost (Kibithu, Arunachal)', lat: 28.01, lon: 97.40, expBox: { minX: 880, maxX: 915, minY: 325, maxY: 355 } },
  ];

  for (const ext of extremities) {
    const c = projectCoordinates(ext.lat, ext.lon);
    assert(c !== null, `${ext.name} should project to valid coordinates`);
    assert(c.x >= ext.expBox.minX && c.x <= ext.expBox.maxX, `${ext.name} X (${c.x}) out of bounds`);
    assert(c.y >= ext.expBox.minY && c.y <= ext.expBox.maxY, `${ext.name} Y (${c.y}) out of bounds`);
  }

  // Test 2: Known Indian Cities & Key Benchmarks on 1000x1000 SVG
  const cities = [
    { name: 'Ferozabad, Kalaburagi (Karnataka benchmark)', lat: 17.0833, lon: 76.7958, stateBox: { minX: 320, maxX: 350, minY: 650, maxY: 680 } },
    { name: 'Bengaluru (Karnataka)', lat: 12.9716, lon: 77.5946, stateBox: { minX: 340, maxX: 375, minY: 765, maxY: 795 } },
    { name: 'New Delhi (NCT of Delhi)', lat: 28.6139, lon: 77.2090, stateBox: { minX: 335, maxX: 355, minY: 310, maxY: 335 } },
    { name: 'Mumbai (Maharashtra)', lat: 18.9067, lon: 72.8147, stateBox: { minX: 215, maxX: 240, minY: 600, maxY: 625 } },
    { name: 'Kolkata (West Bengal)', lat: 22.5726, lon: 88.3639, stateBox: { minX: 635, maxX: 665, minY: 490, maxY: 520 } },
    { name: 'Guwahati (Assam)', lat: 26.1445, lon: 91.7362, stateBox: { minX: 725, maxX: 755, minY: 390, maxY: 420 } },
    { name: 'Srinagar (J&K)', lat: 34.0837, lon: 74.7973, stateBox: { minX: 265, maxX: 295, minY: 125, maxY: 150 } },
    { name: 'Leh (Ladakh)', lat: 34.1526, lon: 77.5771, stateBox: { minX: 340, maxX: 370, minY: 120, maxY: 150 } },
    { name: 'Port Blair (Andaman)', lat: 11.6234, lon: 92.7265, stateBox: { minX: 755, maxX: 785, minY: 805, maxY: 835 } },
  ];

  for (const city of cities) {
    const c = projectCoordinates(city.lat, city.lon);
    assert(c !== null, `${city.name} should project to valid coordinates`);
    assert(c.x >= city.stateBox.minX && c.x <= city.stateBox.maxX, `${city.name} X (${c.x}) out of envelope`);
    assert(c.y >= city.stateBox.minY && c.y <= city.stateBox.maxY, `${city.name} Y (${c.y}) out of envelope`);
  }

  // Test 3: Out-of-bounds rejection
  assert.strictEqual(projectCoordinates(null, 77.5), null, 'null lat should return null');
  assert.strictEqual(projectCoordinates(12.5, null), null, 'null lon should return null');
  assert.strictEqual(projectCoordinates(5.0, 77.5), null, 'lat < 6.0 should be excluded');
  assert.strictEqual(projectCoordinates(40.0, 77.5), null, 'lat > 38.5 should be excluded');
  assert.strictEqual(projectCoordinates(12.5, 65.0), null, 'lon < 68.0 should be excluded');
  assert.strictEqual(projectCoordinates(12.5, 100.0), null, 'lon > 98.5 should be excluded');

  // Test 4: Zoom clamping and step invariants
  let zoom = 1.0;
  const zoomIn = (z) => Math.min(Number((z * 1.3).toFixed(2)), 4.5);
  const zoomOut = (z) => Math.max(Number((z / 1.3).toFixed(2)), 0.85);

  for (let i = 0; i < 10; i++) zoom = zoomIn(zoom);
  assert.strictEqual(zoom, 4.5, `Max zoom should clamp at 4.5, got ${zoom}`);

  for (let i = 0; i < 15; i++) zoom = zoomOut(zoom);
  assert.strictEqual(zoom, 0.85, `Min zoom should clamp at 0.85, got ${zoom}`);
}

// Jest test registration if running under Jest
if (typeof test === 'function') {
  test('Geographic Web Mercator projection, boundary envelopes, and zoom invariants', () => {
    runAllValidationTests();
  });
} else {
  console.log('--- JalDrishti Map & Projection Validation Suite ---');
  runAllValidationTests();
  console.log('--- ALL MAP & PROJECTION TESTS PASSED SUCCESSFULLY! ---');
}
