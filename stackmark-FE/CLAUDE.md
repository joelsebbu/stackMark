# stackmark-FE

Astro frontend for the StackMark project.

## Commands

```bash
npm run dev      # start dev server
npm run build    # production build → dist/
npm run preview  # preview production build
```

## Structure

```
src/
  pages/       # file-based routing (.astro files)
  layouts/     # shared page layouts
  components/  # reusable UI components
public/        # static assets (copied as-is to dist/)
dist/          # build output (gitignored)
```

## Notes

- Built with Astro 4.x
- Pages live in `src/pages/` — each `.astro` file maps to a route
- Shared layout is in `src/layouts/Layout.astro`

## Colors and theme

**Always centralize colors.** Do not sprinkle raw `#hex` or ad-hoc `rgba(...)` in pages, layouts, or component styles.

- **`src/styles/theme.css`** — canonical palette. Define tokens on `:root` (`--navy`, `--orange`, `--text-primary`, `--shadow-search-bar`, focus rings, etc.). Import it once from `Layout.astro` (already done). In `.astro` `<style>` blocks and CSS files, use `var(--token-name)` only.
- **`src/lib/theme-chrome.ts`** — `THEME_COLOR_NAVY` and any future values needed where HTML or JSON cannot use CSS variables (for example `<meta name="theme-color">`). Keep the navy hex in sync with `--navy` in `theme.css` (see the comment next to `--navy`).
- **`public/`** (manifest, SVG icons) — static files cannot use `var()`. When you change a brand color, update those files to match `theme.css` / `theme-chrome.ts`.
- **TypeScript** that needs colors (for example canvas/WebGL) should read from the DOM after CSS is applied (see `src/lib/vanta-dots.ts` and `cssHexVarToRgbInt`) or stay aligned with the same tokens.

## Guardrails (do not regress)

These are intentional UX/product choices. Re-read this section before changing auth UI or `Layout.astro`.

### Login page (`/login`, `activeTab="login"`)

- **Do not** show the global nav **Sign in** link (`#nav-auth-slot` / `#nav-auth-link`) on the login page. Users are already on the sign-in screen; a second “Sign in” is redundant and confusing.
- Implementation: the auth slot is omitted from the layout when `activeTab === "login"` (see `src/layouts/Layout.astro`). Do not reintroduce a duplicate sign-in control in `login.astro` either.

Entry point: [`rules.md`](rules.md) in this folder points here for FE-specific guardrails.
