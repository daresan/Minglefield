# MAP conformance

**Initial draft schema validation script:** [validate_map_v01.py](validate_map_v01.py). It checks JSON Schema structure, action traces, game manifests, capability offers, deterministic negotiation cases and negative controls. GitHub Actions workflow: [.github/workflows/map-v01-conformance.yml](../../.github/workflows/map-v01-conformance.yml). Stateful conformance (authentication, deduplication, ordering, memory isolation) remains to be built. Run with Python 3.11+ and `jsonschema>=4.18`.
