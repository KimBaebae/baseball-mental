# Baseball Mental monorepo

- `apps/mobile`: Expo/React Native. Follow its AGENTS.md for SDK-specific changes.
- `apps/server`: Python/FastAPI/Beanie. Use uv and Python 3.13; keep dependencies locked.
- `contracts`: generated OpenAPI schema. Regenerate after API changes; never edit by hand.
- `infra`: local/container configuration; no paid resource creation without cost review.
- Public documentation describes the project, not personal background or conversation history.
- Never commit credentials, raw third-party responses, or personal notification tokens.
- Open browser-based account setup and authentication for this baseball project in the user's personal Chrome profile (`Hyeji`, Profile 2), not the work profile or the default browser.
- Keep source-data verification separate from production ingestion; do not infer unverified baseball events.
- Verify affected applications independently. Run mobile typecheck/lint/export after layout or workspace changes and server tests after API/storage changes.
