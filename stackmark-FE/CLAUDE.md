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
