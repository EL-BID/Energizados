---
status: accepted
---

# GeoFeatures transformer owns geographic clustering; dataset builders compose it as a post-step

Geographic feature enrichment (`geo_cluster` via KMeans, IBGE hierarchy, distances)
was split across two layers: the `GeoFeatures` transformer (`preprocessing/`) handled
hierarchy + distances, while KMeans clustering and the train/infer model persistence
(`geo_model.pkl`) were welded into `GeoFeaturesETL` (`etl/pipeline.py`), the file-I/O
layer. Project dataset builders then ran a *second* ETL (`dataset_geo`) that re-read the
just-written parquet to append geo columns, overwriting the same file — hiding an
intermediate state and forcing a file round-trip. We decided to make clustering a
first-class responsibility of the `GeoFeatures` transformer, have it follow pure
scikit-learn semantics (`fit` learns without persisting; `transform` applies; `save`/
`load` carry the KMeans+scaler model), and have dataset builders compose it as an
in-memory post-step inside a shared `_finalize()` tail. `GeoFeaturesETL` becomes a thin
wrapper that delegates everything to the transformer.

## Considered options

- **Project-only, nested ETL (rejected):** the builder writes the parquet, then invokes
  `GeoFeaturesETL` on it. Merges the YAML but hides the seam and keeps a redundant file
  round-trip — the "hidden intermediate state" smell survives, disguised.
- **Project-only, duplicate cluster + model in the builder (rejected):** two sources of
  truth for the `geo_model.pkl` format; a future contract change breaks inference
  silently.
- **Chosen — framework refactor:** moves the concern to its linguistically-correct home.
  `CONTEXT.md` defines a Transformer as *"a `fit`/`transform` unit that modifies columns
  during Preprocessing"* — adding `geo_cluster` is exactly that. It gives one clean
  composition target for all consumers and the change is bounded (three methods move;
  `integrity_pickle` and the param surface are preserved).

## Consequences

- **Backward compatibility.** `GeoFeaturesETL` keeps its entire YAML param surface
  (`n_clusters`, `include_cluster`, `geo_model_path`, `regions_file`, …) and behavior, so
  existing two-step configs (`dataset` + `dataset_geo`) continue to work — they now
  delegate to the transformer rather than doing the clustering themselves.
- **Default `include_cluster=False` on the transformer.** `GeoFeatures` is also used via
  `custom_class` in `global_transformers`, where it has never clustered (only hierarchy +
  distances). Defaulting clustering on would silently start clustering there and could
  fail on frames with fewer than 10 valid coordinates. `GeoFeaturesETL` and the dataset
  builders pass `include_cluster=True` explicitly.
- **Train/infer model hand-off.** The load-or-fit decision (train fits + persists, infer
  loads + predicts) lives once in the builders' shared `_finalize()`, driven by whether
  `geo_model.pkl` exists on disk. The transformer itself is mode-agnostic and testable in
  isolation (`fit` without touching disk).
- **First framework-core ADR.** Web-console decisions live under
  `src/energizados/web/docs/adr/`; this establishes the parallel home for framework-core
  decisions.
