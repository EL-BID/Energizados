# ROADMAP-01: Production Features Implementation Plan

## Document Control

| Field       | Value                                                      |
|-------------|------------------------------------------------------------|
| **Title**   | Roadmap: Production Features for Energizados Framework     |
| **Version** | 1.0                                                        |
| **Date**    | 2026-03-15                                                 |
| **Status**  | Draft                                                      |
| **Authors** | BID (Inter-American Development Bank) Engineering           |

---

## Executive Summary

This roadmap outlines the implementation of production-grade features for the Energizados framework, addressing the gaps identified in GAP-ANALYSIS-01. The roadmap follows an **incremental, phased approach** to minimize risk while delivering value to utilities progressively.

**Timeline:** 12-18 months (depending on team size and resources)

**Key Milestones:**
- **Milestone 1 (3 months):** CI/CD pipeline, 80% test coverage, SHAP integration
- **Milestone 2 (6 months):** MLflow integration, REST API, experiment tracking
- **Milestone 3 (12 months):** Drift detection, ONNX export, monitoring dashboard
- **Milestone 4 (18+ months):** Online learning, batch optimization, full production suite

---

## Phases Overview

| Phase | Duration | Focus | Key Deliverables |
|-------|----------|-------|------------------|
| **Phase 1** | 3 months | Foundation & Testing | CI/CD, 80% coverage, SHAP |
| **Phase 2** | 3 months | Experiment Tracking & Deployment | MLflow, REST API, model registry, CV, hyperparameter search |
| **Phase 3** | 6 months | Monitoring & Operations | Drift detection, ONNX export, dashboard |
| **Phase 4** | 6+ months | Advanced Features | Online learning, batch optimization |

---

## Phase 1: Foundation & Testing (Months 1-3)

### Objective
Establish production-grade quality assurance and CI/CD infrastructure.

### Deliverables

#### 1.1 CI/CD Pipeline (P0) - 2 weeks
**Description:** Automated testing, linting, and security checks via GitHub Actions.

**Tasks:**
- [ ] Create `.github/workflows/ci.yml` with:
  - Python version testing (3.10, 3.11, 3.12)
  - pytest execution with coverage report
  - Code linting (ruff, black, mypy)
  - Security scanning (bandit)
  - Dependency vulnerability check (safety)
- [ ] Create `.github/workflows/release.yml` for:
  - Automated changelog generation
  - PyPI publishing on version tags
- [ ] Integrate codecov or coveralls for coverage tracking

**Acceptance Criteria:**
- All PRs must pass CI before merge
- Coverage trends tracked in CI dashboard
- Security vulnerabilities block deployment

**Related FRs:** KI-010 (High priority)

**Dependencies:** None

---

#### 1.2 Increase Test Coverage to 80% (P0) - 6 weeks
**Description:** Add comprehensive tests for core modules.

**Tasks:**
- [ ] Audit current test coverage by module:
  - `src/energizados/etl/` — Target: 85%
  - `src/energizados/modeling/` — Target: 85%
  - `src/energizados/evaluation/` — Target: 80%
  - `src/energizados/preprocessing/` — Target: 80%
  - `src/energizados/core/` — Target: 80%
- [ ] Add unit tests for:
  - ETL orchestrator (DAG resolution, cycle detection)
  - Model adapters (fit, predict, serialization)
  - Transformers (fit, transform, edge cases)
  - Evaluation metrics (all metric types)
- [ ] Add integration tests for:
  - End-to-end training pipeline
  - ETL DAG with multiple dependencies
  - Ensemble training and prediction
- [ ] Add property-based tests for:
  - Feature engineering transformations
  - Evaluation metric calculations
- [ ] Fix all flaky tests (deterministic seed, mock external deps)

**Acceptance Criteria:**
- Overall coverage ≥ 80%
- CI enforces coverage threshold (fail if below)
- No flaky tests in CI

**Related FRs:** KI-008 (Open: 35% coverage)

**Dependencies:** CI/CD pipeline (1.1)

---

#### 1.3 SHAP Integration (P1) - 4 weeks
**Description:** Add SHAP explanations for model interpretability and regulatory compliance.

**Tasks:**
- [ ] Add SHAP dependency to requirements
- [ ] Implement `ShapExplainer` class in `src/energizados/evaluation/`:
  - Support for TreeExplainer (LightGBM, CatBoost)
  - Support for DeepExplainer (Neural Networks, LSTM)
  - Fallback to KernelExplainer for other models
- [ ] Add SHAP to evaluation workflow:
  - Compute SHAP values after model training
  - Generate summary plots (global feature importance)
  - Generate dependence plots (feature interactions)
  - Generate local explanations for top risky customers
- [ ] Add SHAP to HTML report:
  - SHAP summary plot section
  - SHAP dependence plots for top 5 features
  - Sample local explanations (top 10 predictions)
- [ ] Add SHAP to inference API (when implemented):
  - `/explain` endpoint for local explanations

**Acceptance Criteria:**
- SHAP values computed for all supported model types
- SHAP plots included in evaluation reports
- Local explanations available via API

**Related FRs:** FR-EVAL-014 (SHAP feature importance)

**Dependencies:** None (can start immediately)

---

### Phase 1 Summary
**Duration:** 3 months
**Effort:** ~12 weeks (2.5 FTE)
**Milestone:** M1 - Foundation established, framework production-ready for training

---

## Phase 2: Experiment Tracking & Deployment (Months 4-6)

### Objective
Enable systematic experiment tracking and real-time inference capabilities.

### Deliverables

#### 2.1 MLflow Integration (P1) - 4 weeks
**Description:** Automatic experiment tracking and model registry via MLflow.

**Tasks:**
- [ ] Add MLflow dependency to requirements
- [ ] Configure MLflow tracking server:
  - Local development: `mlflow ui`
  - Production: MLflow tracking server + PostgreSQL backend
  - Artifact storage: S3 or local filesystem
- [ ] Integrate MLflow into training pipeline:
  - Auto-log parameters from YAML config
  - Auto-log metrics (AUC, precision, recall, F1, etc.)
  - Auto-log model artifacts (pickle files)
  - Auto-log plots (ROC, gains, feature importance)
  - Auto-log config snapshots
- [ ] Implement model registry integration:
  - Register models with versioning
  - Transition stages (Staging → Production)
  - Compare models in registry
- [ ] Add MLflow CLI commands:
  - `energizados mlflow serve` — serve model via MLflow
  - `energizados mlflow compare` — compare experiments

**Acceptance Criteria:**
- All training runs logged to MLflow
- Models registered in model registry
- Experiment comparison via MLflow UI

**Related FRs:** OBJ-6 (experiment tracking and model versioning)

**Dependencies:** None

---

#### 2.2 REST API (FastAPI) (P1) - 4 weeks
**Description:** Real-time inference API for production integration.

**Tasks:**
- [ ] Add FastAPI dependency to requirements
- [ ] Create `src/energizados/api/` module:
  - FastAPI application setup
  - Pydantic models for request/response schemas
- [ ] Implement endpoints:
  - `POST /predict` — single-record inference
    - Input: JSON with feature values
    - Output: probability, predicted class, threshold
  - `POST /predict-batch` — batch inference
    - Input: JSON array of records
    - Output: array of predictions
  - `GET /health` — health check
  - `GET /info` — model metadata (version, training date, metrics)
  - `GET /explain/{record_id}` — SHAP explanation (if SHAP integrated)
- [ ] Add API configuration:
  - Model path (load from registry or filesystem)
  - Feature engineering pipeline (load from pickle)
  - Threshold (configurable)
  - Rate limiting (optional)
- [ ] Add API documentation:
  - Auto-generated OpenAPI/Swagger docs
  - Example requests/responses
- [ ] Add CLI command:
  - `energizados serve --model-path <path> --port 8000`

**Acceptance Criteria:**
- API serves predictions with < 100ms latency
- Handles 100+ concurrent requests
- Includes comprehensive API documentation

**Related FRs:** FR-INFERENCE-008 (real-time inference API)

**Dependencies:** SHAP (1.3) for explainability endpoint

---

#### 2.3 Configurable Ensemble Weights & Custom Meta-Learners (P2) - 2 weeks
**Description:** Add flexibility to ensemble methods.

**Tasks:**
- [ ] Implement configurable weights for soft voting:
  - Accept weights list in YAML config
  - Normalize weights automatically
  - Document weight impact on predictions
- [ ] Implement custom meta-learner selection:
  - Support LogisticRegression (default)
  - Support RandomForest, XGBoost as meta-learners
  - Allow custom meta-learner via class path
- [ ] Add validation:
  - Check that number of weights matches number of models
  - Warn about extreme weight distributions
- [ ] Update tests:
  - Test weighted soft voting
  - Test custom meta-learner training

**Acceptance Criteria:**
- Soft voting supports configurable weights
- Stacking supports custom meta-learners
- Validation catches configuration errors

**Related FRs:** FR-ENSEMBLE-004, FR-ENSEMBLE-005

**Dependencies:** None

---

#### 2.4 Cross-Validation & Hyperparameter Optimization (P2) - 3 weeks
**Description:** Add k-fold cross-validation during training and automated hyperparameter search.

**Tasks:**
- [ ] Implement k-fold CV in training pipeline:
  - Configurable k via YAML (`cv: 5`)
  - Report metrics per fold + mean/std
  - Support stratified k-fold for imbalanced datasets
- [ ] Implement hyperparameter optimization:
  - Grid search (`method: grid`)
  - Random search (`method: random`, `n_iter`)
  - Bayesian search via `optuna` (`method: bayesian`)
  - Log best params to MLflow (depends on 2.1)
- [ ] Update YAML schema for `hyperparam_search` and `cv` sections
- [ ] Add tests for CV and search workflows

**Acceptance Criteria:**
- CV reports per-fold metrics in evaluation report
- Hyperparameter search logs results to MLflow
- YAML config controls all search parameters

**Related FRs:** FR-TRAINING-012, FR-TRAINING-013, US-TRAINING-008

**Dependencies:** MLflow integration (2.1) for logging best params

---

### Phase 2 Summary
**Duration:** 3 months
**Effort:** ~13 weeks (2 FTE)
**Milestone:** M2 - Real-time inference, experiment tracking, CV and hyperparameter search available

---

## Phase 3: Monitoring & Operations (Months 7-12)

### Objective
Enable continuous monitoring of data and model drift in production.

### Deliverables

#### 3.1 Data Drift Detection (P2) - 6 weeks
**Description:** Continuous monitoring of input distribution changes.

**Tasks:**
- [ ] Create `src/energizados/monitoring/` module:
  - `DataDriftDetector` class
  - `DriftMonitor` orchestrator
- [ ] Implement drift detection algorithms:
  - Population Stability Index (PSI)
  - Kolmogorov-Smirnov test (numerical features)
  - Chi-square test (categorical features)
  - Jensen-Shannon divergence
- [ ] Create drift monitoring workflow:
  - Compute reference distribution from training data
  - Compare incoming data against reference
  - Generate drift alerts (severity: info, warning, critical)
  - Log drift metrics to MLflow
- [ ] Add monitoring configuration:
  - YAML config for drift thresholds
  - Feature-specific thresholds (if needed)
  - Alert channels (email, Slack, webhook)
- [ ] Create drift dashboard (optional):
  - Plot drift over time per feature
  - Highlight features with significant drift
- [ ] Add CLI command:
  - `energizados monitor drift --config monitoring.yaml --input data/new.parquet`

**Acceptance Criteria:**
- Drift detection runs on new data batches
- Alerts triggered when thresholds exceeded
- Drift metrics logged to MLflow

**Related FRs:** OBJ-7 (data drift detection), FR-EDA-007 (segmentation analysis)

**Dependencies:** MLflow integration (2.1) for logging

---

#### 3.2 Model Drift Detection (P2) - 4 weeks
**Description:** Monitor prediction quality degradation over time.

**Tasks:**
- [ ] Implement model drift monitoring:
  - Track metrics on labeled feedback data
  - Compare current metrics vs training metrics
  - Detect significant drops (e.g., AUC drop > 5%)
- [ ] Create feedback loop:
  - Accept labeled feedback from field inspections
  - Update model performance metrics
  - Trigger retraining if thresholds exceeded
- [ ] Add model drift dashboard:
  - Plot metrics over time (AUC, precision, recall)
  - Highlight performance degradation periods
  - Compare multiple model versions
- [ ] Add CLI command:
  - `energizados monitor model-drift --feedback feedback.csv`

**Acceptance Criteria:**
- Model drift detected via feedback data
- Dashboard shows performance trends
- Automated retraining triggers (optional)

**Related FRs:** None (new feature)

**Dependencies:** Data drift detection (3.1), MLflow integration (2.1)

---

#### 3.3 ONNX Export (P2) - 4 weeks
**Description:** Export models to ONNX format for framework-agnostic deployment.

**Tasks:**
- [ ] Add ONNX dependencies (onnx, onnxmltools, skl2onnx)
- [ ] Implement `ModelExporter` class in `src/energizados/export/`:
  - Export LightGBM to ONNX
  - Export CatBoost to ONNX
  - Export Neural Networks/LSTM to ONNX
  - Export feature engineering pipeline (ONNX Operator Zoo)
- [ ] Add CLI command:
  - `energizados export --model-path <path> --output model.onnx`
- [ ] Add ONNX validation:
  - Verify ONNX model produces same predictions as original
  - Test with ONNX Runtime
- [ ] Document ONNX deployment:
  - Inference with ONNX Runtime (Python, C#, Java)
  - Performance comparison (pickle vs ONNX)

**Acceptance Criteria:**
- Models export to ONNX format
- ONNX model predictions match original (within 1e-5 tolerance)
- Documentation covers multi-language deployment

**Related FRs:** None (new feature, Phase 3 Long-term)

**Dependencies:** None

---

#### 3.4 Monitoring Dashboard (P2) - 4 weeks
**Description:** Web dashboard for monitoring drift and model performance.

**Tasks:**
- [ ] Create dashboard application (Streamlit or Plotly Dash):
  - Data drift metrics over time
  - Model performance trends
  - Alert history
  - Model version comparisons
- [ ] Integrate with monitoring outputs:
  - Read MLflow logs
  - Read drift detector outputs
- [ ] Deploy dashboard:
  - Local development: `energizados dashboard`
  - Production: Docker container + Nginx

**Acceptance Criteria:**
- Dashboard displays key metrics
- Refreshed with latest monitoring data
- Accessible via web browser

**Related FRs:** None (new feature)

**Dependencies:** Data drift (3.1), Model drift (3.2), MLflow (2.1)

---

### Phase 3 Summary
**Duration:** 6 months
**Effort:** ~18 weeks (1.5 FTE)
**Milestone:** M3 - Full monitoring and operations suite available

---

## Phase 4: Advanced Features (Months 13-18+)

### Objective
Enable incremental model updates and large-scale inference optimization.

### Deliverables

#### 4.1 Online Learning (P3) - 8 weeks
**Description:** Support incremental model updates without full retraining.

**Tasks:**
- [ ] Research online learning algorithms:
  - Online Gradient Boosting (LightGBM, XGBoost)
  - Stochastic Gradient Descent for NN/LSTM
  - Hoeffding Trees (River library)
- [ ] Implement `OnlineModel` ABC:
  - `fit_partial(X, y)` method for incremental updates
  - `predict(X)` method
- [ ] Implement online learning adapters:
  - `OnlineLGBMAdapter` — partial_fit via LightGBM API
  - `OnlineSGDAdapter` — SGDClassifier/SGDRegressor
  - `OnlineRiverAdapter` — River library algorithms
- [ ] Create online learning workflow:
  - Stream data processing
  - Periodic model updates (hourly/daily)
  - Model checkpointing
- [ ] Add evaluation:
  - Online metrics (AUC online, prequential evaluation)
  - Compare online vs batch models

**Acceptance Criteria:**
- Online learning models supported
- Incremental updates reduce training time
- Performance comparable to batch retraining

**Related FRs:** None (new feature, Phase 3 Long-term)

**Dependencies:** None

---

#### 4.2 Batch Inference Optimization (P3) - 4 weeks
**Description:** Optimize batch inference for large datasets.

**Tasks:**
- [ ] Implement chunked processing:
  - Process data in fixed-size chunks
  - Memory-efficient for large datasets
- [ ] Add parallelization:
  - Multiprocessing for CPU-bound models
  - Batch inference with thread pool
- [ ] Implement streaming inference:
  - Read data in chunks from disk
  - Stream predictions to output file
- [ ] Benchmark performance:
  - Single-threaded vs multi-threaded
  - Chunk size optimization
  - Memory usage profiling

**Acceptance Criteria:**
- Batch inference processes 1M+ records efficiently
- Memory usage < 4GB for 1M records
- Parallelization achieves 2-3x speedup

**Related FRs:** FR-INFERENCE-007 (batch inference optimization)

**Dependencies:** None

---

#### 4.3 Additional Advanced Features (P3) - 4 weeks
**Description:** Complete remaining advanced features from PRD.

**Tasks:**
- [ ] Incremental ETL (FR-ETL-010):
  - Delta loading from source systems
  - Track last processed timestamp
- [ ] Group-aware splits (FR-SPLIT-005):
  - Group K-Fold cross-validation
  - Prevent data leakage by customer ID
- [ ] Mutual information feature selection (FR-FEATSEL-008):
  - Add MutualInformationSelector
  - Support for numerical and categorical features

**Acceptance Criteria:**
- Incremental ETL processes only new/updated records
- Group-aware splits prevent leakage
- Mutual information selector added

**Related FRs:** FR-ETL-010, FR-SPLIT-005, FR-FEATSEL-008

**Dependencies:** None

---

### Phase 4 Summary
**Duration:** 6+ months
**Effort:** ~16 weeks (1 FTE)
**Milestone:** M4 - Full production-grade feature set complete

---

## Resource Requirements

### Team Composition (Recommended)

| Role | Allocation | Responsibilities |
|------|------------|-------------------|
| **ML Engineer** | 2 FTE | Phase 1, 2, 3 (CI/CD, MLflow, API, monitoring) |
| **Data Scientist** | 1 FTE | Phase 1, 4 (SHAP, drift detection, online learning) |
| **Backend Engineer** | 1 FTE | Phase 2, 3 (FastAPI, dashboard, ONNX export) |
| **DevOps Engineer** | 0.5 FTE | Phase 1, 3 (CI/CD, deployment, infrastructure) |

**Total:** 4.5 FTE over 12-18 months

### Infrastructure

| Component | Specification |
|-----------|---------------|
| MLflow Tracking Server | 2 vCPU, 4GB RAM, 20GB storage |
| MLflow Artifact Storage | S3 bucket (or local 100GB) |
| API Server | 2 vCPU, 4GB RAM per instance |
| Monitoring Dashboard | 2 vCPU, 2GB RAM |
| CI/CD Runners | GitHub Actions (free tier) |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| **Team resource constraints** | High | High | Prioritize P0/P1 features; defer P3 to Phase 4 |
| **Integration complexity** | Medium | High | Thorough testing; incremental rollout; feature flags |
| **Performance regression** | Medium | Medium | Benchmark before/after; optimize hot paths |
| **Breaking changes** | Medium | High | Versioning strategy; deprecation period; migration guides |
| **Community adoption** | Medium | Medium | Early adopter program; documentation; tutorials |

---

## Success Metrics

### Technical Metrics

| Metric | Target | Timeline |
|--------|--------|----------|
| Test coverage | ≥ 80% | M1 (3 months) |
| CI/CD pass rate | ≥ 95% | M1 (3 months) |
| API latency (p95) | < 100ms | M2 (6 months) |
| Drift detection accuracy | ≥ 90% | M3 (12 months) |
| Online learning performance | Within 5% of batch | M4 (18 months) |

### Business Metrics

| Metric | Target | Timeline |
|--------|--------|----------|
| Utility deployments with production features | 3+ utilities | M3 (12 months) |
| Reduction in time-to-production | 50% | M2 (6 months) |
| User satisfaction (production features) | ≥ 4/5 | M4 (18 months) |
| Open-source contributors | 10+ | M4 (18 months) |

---

## Dependencies & Blockers

### External Dependencies

| Dependency | Status | Mitigation |
|------------|--------|------------|
| MLflow | Stable, open-source | No issues expected |
| FastAPI | Stable, open-source | No issues expected |
| SHAP | Stable, open-source | No issues expected |
| ONNX Runtime | Stable, open-source | No issues expected |
| Prometheus/Grafana | Stable, open-source | No issues expected |

### Internal Dependencies

| Item | Blocks | Timeline |
|------|--------|----------|
| CI/CD pipeline | All other features | M1 |
| Test coverage 80% | Production deployment | M1 |
| MLflow integration | Drift detection, dashboard | M2 |
| REST API | Production integration | M2 |
| SHAP integration | Explainability endpoint | M1 |

---

## Next Steps

1. **Review and Approve Roadmap**
   - Stakeholder review
   - Budget approval
   - Resource allocation

2. **Kickoff Phase 1**
   - Set up CI/CD pipeline (Week 1-2)
   - Audit test coverage (Week 2-3)
   - Begin SHAP integration (Week 3-6)

3. **Milestone Reviews**
   - M1 review at 3 months
   - M2 review at 6 months
   - M3 review at 12 months
   - M4 review at 18 months

4. **Continuous Improvement**
   - Gather user feedback after each phase
   - Adjust roadmap priorities as needed
   - Update documentation and tutorials

---

## Appendix: Related Documents

- PRD-01: Energizados Framework v1.1
- GAP-ANALYSIS-01: Production Readiness Assessment
- AGENTS.md: Development guidelines and conventions

---

## Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-15 | Initial draft | BID Engineering |
