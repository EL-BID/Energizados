# Offline & Proxied Environments

Energizados can run in corporate networks that require a proxy for outbound
traffic, and in fully air-gapped environments. This page explains what touches
the network, and how to configure each piece.

## What accesses the network

| Component | When | Protocol |
|-----------|------|----------|
| IBGE shapefile downloads | First run of `GeoFeatures` / `GeoFeaturesETL` (geobr) | HTTPS via `requests` |
| Plotly.js / Tailwind CDN in HTML reports | Every time a generated report is opened in a browser | Browser HTTPS |
| Web console frontend assets (Bootstrap, HTMX, fonts) | Every web console page load | Browser HTTPS |

Model training, ETL, EDA computation and inference never make network calls.

## Behind a proxy

geobr downloads through Python `requests`, which honors the standard proxy
environment variables:

```bash
export HTTP_PROXY="http://proxy.company.com:8080"
export HTTPS_PROXY="http://proxy.company.com:8080"
export NO_PROXY="localhost,127.0.0.1"
```

Corporate proxies that perform TLS interception (MITM) use a private CA. Point
Python at the corporate certificate bundle:

```bash
export REQUESTS_CA_BUNDLE="/etc/ssl/certs/company-ca.pem"
# or, more broadly for Python/other tools:
export SSL_CERT_FILE="/etc/ssl/certs/company-ca.pem"
```

## Fully offline geo features

The IBGE shapefiles only need to be downloaded **once**. Configure a cache
directory and the download never happens again:

```yaml
# etl.yaml (GeoFeaturesETL) or the geo_features global transformer
params:
  cache_dir: ".cache/ibge"
```

To pre-populate the cache on an air-gapped machine:

1. Run once on any machine with internet access (the shapefiles are cached as
   parquet files under the `cache_dir`), then
2. Copy the `.cache/ibge/` directory to the target machine, at the same
   relative path (or point `cache_dir` at wherever you place it).

## Self-contained HTML reports

By default, generated reports (EDA and evaluation) reference Plotly.js from a
public CDN, and the run-comparison report references Tailwind the same way. The
pipeline itself never downloads these — the **browser** does when the report is
opened. In restricted environments the reports open without charts.

Set `self_contained: true` to inline the JavaScript bundles directly into the
HTML files:

```yaml
# eda.yaml
output:
  self_contained: true
```

```yaml
# train.yaml
evaluation:
  self_contained: true
```

The programmatic equivalents are `EDAReportGenerator(..., self_contained=True)`,
`DefaultEvaluator(..., self_contained=True)` and
`ComparativeEvaluator(..., self_contained=True)`.

**Tradeoff:** each report grows by roughly 3.5 MB (the inlined Plotly.js
bundle). If you only read reports on machines with internet access, keep the
default.

## Web console

The web console ships all frontend assets (Bootstrap, Bootstrap Icons, HTMX,
Plotly.js and the Inter font) vendored under
`src/energizados/web/static/vendor/`. The console makes **zero external network
requests** and works in air-gapped deployments out of the box. See
`src/energizados/web/static/vendor/README.md` for versions, sources and
licenses, and how to update them.
