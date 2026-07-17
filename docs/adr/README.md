# Architecture Decision Records

Architecture Decision Records (ADRs) capture significant engineering decisions
that affect the structure, constraints or long-term operation of PLC Universal
Simulator. They preserve the context and trade-offs behind a decision so future
contributors do not need to reconstruct them from code or commit history.

## Naming convention

Create ADRs in this directory using a four-digit sequence and a short,
lowercase, hyphenated title:

```text
0001-short-decision-title.md
0002-another-decision.md
```

Copy `ADR_TEMPLATE.md` and replace every placeholder. Sequence numbers are
never reused, including when an ADR is rejected or superseded.

## Lifecycle

An ADR has one of these states:

- **Proposed** — under review and not yet authoritative.
- **Accepted** — approved and guiding implementation.
- **Rejected** — considered but intentionally not adopted.
- **Deprecated** — retained for history but no longer recommended.
- **Superseded by ADR-NNNN** — replaced by a newer decision.

Accepted ADRs are not rewritten to make history look current. If a material
decision changes, create a new ADR and link both records through their status
and relationship fields. Small corrections that do not alter the decision may
be made directly.

## When to create an ADR

Create an ADR when a decision:

- changes a public or cross-module contract;
- introduces or replaces a major dependency, protocol or persistence format;
- establishes concurrency, security, compatibility or deployment policy;
- has meaningful alternatives or difficult-to-reverse consequences;
- affects several features or future contributors.

An ADR is not required for local implementation details, routine bug fixes,
purely visual changes or decisions already dictated by an accepted ADR.

## Review process

1. Create the next numbered ADR with status **Proposed**.
2. Describe context, constraints, options and consequences.
3. Review it with the same stakeholders as the affected code.
4. Mark it **Accepted** or **Rejected** when a decision is reached.
5. Link implementation and later superseding ADRs without deleting history.

This directory starts with a template only. Historical decisions have not been
retroactively invented.
