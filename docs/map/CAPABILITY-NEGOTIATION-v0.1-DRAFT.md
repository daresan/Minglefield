# MAP v0.1 — Game Manifest and Capability Negotiation (Draft)

Status: **NON-NORMATIVE DRAFT**, 2026-10-31. Builds on the founder-approved asynchronous/event-oriented architecture and JSON reference encoding. Exact field and preference rules remain subject to review.

## Discovery
A host publishes a machine-readable game manifest describing its game identity, supported MAP protocol versions, interaction profiles, codecs, required/optional capabilities and connection endpoints. The manifest is **descriptive metadata**, not proof of host identity, authorization, service availability or safety. Production discovery requires authenticated endpoints and integrity controls.

The participant offers its own supported versions, profiles, codecs and capabilities. The two sides negotiate compatibility **before** establishing a gameplay session. Authentication and authorization remain separate and mandatory where applicable.

## Initial profiles
| Profile | Meaning |
|---|---|
| `turn_based` | Actions proceed according to host-defined turns; no universal turn duration |
| `real_time` | Time-sensitive actions and events; actual latency/QoS negotiated separately |
| `hybrid` | Mixes turn and real-time or multiple pacing regimes |
| `event_driven` | Asynchronous event reactions without mandatory turns |

These are declared interaction profiles, not mutually exclusive game classifications. A host may advertise several.

## Draft negotiation algorithm
1. Validate both manifest and offer. Invalid input is a protocol validation error, not an ordinary incompatibility.
2. Intersect `map_versions`; if empty return `no_common_version`. Choose the numerically highest shared major/minor version.
3. Intersect `interaction_profiles`; if empty return `no_common_profile`. Choose the first shared entry in the **host's advertised preference order**.
4. Intersect `codecs`; if empty return `no_common_codec`. Choose `json` when shared, otherwise the first shared codec in the host's advertised order **only if its codec profile is registered and validated**. The sample implementation deliberately supports only JSON.
5. Check that all host-required capabilities are offered; if not return `missing_required_capability`. Optional capabilities are the intersection of the host's optional set and the offer.
6. Return a compatible result with the selected version/profile/codec and the union of required and negotiated optional capabilities.
7. The host still authenticates/authorizes the participant and session. A compatible result grants **no access rights**.

The draft schema does not yet encode a codec registry, required client capabilities, protocol version range negotiation, endpoint trust, security profiles or the lifecycle message carrying the negotiation result.

## Security and versioning notes
- Unsupported or unknown **required** capabilities must fail closed.
- Unknown optional capabilities may be ignored.
- Never downgrade a security requirement to force compatibility.
- Version `0.1` is a draft reference version, not a published stable compatibility promise.
- Capability strings are namespaced; `map.*` is reserved for MAP core semantics, `game.*` for game extensions in examples.
- A successful negotiation is not a signed contract or authentication assertion.

## Schemas and examples
- [Game manifest schema](../../schemas/map/v0.1/game-manifest.schema.json)
- [Capability offer schema](../../schemas/map/v0.1/capability-offer.schema.json)
- [Negotiation result schema](../../schemas/map/v0.1/negotiation-result.schema.json)
- [Manifest example](../../examples/map/v0.1/game-manifest.json)
- [Offer example](../../examples/map/v0.1/capability-offer.json)
- [Positive and negative cases](../../examples/map/v0.1/negotiation-cases.json)
- [Reference negotiation function and validation](../../tests/conformance/validate_map_v01.py)

## Open design gates
Authority, signed manifests, transport discovery, capability registry, codec profile registration, security requirements, version downgrade policy, profile preference authority and session admission semantics. All need founder/design review before normative release.
