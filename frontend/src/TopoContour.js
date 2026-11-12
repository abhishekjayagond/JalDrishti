import React from 'react';

/**
 * TopoContour — JalDrishti's signature topographic contour-line motif.
 *
 * Thin, irregular, nested contour paths evoking geological terrain mapping
 * and subsurface aquifer structure. Used as a decorative accent only.
 *
 * NOTE: These are stylistic contour lines for brand identity purposes.
 * They do NOT represent actual surveyed elevation, aquifer boundaries,
 * or measured groundwater data.
 *
 * @param {number}  width      - SVG width (default 64)
 * @param {number}  height     - SVG height (default 48)
 * @param {string}  color      - Base stroke color (default muted teal)
 * @param {number}  opacity    - Overall opacity (default 0.18 — very subtle)
 * @param {string}  className  - Optional extra CSS class
 */
export function TopoContour({
  width = 64,
  height = 48,
  color = '#0369a1',
  opacity = 0.18,
  className = '',
  style = {},
}) {
  return (
    <svg
      viewBox="0 0 64 48"
      width={width}
      height={height}
      aria-hidden="true"
      focusable="false"
      className={`topo-contour-motif ${className}`}
      style={{ display: 'block', flexShrink: 0, ...style }}
    >
      {/* Outer contour — widest, lowest stroke */}
      <path
        d="M4 38 C10 32, 18 28, 28 30 C38 32, 44 26, 52 28 C58 29, 61 32, 62 36"
        fill="none"
        stroke={color}
        strokeWidth="1.1"
        strokeLinecap="round"
        opacity={opacity}
      />
      {/* Second contour */}
      <path
        d="M6 32 C13 24, 22 22, 30 24 C40 26, 46 20, 54 22 C59 23, 62 26, 62 29"
        fill="none"
        stroke={color}
        strokeWidth="1.0"
        strokeLinecap="round"
        opacity={opacity * 0.95}
      />
      {/* Third contour */}
      <path
        d="M10 26 C16 18, 25 16, 32 18 C41 20, 47 14, 54 16 C59 17, 62 20, 62 23"
        fill="none"
        stroke={color}
        strokeWidth="0.9"
        strokeLinecap="round"
        opacity={opacity * 0.9}
      />
      {/* Fourth contour */}
      <path
        d="M14 21 C20 14, 27 11, 34 13 C42 15, 48 9, 56 11 C60 12, 62 15, 62 18"
        fill="none"
        stroke={color}
        strokeWidth="0.8"
        strokeLinecap="round"
        opacity={opacity * 0.82}
      />
      {/* Inner contour — narrowest, highest elevation */}
      <path
        d="M20 16 C25 9, 31 7, 37 9 C44 11, 50 5, 57 7 C60 8, 62 11, 62 14"
        fill="none"
        stroke={color}
        strokeWidth="0.7"
        strokeLinecap="round"
        opacity={opacity * 0.72}
      />
      {/* Summit detail */}
      <path
        d="M27 11 C30 6, 34 4, 38 6 C43 8, 48 3, 55 4"
        fill="none"
        stroke={color}
        strokeWidth="0.65"
        strokeLinecap="round"
        opacity={opacity * 0.6}
      />
    </svg>
  );
}

/**
 * TopoContourLarge — wider variant for hero / page header backgrounds.
 * Renders a broader, landscape-oriented contour field.
 */
export function TopoContourLarge({
  width = 320,
  height = 120,
  color = '#0369a1',
  opacity = 0.07,
  className = '',
  style = {},
}) {
  return (
    <svg
      viewBox="0 0 320 120"
      width={width}
      height={height}
      aria-hidden="true"
      focusable="false"
      className={`topo-contour-large ${className}`}
      style={{ display: 'block', ...style }}
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Wide landscape contours */}
      <path d="M0 95 C30 88, 60 80, 95 85 C125 89, 145 78, 175 82 C205 86, 225 72, 260 76 C290 79, 310 88, 320 92" fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round" opacity={opacity} />
      <path d="M0 80 C25 72, 58 64, 90 70 C120 76, 140 62, 172 67 C205 72, 228 56, 262 61 C292 65, 310 72, 320 76" fill="none" stroke={color} strokeWidth="1.2" strokeLinecap="round" opacity={opacity * 0.92} />
      <path d="M0 65 C28 56, 60 48, 92 55 C122 61, 142 47, 174 52 C207 57, 230 42, 264 47 C294 51, 311 57, 320 61" fill="none" stroke={color} strokeWidth="1.1" strokeLinecap="round" opacity={opacity * 0.84} />
      <path d="M5 50 C32 41, 64 34, 94 41 C124 47, 145 33, 177 38 C210 43, 232 28, 266 33 C296 37, 313 43, 320 47" fill="none" stroke={color} strokeWidth="1.0" strokeLinecap="round" opacity={opacity * 0.75} />
      <path d="M12 36 C38 27, 68 21, 97 28 C127 34, 148 19, 180 24 C212 29, 235 15, 268 20 C298 24, 314 29, 320 33" fill="none" stroke={color} strokeWidth="0.9" strokeLinecap="round" opacity={opacity * 0.65} />
      <path d="M22 23 C46 14, 76 8, 105 15 C134 21, 155 7, 186 12 C218 17, 240 3, 272 8 C300 12, 315 17, 320 20" fill="none" stroke={color} strokeWidth="0.8" strokeLinecap="round" opacity={opacity * 0.52} />
      <path d="M35 11 C58 3, 88 0, 116 6 C145 12, 166 0, 196 4 C226 8, 250 0, 280 3" fill="none" stroke={color} strokeWidth="0.7" strokeLinecap="round" opacity={opacity * 0.38} />
    </svg>
  );
}

/**
 * TopoContourMark — compact square mark for favicon / brand symbol context.
 * Designed to sit inside the header icon square.
 */
export function TopoContourMark({
  size = 22,
  color = '#ffffff',
  opacity = 0.9,
  style = {},
}) {
  return (
    <svg
      viewBox="0 0 22 22"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
      style={{ display: 'block', ...style }}
    >
      {/* Letter J as a minimal cartographic mark */}
      <path
        d="M13 3 L13 14 C13 17, 11 19, 8 18 C6 17, 5 15, 5.5 13"
        fill="none"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={opacity}
      />
      {/* Contour accent lines underneath the J */}
      <path
        d="M2 20 C5 17, 9 16, 13 17 C17 18, 20 16, 22 17"
        fill="none"
        stroke={color}
        strokeWidth="0.9"
        strokeLinecap="round"
        opacity={opacity * 0.55}
      />
      <path
        d="M2 22 C6 19, 10 18, 14 19 C18 20, 21 18, 22 19"
        fill="none"
        stroke={color}
        strokeWidth="0.75"
        strokeLinecap="round"
        opacity={opacity * 0.38}
      />
    </svg>
  );
}

export default TopoContour;
