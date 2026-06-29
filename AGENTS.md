# AGENTS.md

Repository-wide operating instructions for Codex and other coding agents.

These rules prioritize correctness, traceability, maintainability, and efficient use of context. Apply them proportionally to the task, but never skip security, data-integrity, Git-safety, or honest verification requirements.

## 1. Instruction Scope and Precedence

- This file applies to the entire repository.
- A nested `AGENTS.md` may add or override instructions for its own directory subtree.
- Follow the nearest applicable instructions when files disagree.
- Direct user instructions take precedence over repository guidance unless they would cause unsafe, destructive, or clearly incorrect behavior.
- Do not infer permission for destructive, remote, production, or irreversible actions.

## 2. Context Recovery Protocol

Before starting any non-trivial task:

1. Read the nearest applicable `AGENTS.md` files.
2. Read `docs/PROJECT_STATE.md`, if present.
3. Search `docs/adr/README.md` and relevant ADRs for decisions affecting the requested area.
4. Read only the latest relevant entries under `docs/worklog/`.
5. Inspect `git status`, the current branch, and relevant uncommitted diffs.
6. Identify unfinished work, known failures, provisional decisions, and unconfirmed assumptions.

Do not reconstruct documented project decisions from code or chat history alone.
Do not load the entire ADR or worklog history when targeted search is sufficient.
Treat `PROJECT_STATE.md` as a current snapshot, not as a substitute for repository inspection.

## 3. Think Before Coding

Before changing code:

- Read the relevant implementation, tests, types, schemas, configuration, and documentation.
- Establish the current behavior before proposing a new one.
- Define concrete success criteria.
- State material assumptions explicitly.
- Distinguish among:
  - `USER_INSTRUCTION`: explicitly requested or confirmed by the user;
  - `REPOSITORY_EVIDENCE`: supported by existing code, tests, configuration, or documented conventions;
  - `EXTERNAL_AUTHORITY`: required or supported by an official specification, vendor documentation, release note, or primary source;
  - `AGENT_ASSUMPTION`: selected because authoritative information is unavailable.
- Do not silently choose between materially different interpretations.
- Prefer the smallest reversible solution that fully satisfies the request.
- Push back when an approach introduces unnecessary complexity, duplication, security risk, data loss, or architectural inconsistency.

Ask for clarification only when ambiguity materially affects behavior, security, data integrity, compatibility, cost, or an irreversible decision. Otherwise, choose the smallest reversible option, label it provisional, and document it.

## 4. Focused Initial Audit

For every non-trivial task, perform a focused audit before editing.

Inspect only what is relevant:

1. Repository structure and applicable local instructions.
2. Existing implementation of the affected feature.
3. Related tests, types, schemas, migrations, APIs, dependencies, and configuration.
4. Existing conventions and module boundaries.
5. Git status and overlapping uncommitted work.
6. Relevant security, privacy, data-integrity, concurrency, compatibility, and deployment risks.

Before implementation, summarize briefly:

- current behavior;
- affected components;
- risks and unknowns;
- proposed minimal change;
- verification strategy.

Do not perform a repository-wide audit unless requested or genuinely required by the affected scope.

## 5. Research Before Guessing

Investigate when the answer is not reliably available in the repository.

Research is required when work depends on:

- external APIs, SDKs, providers, or protocols;
- framework or library behavior that may vary by version;
- security recommendations;
- platform-specific behavior;
- recently changed standards, dependencies, or vendor contracts;
- undocumented edge cases that affect correctness.

Research rules:

- Prefer primary sources: official documentation, specifications, release notes, and upstream source code.
- Confirm the installed version before applying online documentation.
- Record external sources that materially influence a decision in the relevant ADR.
- Stop researching once sufficient evidence exists to implement safely.
- Never invent APIs, flags, configuration keys, commands, library behavior, or provider guarantees.
- Clearly separate documented facts from inferences.

## 6. Plan With Verifiable Outcomes

For non-trivial work, use a short plan:

```text
1. [step] -> verify with [specific check]
2. [step] -> verify with [specific check]
3. [step] -> verify with [specific check]
```

Examples:

- Bug fix: reproduce with a focused test, implement the fix, run the focused test and relevant regressions.
- Endpoint: define contract, implement validation/authorization/persistence, run API tests.
- Refactor: establish a passing baseline, make behavior-preserving changes, rerun the same checks.
- UI change: identify state and DOM behavior, implement, verify deterministically, then perform only the necessary visual checks.

Avoid success criteria such as “make it work” or “looks good.”

## 7. Simplicity and Surgical Changes

Implement the minimum code needed to satisfy the verified requirement.

- Do not add speculative features.
- Do not introduce abstractions for a single use unless they enforce a real boundary or remove meaningful duplication.
- Do not refactor, rename, reformat, or modernize unrelated code.
- Match existing project style and architecture unless changing them is part of the task.
- Remove only imports, variables, files, and code made obsolete by your own changes.
- Mention unrelated issues in the handoff; do not fix them without authorization.
- Avoid fallback behavior that hides configuration or programming errors.
- Prefer explicit, boring, testable code over cleverness.

Every changed line must trace to:

- the user request;
- a required verification step;
- or a necessary security, integrity, compatibility, or reliability consequence of the implementation.

## 8. Efficient Context, Tool, and Token Use

Use repository evidence and deterministic checks before trial and error.

### Preferred order

1. Search for symbols, routes, types, tests, configuration, and usages.
2. Read only relevant files and ranges.
3. Inspect logs, static analysis, and existing test behavior.
4. Run the smallest focused check that can validate the current hypothesis.
5. Run broader regression checks after focused checks pass.
6. Use browser or visual inspection only when the behavior is genuinely visual or cannot be validated deterministically.

### Avoid wasteful behavior

- Do not reread large files when a targeted search or range is enough.
- Do not paste large logs into context; extract the relevant error and surrounding evidence.
- Do not retry an unchanged command after failure; form a new diagnosis first.
- Do not generate multiple near-identical implementations just to compare them by trial.
- Do not repeatedly render the same state without a new hypothesis, code/state change, viewport, or interaction.
- Do not run a full suite after every small edit.
- Stop investigating when sufficient evidence exists to proceed safely.

## 9. UI and Visual Verification Policy

For UI work, verify in this order:

1. component logic and application state;
2. type checking and focused unit tests;
3. DOM, accessibility, and event assertions;
4. console and network inspection;
5. focused browser automation;
6. screenshots or manual visual inspection.

Rules:

- Do not use screenshots to infer information available from the DOM, accessibility tree, logs, network responses, or application state.
- State the exact visual condition being checked before visual inspection.
- A repeated visual check requires a new hypothesis, implementation change, state, viewport, or interaction.
- Test only the breakpoints and states relevant to the requirement unless a full responsive audit was requested.
- Prefer one focused end-to-end path over broad manual exploration.
- Record visual verification as evidence, not as a replacement for deterministic checks.

## 10. Testing and Verification

Never claim success without evidence.

Use the strongest practical verification available:

- focused automated tests;
- type checking;
- linting;
- builds;
- schema or migration validation;
- deterministic reproduction scripts;
- focused API or integration checks;
- visual checks only for visual behavior.

Verification rules:

- Reproduce a bug before fixing it whenever practical.
- Test expected behavior and important failure paths.
- Check authorization, validation, consistency, retries, and idempotency when relevant.
- Do not change tests merely to accept incorrect behavior.
- Separate pre-existing failures from failures caused by the change.
- When a check cannot be run, state the exact reason and remaining risk.
- Never report “all tests pass” if only a subset ran.

For each reported check, record:

- exact command or procedure;
- affected scope;
- result and exit status when available;
- whether it ran before or after the change;
- skipped checks and reasons.

## 11. Security and Data-Integrity Review

For changes involving authentication, authorization, payments, webhooks, permissions, user input, external APIs, files, secrets, persistence, or background jobs, explicitly review:

- trust boundaries and authorization checks;
- input validation and output encoding;
- secret and credential handling;
- replay and duplicate-event protection;
- transactionality and partial failure;
- race conditions and concurrency;
- sensitive logging and privacy;
- retries, idempotency, and backoff;
- rollback, recovery, and reconciliation;
- production versus local behavior.

Do not rely on prompts, comments, frontend checks, or conventions as a security control when deterministic enforcement is possible.
Never log secrets, tokens, full payment data, or unnecessary personal information.

## 12. Dependency Policy

- Do not add or upgrade a dependency when the repository already provides a reasonable solution.
- Before adding one, document:
  - the capability it provides;
  - why existing code or dependencies are insufficient;
  - maintenance, licensing, bundle-size, and security implications when relevant;
  - the selected version and compatibility constraints.
- Do not perform broad dependency upgrades as part of an unrelated task.
- Keep manifests and lockfiles consistent.
- Do not remove dependencies solely because they appear unused without confirming build-time, plugin, generated-code, and runtime usage.
- Run the relevant audit or compatibility checks when available and proportionate.

## 13. Database and Migration Policy

- Never modify an already-applied migration unless explicitly instructed and the deployment model makes it safe.
- Prefer forward-only corrective migrations.
- Review backward compatibility, existing data, locking, indexes, rollback, and deployment order.
- Separate schema changes from destructive data cleanup when possible.
- Make data migrations restartable or idempotent when practical.
- Do not claim a migration is safe without testing realistic existing data or documenting why that validation was unavailable.
- Record irreversible or high-risk migrations in an ADR.

## 14. External Integrations and Side Effects

For emails, payments, shipping, webhooks, cloud resources, third-party APIs, and similar side effects:

- Prefer mocks, sandboxes, dry runs, or local emulators during development.
- Do not trigger real charges, messages, shipments, deletions, deployments, or production writes unless explicitly authorized.
- Verify environment and target account before executing side effects.
- Use idempotency and reconciliation where duplicate or partial execution is possible.
- Record vendor assumptions and contractual constraints in an ADR.

## 15. Persistent Project Memory

Maintain durable context so another contributor or agent can continue without reconstructing prior chat history.

Use:

- `docs/PROJECT_STATE.md`: current project snapshot, canonical commands, active work, known failures, constraints, and open decisions.
- `docs/adr/README.md`: ADR index.
- `docs/adr/NNNN-short-title.md`: one durable decision per file.
- `docs/worklog/YYYY-MM.md`: chronological monthly implementation log.

Create missing files from the repository templates.

### Required update timing

Update documentation:

- when a significant decision is made or changed;
- after a meaningful implementation milestone;
- when the implementation diverges from the plan;
- before ending a non-trivial task;
- before handing work to another agent.

Update `PROJECT_STATE.md` only when the current truth changes. Do not append chronological history there.

## 16. ADR Rules

Create an ADR when a decision affects:

- architecture or module boundaries;
- data model or persistence strategy;
- public APIs, events, or contracts;
- authentication, authorization, security, or privacy;
- external services or dependencies;
- deployment, infrastructure, observability, or CI/CD;
- performance, caching, concurrency, resilience, or reliability;
- migrations or irreversible data changes;
- a durable tradeoff future contributors may reasonably question.

Do not create an ADR for formatting, local variable names, routine bug fixes, or temporary implementation details with no durable tradeoff.

Each ADR must include:

- sequential ID and descriptive filename;
- date and status: `proposed`, `accepted`, `superseded`, or `rejected`;
- decision source using one or more provenance labels;
- context, decision, rationale, alternatives, consequences, and affected areas;
- assumptions labeled confirmed or unconfirmed;
- evidence and references;
- follow-up actions and superseded ADR when applicable.

### Assumption acceptance policy

A decision based only on an unconfirmed `AGENT_ASSUMPTION` must not be marked `accepted`.

Keep it `proposed` until one of these occurs:

- the user confirms it;
- repository evidence confirms it;
- an authoritative external specification confirms it.

When proceeding on an unconfirmed assumption:

- choose the smallest reversible option;
- state what could invalidate it;
- record how to change or revert it;
- list required confirmation in `PROJECT_STATE.md` and the worklog.

Never rewrite accepted history. When a decision changes, mark the old ADR `superseded`, create a new ADR, and update the index.

## 17. Worklog Rules

For every non-trivial task, append a concise entry to the current `docs/worklog/YYYY-MM.md` containing:

- date and task title;
- user goal;
- base branch/commit when relevant;
- scope inspected;
- plan and any deviations;
- files changed and behavioral summary;
- exact verification commands and results;
- ADRs created or updated;
- assumptions;
- rejected approaches or notable failures worth preventing from recurring;
- unresolved risks or TODOs;
- final working-tree and handoff state.

Do not log every command, typo, or transient failure. Record only information another contributor can reuse.
Link to ADRs instead of duplicating their rationale.

## 18. Project State Rules

Keep `docs/PROJECT_STATE.md` short and current.

Update only sections whose truth changed:

- last verified date and commit;
- architecture snapshot;
- important paths;
- canonical commands;
- active work;
- current constraints;
- known failures and technical debt;
- open decisions and unconfirmed assumptions;
- last completed meaningful work.

Remove or replace stale state instead of accumulating history.
Every important claim should be verifiable from the repository, a linked ADR, or a worklog entry.

## 19. Documentation Proportionality

Documentation must remain proportional to the change.

- Do not duplicate the same explanation across ADRs, worklogs, code comments, `PROJECT_STATE.md`, and the final response.
- Prefer links and references over repeated narrative.
- Keep worklog entries under roughly 50 lines unless the task genuinely needs more detail.
- Keep ADRs focused on one decision.
- Update only documentation affected by the change.
- Do not use documentation maintenance as a substitute for implementation or verification.

## 20. Git and Remote Safety

Assume uncommitted changes may belong to the user or another agent.

- Inspect `git status` before editing and before finishing.
- Do not discard, overwrite, reset, clean, or reformat changes you did not create.
- Keep your changes separable from unrelated work.
- When a file has overlapping edits, modify it carefully and report the overlap.
- Do not commit, amend, rebase, merge, cherry-pick, tag, push, force-push, change branches, or create pull requests unless explicitly requested.
- Never use destructive Git commands solely to obtain a clean working tree.
- Inspect the final diff and identify unrelated changes.

## 21. Communication During Work

For non-trivial tasks, communicate at useful milestones rather than after every command.

Report:

- focused audit findings;
- material assumptions;
- discovered blockers or risks;
- meaningful plan changes;
- partial findings that affect the solution;
- completion and verification status.

Do not flood the user with low-level logs or repeat the same status.

## 22. Definition of Done

A task is complete only when:

- the requested behavior is implemented;
- the final diff has no unexplained unrelated changes;
- relevant focused checks pass, or limitations are documented;
- broader regressions were run when justified;
- security and data-integrity implications were reviewed when applicable;
- changed contracts and behavior are documented;
- significant decisions are reflected in ADRs;
- the worklog contains reproducible verification evidence;
- `PROJECT_STATE.md` reflects changes to current project state;
- assumptions, unfinished work, and real risks are explicit.

## 23. Final Response Format

End non-trivial tasks with:

### Implemented
Concise summary of changed behavior and files.

### Verified
Exact checks run and outcomes. Distinguish focused from full-suite verification.

### Decisions
ADR IDs created or updated and their provenance.

### Remaining risks
Only unresolved issues, skipped checks, provisional assumptions, or follow-up work.
