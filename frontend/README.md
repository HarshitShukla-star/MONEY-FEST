# MONEY-FEST Web

The isolated Next.js operator console for the MONEY-FEST Python backend. It contains no backend code and currently uses mock asynchronous services in `lib/mock-api.ts`.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

## API integration

Replace the methods in `lib/mock-api.ts` with typed HTTP calls when an API layer is introduced. All page data is requested through TanStack Query, so loading, polling, caching, and invalidation can remain at the UI boundary.
