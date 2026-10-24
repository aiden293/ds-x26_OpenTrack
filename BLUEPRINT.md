# Basic repository blueprint

## Purpose

Start a shared GitHub repository for Civic Pulse, based on the brainstorming document's idea of forecasting Boston 311 request resolution times.

## Step 1: Get the repository online

- [x] Add a short project README.
- [x] Record the initial scope and next task.
- [x] Add a `.gitignore` for secrets, local datasets, and generated files.
- [x] Identify the team's GitHub repository: https://github.com/aiden293/ds-x26_OpenTrack.
- [x] Connect this folder to that repository.
- [x] Publish the initial files on `main`.
- [ ] Give teammates access.

Done means teammates can open the repository, understand the idea, and clone it.

## Step 2: First task after setup

Choose one Boston 311 dataset and document its source, date range, usage terms, and actual column names. Check whether it contains:

- Request creation time.
- Request closure time and status.
- Request category.
- Neighborhood or another usable location field.
- An SLA target date, if available.

Start with one request category. For valid closed requests, calculate elapsed time between creation and closure and report the median. Keep open requests separate; do not treat them as having zero resolution time.

This establishes a simple baseline before building a forecasting model.

## Later ideas

- Compare estimates with observed resolution times on later records.
- Add a small interface for viewing estimates.
- Explore weather as an additional input.
- Compare estimates with documented service targets.

Historical patterns may suggest factors associated with delays; they do not establish the actual reason for an individual delay. The brainstorming document's example deadlines and accuracy figures are illustrative and need verification.

## Decisions still open

- Dataset and first request category.
- Technology stack, chosen once the data has been inspected.
