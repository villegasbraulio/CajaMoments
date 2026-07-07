# ADR-0012: Material UI Backoffice Shell

- **Date:** 2026-07-07
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE

## Context

The frontend was a single React/Vite file using Bootstrap-loaded classes and custom CSS. The user requested a more professional production backoffice, popup notifications, transitions, a better menu, and Material UI.

## Decision

Adopt Material UI for the app shell and shared controls:

- `@mui/material` and Emotion for components/theme.
- `@mui/icons-material` available for future icon buttons.
- Material theme, permanent drawer menu, app bar, screen fade transition, Snackbar notifications.
- Shared text/select/table/header components migrated to MUI while keeping existing screen logic.

## Rationale

Material UI provides production-grade primitives for navigation, forms, tables, alerts, and theming without building a design system from scratch. Migrating shared primitives changes the whole app with the smallest safe diff.

## Alternatives

- Keep Bootstrap/custom CSS: rejected by user instruction.
- Rewrite every screen into separate route/component files now: deferred because it is a much larger refactor with little immediate business behavior gain.

## Consequences

- Added dependencies: `@mui/material@^9.2.0`, `@mui/icons-material@^9.2.0`, `@emotion/react@^11.14.0`, `@emotion/styled@^11.14.1`.
- Production JS bundle is larger; Vite warns at ~519 KB minified.
- Existing Bootstrap CDN remains temporarily because many screen layouts still use Bootstrap grid utility classes.
- `npm audit` reports Vite/esbuild dev-server advisories; automatic fix requires a breaking Vite major upgrade.
- Vite splits React, Material UI, and other vendor dependencies into separate chunks.

## Affected Areas

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/App.jsx`
- `frontend/src/styles.css`

## Assumptions

- **Confirmed:** Material UI is required by user instruction.
- **Unconfirmed:** whether the app should remove Bootstrap entirely in this same release.

## Evidence and References

- User instruction on 2026-07-07.
- Existing frontend is a React/Vite SPA with shared local form/table helpers.

## Follow-up Actions

- Remove Bootstrap CDN after replacing remaining grid utility classes.
- Plan Vite major upgrade separately to resolve dev-server audit advisories.
