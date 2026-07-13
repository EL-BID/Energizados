# Context Map

This repo has two bounded contexts.

## Contexts

- [Framework Core](./src/energizados/CONTEXT.md) — the ML framework itself: turns raw data + config into trained models, predictions, reports, and analyses. Owns all ML logic.
- [Web Console](./src/energizados/web/CONTEXT.md) — manages ML experiments: registers projects, queues async pipeline executions, and browses what they produced.

## Relationships

- **Web Console → Framework Core**: the web console is a thin observer/controller over the core. It triggers runs through the core's `ConfigPipelineBuilder` (via the `energizados.api` service layer), streams progress events, and reads core-produced artifacts (Runs, metrics, models, reports). The core has no dependency on the web console.
- **Shared vocabulary**: both contexts use *Run* (the core produces one per successful training execution; the web console generalizes it — see each context's `CONTEXT.md`). *Pipeline*, *Step*, *Model* are core concepts the web console references but does not own.
