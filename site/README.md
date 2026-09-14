# gethired — product site

Premium product landing page for [gethired](https://github.com/sachncs/gethired).

- **Source:** `site/app/` (Vite + React + TypeScript + Tailwind CSS + Framer Motion)
- **Build output:** `site/dist/` (deployed to GitHub Pages)
- **Legacy Jekyll config:** `site/legacy/` (preserved for history)

## Develop

```bash
cd site/app
npm install
npm run dev          # http://localhost:5173
```

## Build

```bash
cd site/app
npm run build        # outputs ../dist
```

## Deploy

GitHub Actions (`.github/workflows/pages.yml`) builds on push to `main`
and publishes `site/dist/` to GitHub Pages.