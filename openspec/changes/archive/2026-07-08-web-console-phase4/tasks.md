# Tasks: web-console-phase4 - Metrics Dashboard

## Review Workload Forecast

| Metric | Estimate |
|--------|----------|
| **Total changed lines** | ~1,100-1,300 lines (Timeline: 350, Comparison: 500, Threshold: 250, Integration: 100) |
| **400-line budget risk** | **Medium** - Timeline slice safe, Comparison slice near budget (~450), Threshold safe |
| **Chained PRs recommended** | **Yes** - 3 PRs proposed |
| **Decision needed before apply** | **Yes** - PR split decision pending user approval |

**Proposed PR Boundaries (delivery_strategy: ask-on-risk):**
- **PR1 (Timeline)**: Tasks 1-5 - Foundation + Timeline (~350 lines) - LOW risk, well-contained
- **PR2 (Comparison)**: Tasks 6-13 - Comparison view + batch loading (~500 lines) - MEDIUM risk, near budget
- **PR3 (Threshold)**: Tasks 14-19 - Threshold exploration + Integration (~350 lines) - LOW risk, focused

---

## Task Checklist (Strict TDD Order)

### SLICE 1: FOUNDATION + TIMELINE DASHBOARD (PR1 Candidate)

#### Task 1: Test - base.html includes Plotly CDN (RED)
**Spec requirement**: All dashboard views use Plotly for charts
**Type**: Test (red)
**Test file**: `tests/web/test_plotly_foundation.py` (new)
**Test method**: `test_base_template_includes_plotly_cdn`

#### Task 2: Implement - Add Plotly CDN to base.html (GREEN)
**Spec requirement**: All dashboard views use Plotly for charts
**Type**: Implementation
**File**: `src/energizados/web/templates/base.html`

#### Task 3: Test - Timeline API endpoint (RED)
**Spec requirement**: Timeline JSON Data Endpoint
**Type**: Test (red)
**Test file**: `tests/web/test_dashboard_timeline.py` (new)
**Test class**: `TestTimelineApi`

Test cases:
- `test_timeline_api_returns_correct_structure`
- `test_timeline_api_with_limit_param`
- `test_timeline_api_with_status_filter`
- `test_timeline_api_empty_runs`
- `test_timeline_api_handles_missing_metrics`

#### Task 4: Implement - Timeline API endpoint + helper (GREEN)
**Spec requirement**: Timeline JSON Data Endpoint
**Type**: Implementation
**File**: `src/energizados/web/app.py`

#### Task 5: Test + Implement - Dashboard page (RED + GREEN)
**Spec requirement**: Timeline Dashboard View
**Type**: Test + Implementation
**Test file**: `tests/web/test_dashboard_timeline.py`
**Files**: `src/energizados/web/app.py`, `templates/dashboard.html` (new)

---

### SLICE 2: COMPARISON VIEW (PR2 Candidate)

#### Task 6: Test - Run ID parsing validation (RED)
**Spec requirement**: Comparison View - reject malformed/invalid IDs
**Type**: Test (red)
**Test file**: `tests/web/test_comparison_validation.py` (new)
**Test class**: `TestRunIdParsing`

Test cases:
- `test_parse_valid_run_ids`
- `test_parse_less_than_2_ids_returns_400`
- `test_parse_more_than_10_ids_returns_400`
- `test_parse_empty_ids_returns_400`
- `test_parse_path_traversal_rejected`
- `test_parse_whitespace_handled`

#### Task 7: Implement - `_parse_and_validate_run_ids` helper (GREEN)
**Spec requirement**: Comparison View - security validation
**Type**: Implementation
**File**: `src/energizados/web/app.py`

#### Task 8: Test - Batch evaluation loader (RED)
**Spec requirement**: Batch Evaluation Loader Helper
**Type**: Test (red)
**Test file**: `tests/web/test_comparison_batch_loader.py` (new)
**Test class**: `TestBatchEvaluationLoader`

Test cases:
- `test_batch_load_multiple_runs`
- `test_batch_load_skips_missing_eval_json`
- `test_batch_load_handles_single_model`
- `test_batch_load_handles_multi_model`
- `test_batch_load_empty_list`

#### Task 9: Implement - `_load_run_evaluations_batch` helper (GREEN)
**Spec requirement**: Batch Evaluation Loader Helper
**Type**: Implementation
**File**: `src/energizados/web/app.py`

#### Task 10: Test - Comparison API endpoint (RED)
**Spec requirement**: Comparison JSON Data Endpoint
**Type**: Test (red)
**Test file**: `tests/web/test_comparison_api.py` (new)
**Test class**: `TestComparisonApi`

Test cases:
- `test_compare_api_returns_correct_structure`
- `test_compare_api_validation_errors`
- `test_compare_api_mixed_run_types`
- `test_compare_api_skips_missing_runs`
- `test_compare_api_all_runs_missing_returns_404`
- `test_compare_api_includes_available_models`

#### Task 11: Implement - Comparison API endpoint (GREEN)
**Spec requirement**: Comparison JSON Data Endpoint
**Type**: Implementation
**File**: `src/energizados/web/app.py`

#### Task 12: Test - Comparison page (RED)
**Spec requirement**: Comparison View
**Type**: Test (red)
**Test file**: `tests/web/test_comparison_page.py` (new)
**Test class**: `TestComparisonPage`

Test cases:
- `test_compare_page_renders_html`
- `test_compare_page_validation_errors`
- `test_compare_page_shows_single_model_metrics`
- `test_compare_page_shows_ensemble_ranking`
- `test_compare_page_best_value_highlighting`
- `test_compare_page_csv_download`

#### Task 13: Implement - Comparison page + template (GREEN)
**Spec requirement**: Comparison View
**Type**: Implementation
**Files**: `src/energizados/web/app.py`, `templates/compare_runs.html` (new)

---

### SLICE 3: THRESHOLD EXPLORATION + INTEGRATION (PR3 Candidate)

#### Task 14: Test - Threshold data loader (RED)
**Spec requirement**: Threshold Exploration Data Endpoint
**Type**: Test (red)
**Test file**: `tests/web/test_threshold_loader.py` (new)
**Test class**: `TestThresholdDataLoader`

Test cases:
- `test_threshold_load_single_model_full_data`
- `test_threshold_load_ensemble_returns_null_metrics`
- `test_threshold_load_missing_threshold_metrics`
- `test_threshold_load_missing_cumulative_gains`
- `test_threshold_load_missing_run_returns_none`

#### Task 15: Implement - `_load_threshold_data` helper (GREEN)
**Spec requirement**: Threshold Exploration Data Endpoint
**Type**: Implementation
**File**: `src/energizados/web/app.py`

#### Task 16: Test - Threshold API endpoint (RED)
**Spec requirement**: Threshold Exploration Data Endpoint
**Type**: Test (red)
**Test file**: `tests/web/test_threshold_api.py` (new)
**Test class**: `TestThresholdApi`

Test cases:
- `test_threshold_api_single_model_returns_data`
- `test_threshold_api_ensemble_returns_null_metrics_with_message`
- `test_threshold_api_missing_threshold_metrics_returns_partial`
- `test_threshold_api_missing_run_returns_404`
- `test_threshold_api_response_structure`

#### Task 17: Implement - Threshold API endpoint (GREEN)
**Spec requirement**: Threshold Exploration Data Endpoint
**Type**: Implementation
**File**: `src/energizados/web/app.py`

#### Task 18: Test - run_detail.html threshold section (RED)
**Spec requirement**: Threshold Exploration UI Integration
**Type**: Test (red)
**Test file**: `tests/web/test_threshold_ui.py` (new)
**Test class**: `TestThresholdUi`

Test cases:
- `test_run_detail_includes_threshold_section`
- `test_threshold_section_with_data_loads_charts`
- `test_threshold_section_without_data_shows_message`
- `test_threshold_section_ensemble_specific_message`
- `test_threshold_slider_interaction`
- `test_run_detail_passes_unavailable_message`

#### Task 19: Implement - run_detail.html threshold extension (GREEN)
**Spec requirement**: Threshold Exploration UI Integration
**Type**: Implementation
**Files**: `src/energizados/web/app.py`, `templates/run_detail.html`

#### Task 20: Test + Implement - Integration testing (RED + GREEN)
**Spec requirement**: Cross-Cutting Graceful Degradation + Multi-Model Support
**Type**: Test + Integration
**Test file**: `tests/web/test_integration_phase4.py` (new)
**Test class**: `TestPhase4Integration`

Test cases:
- `test_dashboard_to_run_detail_navigation`
- `test_run_detail_to_compare_navigation`
- `test_compare_with_mixed_run_types`
- `test_timeline_shows_ensemble_runs`
- `test_content_negotiation_json_endpoints`
- `test_status_filter_across_views`
- `test_graceful_degradation_old_runs`
- `test_path_traversal_blocked_all_endpoints`

---

## Total Task Count: 20 tasks
**Implementation phases**: 3 slices (Foundation/Timeline: 5 tasks, Comparison: 8 tasks, Threshold: 5 tasks, Integration: 2 tasks)
**Estimated time**: 3-5 days (assuming 1-2 tasks per hour with TDD rigor)
**Test coverage target**: 100% of new routes and helpers (strict TDD ensures this)
