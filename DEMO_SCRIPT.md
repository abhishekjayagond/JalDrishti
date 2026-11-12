# Demo Script

## 60-90 Second Version

JalDrishti is an Indian groundwater intelligence and forecasting platform built for the Ministry of Jal Shakti (CGWB Problem Statement #25068). It integrates continuous DWLR water-level analysis, dynamic recharge estimation, real-time CGWB resource evaluation, and multi-year AI forecasting in one comprehensive system.

On the console, we observe nationwide station telemetry, active early warning alerts, and state/district health rankings. The system ingests live-source sensor streams while providing resilient benchmark fallback telemetry when upstream public APIs throttle or become unavailable.

Selecting any monitoring station presents Task 1 fluctuation analysis (drawdown rates, moving averages, and sensor anomalies). Task 2 calculates dynamic recharge by correlating IMD precipitation events with aquifer recovery curves and specific yields. Task 3 evaluates aquifer health against official CGWB criteria (Safe, Semi-Critical, Critical, Over-Exploited) alongside depletion timelines and Resource Availability Indices. In the AI forecasting tab, multi-year pre-monsoon predictions run with empirical validation error bands.

The backend leverages FastAPI, PostgreSQL with TimescaleDB hypertables, and an automated data pipeline, while the presentation tier provides a clean, minimal scientific interface with topographic motifs in React 18.

The core impact of JalDrishti is converting high-volume sensor telemetry into rigorous, forward-looking groundwater intelligence for scientists, policy makers, and community planners.

## Extended Walkthrough

JalDrishti represents our solution for real-time groundwater resource evaluation and predictive intelligence using automated DWLR sensor networks. Although high-frequency sensor readings exist at scale, transforming raw depths into recharge quantification, depletion forecasts, and early warning advisories has historically remained challenging.

The platform unifies these workflows across five key modules:

First, Water Table Fluctuation (WTF) analysis: continuous telemetry tracks aquifer level movement, computes hourly, daily, and weekly rate of change vectors, and flags sudden sensor drops or over-extraction events.

Second, Dynamic Recharge Estimation: we couple water level responses with IMD rainfall telemetry to determine recharge rates (m/day), hydrologic lag times, and seasonal net recharge across different aquifer types.

Third, Resource Evaluation: stations and administrative blocks are evaluated using official CGWB criteria into Safe, Semi-Critical, Critical, or Over-Exploited classifications, calculating depletion rates and Resource Availability Indices (RAI).

Fourth, Spatial-Temporal AI Forecasting: trained on historical Karnataka DWLR pre-monsoon records (1994–2025), machine learning models forecast next-year water levels with calibrated 90th-percentile error bands and risk indicators.

Fifth, National Early Warnings: automated alerts identify aquifer collapse risk and sensor communication failures before critical crises emerge.

The containerized stack uses FastAPI, React 18, TimescaleDB, and Redis, delivering an operational decision-support tool for sustainable aquifer stewardship.
