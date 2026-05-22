# frontend

Angular 17+ — contracting-officer UX surface.

## Build + run (local)

```bash
npm install
npm start
# → http://localhost:4200
```

Talks to api-gateway at `http://localhost:8080` per `environment.ts` —
**except** the one component that hardcodes the solicitation-service URL
directly (Item 8).

## Brownfield-debt items present in this service

- **Item 8** — `SolicitationListComponent` hardcodes `http://localhost:8081/api/solicitations`
  bypassing the gateway.
- **Item 8 reinforcement** — `/reports` nav link points to a route with no
  registered component; clicking produces a routing error.
- **Item 9 reinforcement** — `SolicitationCreateComponent` form has no
  validation (no `required`, no `maxlength`, no HTML-strip). Pairs with
  backend's `description` accepting raw HTML.
- **Item 11** — `Dockerfile` uses `node:latest` and `nginx:latest`.

See `docs/brownfield-debt.md` for the full inventory.
