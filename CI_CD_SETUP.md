# CI/CD Pipeline Setup Documentation

## Overview
This document describes the comprehensive CI/CD pipeline for the clinical-rag-assistant project with automatic PR checks and deployment triggers.

## 🔄 Three-Stage Pipeline Architecture

### Stage 1: **Automated PR Checks (CI Pipeline)** 🔍
**Triggers:** When PR is created/updated against `main`

**What runs:**
- ✅ Unit Tests (80% code coverage minimum)
- ✅ Pylint Code Quality (score >= 8.0)
- ✅ Black Code Formatting
- ✅ Flake8 Linting
- ✅ MyPy Type Checking
- ✅ Bandit Security Scans
- ✅ Safety Vulnerability Checks

**Result:** PR cannot be merged until all checks pass

---

### Stage 2: **Merge Status Check**
**Triggers:** When PR is opened/updated

**What runs:**
- ✅ PR title validation
- ✅ PR description validation
- ✅ Automatic comment with pipeline status

**Result:** Clear visibility of check status on PR

---

### Stage 3: **Deployment Pipeline (CD)** 🚀
**Triggers:** AUTOMATICALLY when code is merged to `main` branch

**What runs:**
- ✅ Final verification tests
- ✅ Docker image build (if Dockerfile exists)
- ✅ Deployment readiness check
- ✅ Status notifications

**Result:** Ready for production deployment

---

## 📋 Workflow Files

### 1. `.github/workflows/ci.yml` - Main CI Pipeline
```yaml
Triggers:
  - pull_request: When PR is opened/updated against main
  - push: When code is merged to main

Jobs:
  1. quality-checks: Pylint, Black, Flake8, MyPy (Python 3.9, 3.10, 3.11)
  2. unit-tests: Pytest with 80% coverage threshold
  3. security-checks: Bandit & Safety scans
  4. all-checks-passed: Final aggregator