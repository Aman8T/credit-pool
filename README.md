# Credit Pool

A Next.js application for creating shared credit pools and allocating credits.

## Development

```bash
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

## Scripts

| Command | Description |
| --- | --- |
| `pnpm dev` | Start the development server |
| `pnpm build` | Create a production build |
| `pnpm start` | Run the production server |
| `pnpm lint` | Run ESLint |

## API

- `GET /api/pools` — list credit pools
- `POST /api/pools` — create a pool (`{ "name": "...", "totalCredits": 1000 }`)
- `POST /api/pools/:id/allocate` — allocate credits (`{ "amount": 100 }`)

SQLite data is stored in `data/credit-pool.db`.
