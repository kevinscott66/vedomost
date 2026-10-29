# Cloudflare demo

Public demo: https://dobropalm.tech/demos/vedomost/. Backup address: https://vedomost-demo.dobropalm.workers.dev/demos/vedomost/.

The hosted adapter uses FastAPI in a Python Worker and D1. Each visitor receives a random 64-character session token in a Secure/HttpOnly/SameSite=Strict cookie scoped to the demo path. D1 stores a bounded ledger document plus a version; conditional updates retry on conflicts. Each visit renews the session and cookie for 90 days without changing ledger contents. After 90 days without visits, access expires; hourly cleanup removes the records within another hour. Limits: 100 students, 1,000 payments and 1,000 idempotency keys and 3,000 activity events per session; request body 16 KiB and stored state 1 MB. Hashed rate-limit buckets expire and are cleaned within three hours. Only fictional data is allowed.

Session bootstrap is serialized across tabs with an origin-scoped Web Lock: the next tab sends its request only after the previous response installs the cookie. Browsers without Web Locks can renew an existing session, but cannot create a new one; the UI asks visitors to update their browser. This prevents competing first-visit cookies without weakening visitor isolation.

The localhost SQLite API remains unchanged. `cloud/domain.py` implements the hosted ledger contract; `cloud/worker.py` handles HTTP, D1, cookies, rate loading and assets. `cloud/build_assets.py` generates ignored `public/`, `src/` and the FX source copy from the canonical app. The public Worker serves the case and teaching scenario described below; the separate static portfolio export remains an unpublished historical experiment.

Payments retain original currency, original amount, booked UZS amount and the exact rate/date/source used. Updating display rates does not rewrite these records. Official rates are fetched through Workers fetch from CBU, then CBR on failure. A fresh quote is cached for one hour; failed refreshes back off for five minutes. Foreign-currency booking requires a fresh quote. UZS booking remains available during source failures.

## Build and deploy

The Worker environment in `cloud/pyproject.toml` requires Python 3.13+ and uses its own `cloud/uv.lock`; the root Python 3.11/3.13 CI matrix covers the local application and adapter tests, not a Worker runtime deployment. Run from the repository root:

```sh
.venv/bin/python cloud/build_assets.py
uv tool run --from 'uv>=0.13.4' uv run --directory cloud pywrangler deploy
```

D1 schema is in `cloud/schema.sql`; binding and route are in `cloud/wrangler.jsonc`. Apply the schema before the first deployment using `wrangler d1 execute vedomost-demo --remote --file cloud/schema.sql --config cloud/wrangler.jsonc`. The Worker uses the Free plan's standard CPU limit; no paid upgrade is configured. Bundled upload is about 2.31 MiB compressed.

The root domain's eight A/AAAA records were switched to Proxied with the owner's approval. GitHub Pages remains the origin for paths outside `/demos/vedomost*`. Mail records and subdomains were not changed. The Worker route is specific to the demo path.

## Release 29 October 2026

Published the trilingual case and isolated teaching scenario, updated visual identity, responsive cards and accessible dialog headings. Statement requests use the same session/base-path wrapper as other API requests. No schema migration.

## Historical verification of the published demo

92 pytest and 42 JavaScript tests pass. Cross-tab bootstrap tests cover delayed cookie installation in two independent contexts and safe renewal without Web Locks. Session-renewal tests confirm the same cookie and ledger persist across reopening, while expired sessions are not revived. Actual local Workers/Pyodide and local D1 verified asset routes, session initialization, persistence and concurrent idempotency. Public Workers verification confirmed isolated visitors, persistence, four concurrent payment retries producing one record, CSRF rejection, and foreign-payment snapshots. A 1.25 USD test payment booked 14,827.44 UZS with the exact CBR rate dated 2026-10-28. Test sessions were deleted afterwards. Public official FX refresh succeeded through CBR. The domain route also passed the public API checks when resolving the hostname to its current Cloudflare address. Some resolvers still returned cached GitHub addresses immediately after the DNS change. The browser verified the Workers URL and RUB display; [published screenshot](cloud-demo.png).

The official Pyodide download required a command-scoped NO_PROXY setting for GitHub release hosts in this environment; TLS validation remained enabled. Deployments must use pywrangler rather than directly bundling the Python virtual environment with Wrangler.

Payment cancellation and activity use the existing versioned session document. Legacy session states without activity remain valid; no D1 schema migration. GET /activity and POST /payments/{id}/void are covered by the same cookie isolation, body/origin checks and conditional updates as other ledger routes.
