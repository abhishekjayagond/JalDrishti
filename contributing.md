# Contributing to JalDrishti

Thank you for your interest in contributing to **JalDrishti** (Lead & Maintainer: **Abhishek Jayagond**). JalDrishti is a groundwater monitoring, resource evaluation, and predictive forecasting platform independently developed by Abhishek Jayagond.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project adheres to the [Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to maintain a professional, collaborative environment.

---

## How Can I Contribute?

| Type | Focus Area |
|------|------------|
| Bug Reports | Identify calculation discrepancies, pipeline failures, or UI bugs |
| Feature Enhancements | Propose algorithmic or visualization improvements |
| Documentation | Clarify hydrogeological formulas, API schemas, or deployment instructions |
| Core Algorithms | Refine Task 1, Task 2, Task 3, or AI forecasting implementations |
| Data Validation | Audit data cleaning rules against India-WRIS or IMD telemetry standards |
| Tests | Expand unit and integration test coverage |

---

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/abhishekjayagond/JalDrishti.git
cd JalDrishti
```

### 2. Environment Setup

#### Backend & Data Pipeline:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r backend/requirements.txt
```

#### Frontend:
```bash
cd frontend
npm install
npm start
```

### 3. Automated Local Startup (Windows)

```powershell
.\start-jaldrishti.ps1
```
This boots the complete local stack (PostgreSQL TimescaleDB, Redis, AI service, Backend API, and Frontend). To shut down:
```powershell
.\stop-jaldrishti.ps1
```

---

## Development Workflow

### Step 1: Sync with Main
```bash
git checkout main
git pull origin main
```

### Step 2: Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### Step 3: Run Tests
Always ensure automated tests pass before submitting changes:
```bash
pytest backend/tests ai/tests data/scripts/test_pipeline.py -v
cd frontend && npm run build
```

---

## Commit Guidelines

Use clear, imperative commit messages:
- `feat: add specific yield calculation for basalt aquifers`
- `fix: handle null coordinates in station cleaner`
- `docs: update API documentation for AI forecast endpoints`
- `test: add unit tests for Task 3 classification`

---

## Pull Request Process

1. Ensure your code passes all unit tests and builds without errors.
2. Submit a Pull Request targeting the `main` branch of `https://github.com/abhishekjayagond/JalDrishti`.
3. Provide a clear summary of changes, motivation, and verification steps.
4. Maintainers will review and provide feedback.
