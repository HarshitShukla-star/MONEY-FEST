# MONEY-FEST Web

The isolated Next.js operator console for the MONEY-FEST Python backend. It now talks to the local Python JSON API instead of hard-coded mock arrays.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

## API integration

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if your backend API is not on `http://127.0.0.1:8000`. All page data is requested through TanStack Query, so loading, polling, caching, and invalidation can remain at the UI boundary.
