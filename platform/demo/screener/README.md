# demo.glyphh.ai/screener

The Resume Screener on a page: paste an application's email, attach the cover letter and the resume, see the
verdict. The route is `server/screener.ts`; the page is `demo/public/screener`.

## One source

The page does not have its own copy of the screener. The image fetches the Resume Screener plugin's skill folder
from the public repository (github.com/glyphh-ai/plugins, `plugins/resume-screener/skills/screen-application`) at
the commit in `plugin.ref`, and the route runs the plugin's own `scripts/run.py` on each request. To move the demo
to a newer plugin, change `plugin.ref` to that commit and deploy.

## Nothing is stored

The upload is held in memory, passed to `run.py` on its standard input, and dropped when the answer is sent. No
file is written and the application is not recorded in any model (`run.py` records only with `--keep`, which the
route never passes).

## To go live

1. The demo's Ada key is the one the other demos use (`DEMO_GLYPHH_API_KEY`). Nothing new to set.
2. Seed the demo's models once, from a machine with the plugin checked out at `plugin.ref`, with the demo's key:

   ```
   pip install glyphh pypdf
   GLYPHH_API_KEY=<the demo's key> python plugins/resume-screener/skills/screen-application/scripts/seed.py --prefix demo-screener-
   ```

   It makes `demo-screener-fit`, `-made`, `-others`, `-files`, `-timing` and `-greenhouse` in the demo's org, loads
   the plugin's examples and runs learning. It can be run again safely. The demo org's plan must allow six more
   models and about 6,000 more precedents.
3. Deploy. The image now also carries Python, `glyphh` and `pypdf`.

Optional settings: `DEMO_SCREENER_DAILY` (screenings a day for the whole page, default 300) and
`DEMO_SCREENER_SCRIPTS` (where the plugin's scripts are, default `/opt/screener/scripts`).
