/**
 * JalDrishti — Brand Configuration
 * Central source of truth for all user-facing brand strings,
 * identity constants, and application metadata.
 *
 * Internal identifiers (Docker services, API routes, env variables)
 * are NOT changed. Only user-visible strings are managed here.
 */

export const BRAND = {
  /** Primary product name — always use this exact capitalisation */
  name: 'JalDrishti',

  /** Release identity */
  releaseId: 'JalDrishti_abhi',

  /** Project owner / author */
  author: 'Abhishek Jayagond',

  /** Short tagline shown in header and footer */
  tagline: 'Groundwater Intelligence & Forecasting',

  /** Long description for methodology / about pages */
  description:
    'Automated environmental analytics platform engineered for rigorous water resource evaluation, ' +
    'continuous DWLR sensor telemetry processing, precipitation correlation, and multi-year temporal forecasting.',

  /** Problem statement reference shown in badge */
  problemStatement: 'CGWB #25068',

  /** Browser <title> */
  pageTitle: 'JalDrishti | Groundwater Intelligence & Forecasting',

  /** Browser meta description */
  metaDescription:
    'JalDrishti — Professional Groundwater Intelligence & Forecasting Platform. ' +
    'Telemetry monitoring, fluctuation analysis, recharge estimation, CGWB resource evaluation, and AI forecasting.',

  /** Footer attribution line */
  footerLine: 'JalDrishti · Groundwater Intelligence & Forecasting · Problem Statement #25068',

  /** Telemetry / data source attribution */
  dataSources: 'India-WRIS · IMD · TimescaleDB · FastAPI · React 18',

  /** GitHub repository URL */
  githubUrl: 'https://github.com/abhishekjayagond/JalDrishti',
};

export default BRAND;
