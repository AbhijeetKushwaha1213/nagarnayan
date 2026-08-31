# Nagar Nayan — Urban Operations Intelligence Platform

> **Nagar Nayan** — *"The Eyes of the City."*
> Public transport buses become distributed mobile sensing units. Edge AI turns
> onboard camera video into structured urban events; this platform turns those
> events into actionable operational intelligence.

This repository contains the **frontend** — the central command platform used by
city, transport, traffic and maintenance authorities.

## Tech stack

- **React 19 + TypeScript + Vite**
- **Tailwind CSS v4** (design tokens defined in `src/index.css` via `@theme`)
- **Leaflet + react-leaflet** — the GIS map is a primary operational surface, not decoration
- **TanStack Query** — server-state layer (mock today, backend-swap-ready)
- **Recharts** — analytics visualizations
- **React Router** — app shell + routing
- **lucide-react** — iconography

## Getting started

```bash
npm install
npm run dev
```

Then open http://localhost:5173.

Other scripts:

```bash
npm run build      # type-check + production build
npm run typecheck  # tsc only
npm run preview    # preview the production build
```

> **Note on the sandbox:** dependency install requires access to
> `registry.npmjs.org`. If you're running inside a restricted sandbox that blocks
> the npm registry, run `npm install` in a normal terminal (or allow the host)
> before `npm run dev`.

## Architecture

Feature-based, with a strict separation of UI / data / domain so the mock data
layer can be replaced by real API calls without touching components.

```
src/
├── types/domain.ts          # Typed domain model (UrbanEvent, FleetBus, …)
├── config/
│   ├── taxonomy.ts          # Event types, categories, severity/status metadata
│   └── nav.ts               # Sidebar navigation model
├── mock/                    # Realistic mock data (Prayagraj), anchored to real geo
│   ├── city.ts  events.ts  fleet.ts  traffic.ts
├── services/
│   ├── api.ts               # Data-access layer — mirrors future FastAPI endpoints
│   └── hooks.ts             # TanStack Query hooks (the only thing components call)
├── components/
│   ├── layout/              # Sidebar, Header, DashboardLayout, Page shells
│   ├── map/                 # CityMap, MapPanel, MapFilters, markers
│   ├── events/              # EventCard, EventTable, EventDetailPanel, badges
│   ├── analytics/           # MetricCard, charts
│   ├── fleet/               # BusCard
│   └── workspace/           # CategoryWorkspace (shared intelligence-page layout)
└── pages/                   # One file per route
```

### Backend integration

`src/services/api.ts` is the single integration seam. Each function maps to a
planned endpoint:

| Function              | Endpoint                     |
| --------------------- | ---------------------------- |
| `listEvents()`        | `GET /api/events`            |
| `getEvent(id)`        | `GET /api/events/{id}`       |
| `listFleet()`         | `GET /api/fleet`             |
| `getTraffic()`        | `GET /api/traffic`           |
| `getTrends()`         | `GET /api/analytics`         |
| `getCommandMetrics()` | `GET /api/summary`           |

Real-time detections will arrive over a **WebSocket** and push into the same
TanStack Query cache — components need no changes.

## Design language

Professional, precise, calm, high-information-density — built to feel like software
inside a real city command center. Hybrid surface model: **dark command sidebar +
light content dashboard + dark operational map**. Semantic color: blue = info,
amber = warning, red = critical, green = resolved/healthy.

## Modules

| Route             | Status        |
| ----------------- | ------------- |
| Command Center    | ✅ Built       |
| Live Map          | ✅ Built       |
| Road Intelligence | ✅ Built       |
| Traffic Intelligence | ✅ Built    |
| Infrastructure    | ✅ Built       |
| Safety & Incidents | ✅ Built      |
| Fleet Coverage    | ✅ Built       |
| Analytics         | ✅ Built       |
| Alerts            | ✅ Built       |
| System Settings   | 🚧 Stub        |
