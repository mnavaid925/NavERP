# Gap Register: Module 12.15 Process Validation & Verification

**Target Sub-module**: 12.15 Process Validation & Verification  
**App**: `quality` (`apps/quality/models/ProcessValidation/`)  
**Date**: 2026-11-21  
**Status**: Clean (Zero Open Gaps)  

---

## Gaps Summary

- **Open**: 0
- **Closed**: 0
- **Deferred / Superseded**: 3 (Documented in research & build scope)

---

## Deferred Enhancements (External Service & Advanced Statistical Scope)

### GAP-quality-12.15-01: Automated GAMP Category 5 Source Code Static Analysis & AST Ingestion
- **Owner**: `apps/quality` (Computer System Validation Services)
- **Waiting For / Blocked On**: Integration of AST static analysis and vulnerability scanner hooks for custom-built scripts and software in GAMP Category 5 validation flows.
- **Status**: `[~] Deferred`
- **Done When**: Registering a GAMP Category 5 computerized system allows automated ingestion of static security scans, SonarQube quality gate outputs, and commit change summaries into the validation record.

### GAP-quality-12.15-02: Direct CDS / LIMS Analytical Instrument Gateway for Swab & Rinse Telemetry
- **Owner**: `apps/quality` (Laboratory Instrument Integrations)
- **Waiting For / Blocked On**: Corporate lab instrument REST/OPC-UA connector configuration for Waters Empower, Agilent OpenLab, or Shimadzu LabSolutions.
- **Status**: `[~] Deferred`
- **Done When**: Analytical lab testing records automatically pull HPLC chromatogram peaks, TOC ppm readouts, and spectrophotometer recoveries directly into `CleaningValidation` swab result registers without manual entry.

### GAP-quality-12.15-03: Continuous Process Verification (CPV) Advanced Non-Normal Distribution Fitting
- **Owner**: `apps/quality` (Statistical Analysis Engine)
- **Waiting For / Blocked On**: Integration of advanced mathematical libraries (`scipy.stats` / Box-Cox, Johnson, Weibull transformations) into background analytical workers.
- **Status**: `[~] Deferred`
- **Done When**: Process capability studies for heavily skewed or multi-modal parameter distributions can automatically apply Box-Cox / Johnson transformations to compute non-normal capability indices ($P_{pk}$) alongside standard normal metrics.

---

**Gaps**: None.
