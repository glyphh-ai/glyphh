# app_react

A React page published to the organisation: one `.tsx` file, nothing behind it.

- **What it is:** `index.tsx`, a component with a recharts bar chart of static numbers and Tailwind classes, as
  claude.ai's React artifacts are written. rrotor serves it in its React shell at
  `https://<host>/apps/deploys_chart/` to anyone signed in to Glyphh for that rrotor (`"roles": []`), once a
  reviewer has approved it. The type is `page` (`app.type`; a `.tsx` entry is a page when none is said).
- **No build.** The shell is an HTML page with an import map sending `react`, `react-dom`, `recharts`,
  `lucide-react`, `d3`, `three`, `framer-motion`, `date-fns`, `lodash`, `papaparse`, `mathjs` and `@radix-ui/*` to
  esm.sh (the React family, one React on the page) and jsDelivr (the rest), the Tailwind CDN, and Babel transforming
  the file in the browser (the automatic JSX runtime, and TypeScript for `.tsx`);
  the default export is mounted into `#root`. A package outside that list fails in the browser, as on claude.ai.
- **What it calls:** nothing. For live numbers, make each chart a function the page calls as the viewer
  (`programs/app_dashboard`) and say `"type": "dashboard"`.

## Publish it

Ask Claude to *"publish programs/app_react to my org"* (the plugin's `publish` skill), or from the mod:
`/glyphh publish programs/app_react/index.tsx --name deploys-chart --title "Deploys this week"`. The app waits for
review in the organisation's catalogue (the platform's Apps page, the `apps` tool in Claude, or `/glyphh apps`).
