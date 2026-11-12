# Submission Checklist

## Before Recording

- Start all local native services:
  `.\start-jaldrishti.ps1`
- Verify endpoints:
  - Backend: `http://localhost:8000/api/health`
  - AI Service: `http://localhost:8010/health`
  - Frontend: `http://localhost:3000`
- Check at least 4-5 stations from different states
- Check Task 1, Task 2, and Task 3 for at least 2 stations
- Check State Ranking and Alerts tabs
- Keep one strong station selected before recording

## Before Pushing

- `git status` is clean
- README has correct run steps
- Demo/fallback badge is visible in UI
- No local-only secrets are committed
- Latest fixes are pushed to GitHub

## In The Video

- Show homepage overview
- Show one station with Task 1, Task 2, and Task 3
- Mention live-source architecture plus resilient fallback demo mode
- Mention FastAPI + React + TimescaleDB pipeline
- End with impact / decision-support value

## If Something Breaks

- Restart from:
  `.\stop-jaldrishti.ps1`
  `.\start-jaldrishti.ps1`
- Review service logs in `logs/` directory
- Use fallback-demo explanation confidently instead of improvising
