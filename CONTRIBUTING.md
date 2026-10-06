# Working rules
- `main` is protected. `dev` is the integration branch. Open PRs into `dev`.
- Branch names: `feature/<area>-<short-description>` (example: `feature/api-mock-endpoint`).
- The team lead approves every PR. Author squash-merges after approval.
- Lead merges `dev` into `main` once, after the Day 3 integration test.
- No secrets or real user data in the repo. Use `.env` (see `.env.example`).
- Schema changes only through the team lead.

# Who owns what
| Folder | Owner |
|---|---|
| app/schemas, app/core, app/safety | Team lead |
| app/rag | AI/ML 2 |
| route and generate in app/core | AI/ML 3 |
| data/ (synthetic profiles, test conversations) | AI/ML 1 |
| app/api, Docker | DevOps 1 |
| .github, deployment, docs/ | DevOps 2 |
