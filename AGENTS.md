# Agent Workflow

Before changing code, check the current branch.

- Do not develop directly on `main`.
- Start new work from `develop`.
- Use branch prefixes:
  - `feature/<short-name>` for new functionality.
  - `bugfix/<short-name>` for normal fixes.
  - `hotfix/<short-name>` for urgent production fixes.
  - `release/<version>` for release stabilization.
- Push the branch and merge through `develop` first.
- `develop` is the integration branch.
- `main` is the stable branch.

Typical start:

```bash
git switch develop
git pull --ff-only
git switch -c feature/<short-name>
```
