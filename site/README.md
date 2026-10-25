# Networth site

The web dashboard and chat for Networth. It reads only the JSON API in `networth/web/api.py`
(see `docs/phases/phase-8-contract.md`) from its own server, renders what comes back, and never
computes a number, calls a model or holds an API key.

```sh
npm ci
NETWORTH_API_URL=http://127.0.0.1:8000 npm run dev   # the Python server's base URL
npm run build && npm run lint && npm run typecheck && npm run check:build
npx playwright test                                   # against e2e/mock-api.mjs
SHOTS=1 npx playwright test e2e/shots.spec.ts         # refresh docs/phases/phase-8-shots/
```

`NETWORTH_API_URL` is server-only. Never give it a `NEXT_PUBLIC_` prefix.
