# ADR-0001 — Maintain persistent agent memory and decision provenance

- **Date:** 2026-06-25
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** repository documentation and agent workflow

## Context

Work may be performed across multiple sessions or by different coding agents. Chat history alone is not a durable or efficient source of project context. Future contributors need to understand the current state, what was implemented, why significant decisions were made, and whether those decisions came from an explicit instruction, repository evidence, an external authority, or an agent assumption.

## Decision

Maintain repository-level agent instructions and persistent project memory using:

- `AGENTS.md` for durable operating rules;
- `docs/PROJECT_STATE.md` for the current project snapshot;
- one file per decision under `docs/adr/`;
- monthly implementation logs under `docs/worklog/`.

Every significant decision records its provenance. Decisions based only on an unconfirmed agent assumption remain `proposed` rather than `accepted`.

## Rationale

Separating current state, durable decisions, and chronological activity makes handoffs faster and prevents assumptions from becoming indistinguishable from explicit requirements. Individual ADR files and monthly worklogs also reduce merge conflicts and unnecessary context loading as the repository grows.

## Alternatives considered

- **Rely only on Git history:** rejected because commits rarely preserve full rationale, rejected alternatives, or assumption provenance.
- **Keep a single large ADR and worklog file:** rejected because they become expensive to search, create merge conflicts, and encourage loading irrelevant history.
- **Rely on conversation history:** rejected because it is not durable repository documentation and may be unavailable to another agent.
- **Document only in code comments:** rejected because comments explain local implementation, not project-level decisions or handoff state.

## Consequences and tradeoffs

### Positive

- Faster recovery of project context.
- Clear distinction between requirements, evidence, authority, and assumptions.
- Reusable documentation for human reviewers and other agents.
- Less repeated investigation and fewer contradictory decisions.

### Negative or limiting

- Non-trivial tasks require a small documentation overhead.
- Records must be kept concise and current to avoid becoming noise.
- Contributors must update indexes and supersession links when decisions change.

## Assumptions

- **Confirmed:** the repository will be used across multiple work sessions or agents.
- **Confirmed:** the user wants an ADR containing what was decided, why, and the source of the decision.
- **Unconfirmed:** none.

## Evidence and references

- User instruction requesting persistent implementation history, auditing, research, reduced visual trial and error, and ADR decision provenance.

## Follow-up actions

- [ ] Replace placeholder dates and project-state fields when these files are installed in a repository.
- [ ] Add the first monthly worklog entry during the first non-trivial repository task.
