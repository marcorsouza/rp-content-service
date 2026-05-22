# Agent Workflow

Before changing code, check the current branch.

- Do not develop directly on `main`.
- Start new work from an up-to-date `main`.
- Use branch prefixes:
  - `feature/<short-name>` for new functionality.
  - `bugfix/<short-name>` for normal fixes.
  - `hotfix/<short-name>` for urgent production fixes.
  - `release/<version>` for release stabilization, if a formal release flow is active.
- Push the branch and merge to `main` after validation.
- `main` is the deploy branch when this service is included in auto-deploy.

Typical start:

```bash
git switch main
git pull --ff-only
git switch -c feature/<short-name>
```
