# Landing Page Handoff

Last updated: 2026-04-07

## 1) Scope Guardrails

- This landing implementation is isolated under `Starfirelandingpage-main/`.
- Do not edit `platform/`, `canvas/`, `workspace-template/` for landing-only tasks.
- Commit scope should remain under `Starfirelandingpage-main/**`.

## 2) Current Section Structure

The page is assembled in [`src/app/App.tsx`](./src/app/App.tsx):

1. `Header`
2. `Hero`
3. `MarketMomentum`
4. `UseCases`
5. `MemoryArchitecture`
6. `Enterprise` (advantages)
7. `FinalCTA`
8. `Footer`

## 3) Visual System (Current)

- Overall style: dark, cold-tone, logo-aligned blue/cyan palette
- Primary emphasis gradient: `from-sky-300 via-blue-300 to-cyan-200`
- Background shape effect: top-only `ShapeGrid` in [`LandingBackground.tsx`](./src/app/components/background/LandingBackground.tsx)
- Accessibility pass: gray text classes were raised to higher contrast in [`src/styles/theme.css`](./src/styles/theme.css)

## 4) Key Components

## `Hero.tsx`
- Main positioning statement + primary CTA
- The short tagline row was intentionally removed and replaced with a full descriptive sentence

## `UseCases.tsx`
- Scenario tabs retained
- Rotating headline uses [`RotatingText.tsx`](./src/app/components/RotatingText.tsx)
- Emphasis strip uses logo-theme gradient

## `MemoryArchitecture.tsx`
- Dedicated promotional section for HMA
- Messaging based on project docs:
  - L1 local memory
  - L2 team shared memory
  - L3 corporate memory

## `Enterprise.tsx`
- Alternating left-right layout
- Image panel is now standard slider (no folding collage)
- Features:
  - left/right arrow controls
  - dot pagination
  - fixed `16:9` frame

## `FinalCTA.tsx`
- Non-rotating conversion block
- Uses original “Design your AI org chart” intent with stronger hierarchy and conversion emphasis

## 5) Placeholder Media Policy

- Current images are placeholders and explicitly labeled `Placeholder Media`.
- Replace image URLs in:
  - [`UseCases.tsx`](./src/app/components/UseCases.tsx)
  - [`Enterprise.tsx`](./src/app/components/Enterprise.tsx)
- Keep aspect ratios unchanged unless design review approves a layout refactor.

## 6) Branding Assets

Stored in [`public/branding`](./public/branding):

- `starfire-logo.png` (icon)
- `starfire-text-logo-white.png` (white transparent text logo)
- `starfire-text-logo.png` (legacy text logo; optional fallback)

Header currently renders icon + white text logo together.

## 7) Cleanup Already Done

- Removed unused legacy sections and unused component bundles:
  - old section components (`Problem`, `Architecture`, `Differentiators`, `Comparison`, `OrgTopology`)
  - unused `ui/` and `figma/` directories
- Removed empty placeholder docs in `guidelines/`

## 8) Recommended Next Tasks

1. Replace placeholder media with real Starfire product captures
2. Add simple auto-play + pause-on-hover for advantage slider (optional)
3. Add section-level analytics events for CTA clicks
4. Snapshot visual regression baseline after media replacement

## 9) QA Checklist Before Merge

- `npm run build` passes
- Hero + CTA copy remains aligned with Starfire core positioning
- Contrast remains readable on dark backgrounds
- Mobile view checks:
  - `375px` width
  - `768px` width
  - `1280px` width
