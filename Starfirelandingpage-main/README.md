# Starfire Landing Page

Production-ready landing page workspace for Starfire, isolated from the rest of the monorepo.

This folder is intentionally self-contained and should be the **only** area touched for landing-page iteration.

## Quick Start

```bash
cd Starfirelandingpage-main
npm install
npm run dev
```

Open `http://localhost:5173`.

## Build

```bash
npm run build
```

## Directory Guide

```text
Starfirelandingpage-main/
├─ public/branding/                 # Logo assets (icon + white text logo)
├─ src/app/App.tsx                  # Page assembly
├─ src/app/components/              # Section components
│  ├─ Hero.tsx
│  ├─ MarketMomentum.tsx
│  ├─ UseCases.tsx
│  ├─ MemoryArchitecture.tsx
│  ├─ Enterprise.tsx
│  ├─ FinalCTA.tsx
│  ├─ Header.tsx
│  ├─ Footer.tsx
│  ├─ RotatingText.tsx
│  └─ background/
│     ├─ LandingBackground.tsx
│     ├─ ShapeGrid.tsx
│     └─ ShapeGrid.css
└─ src/styles/                      # Tailwind + theme overrides
```

## Team Handoff

Detailed continuation notes:

- [HANDOFF.md](./HANDOFF.md)
