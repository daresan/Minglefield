# Minglefield licensing and marketplace — binding project decision

**Decision confirmed: 2026-11-04.** Applies to the public Minglefield framework and planned commercial platform services. This is an **architecture and business-model decision**, not a claim that a marketplace, payment system, or published framework license already exists.

## Non-negotiable separation

1. **Framework:** Minglefield follows the Blender-style free/open-source model. The selected license family is **GNU GPL**; the working repository plan names **GPL-3.0-or-later**. The exact license notice and complete canonical text must be committed before describing the repository as actually GPL-licensed or distributing it on that basis. Do not invent or paraphrase the GPL as substitute legal text.
2. **Marketplace:** Commercial transactions *mediated through Minglefield's marketplace/services* are governed by separate marketplace/merchant terms, not by an added condition in the GPL. The project-defined platform share is **5% of the contractually defined transaction basis**. Contributor pricing and margins remain their choice subject to agreed terms.
3. **Third-party content and services:** Games, assets, models, agents, rentals and services retain their own applicable licenses and contracts, subject to compatibility with any incorporated GPL-covered code and platform terms. Being listed in the marketplace does not automatically make independent content GPL.
4. **Outside the marketplace:** The GPL's freedoms to use, modify and redistribute GPL-covered code are **not** subject to a Minglefield 5% royalty. The platform fee must not be represented as an obligation on every external sale, redistribution or independent use of GPL-covered software.
5. **Forks:** Forks and third parties retain GPL freedoms. Use of Minglefield-operated commercial services may be subject to service terms, but GPL rights do not require purchasing those services.

## Operational requirements

- Implement the 5% share in marketplace transaction accounting and merchant agreements, **not** in GPL license text or in a generic installer license-acceptance mechanism.
- Define transaction basis, taxes, refunds/chargebacks, settlement, invoicing and merchant responsibilities in marketplace terms before activating real payments. These implementation details do **not** reopen the decided GPL + marketplace model.
- The installer may show the full published GPL text and notices. GPL use does not require an invented extra copyright-license acceptance condition. Any separate acceptance of commercial service terms must be labeled as such and only gate the relevant service.
- Until the actual license text and notices are committed, installation **execution/distribution gates remain fail-closed** as already designed; this is a concrete missing release artifact, **not** an unresolved choice of business model.
- Do not automatically block unrelated engineering work or repeat a general request to redefine licensing. Escalate only specific conflicts: rights ownership, incompatible included licenses, consumer/payment obligations, or the precise marketplace contract language.

## Implementation status

- **Decided:** GPL framework model; separate commercial marketplace terms; 5% platform transaction share.
- **Not yet published/implemented:** root LICENSE file, exact copyright/SPDX notices, merchant terms, payment and settlement logic.
- **Not authorized by this document:** falsely claiming a GPL grant before publishing the license, silently enabling payment flows, or changing the 5% decision.

This decision supersedes earlier speculative wording suggesting the project must first choose whether GPL and a 5% marketplace share can coexist.
