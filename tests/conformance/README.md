# MAP conformance

**Initial draft schema validation script:** [validate_map_v01.py](validate_map_v01.py). It checks JSON Schema structure and the example trace, plus a negative control. Stateful conformance (authentication, deduplication, ordering, memory isolation) remains to be built. Run with Python 3.11+ and `jsonschema>=4.18`.
