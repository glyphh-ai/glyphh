# demo.glyphh.ai/screener

One thing in, one thing out: a resume and a cover letter (either may be missing) in; how close they are to real
people's and to fakes out, with Ada's decision, its confidence and its fact tree. The route is
`server/screener.ts`; the page is `demo/public/screener`.

## One source

The page does not have its own copy of the check. The image fetches the Resume Screener plugin's skill folder from
the public repository (github.com/glyphh-ai/plugins, `plugins/resume-screener/skills/screen-application`) at the
commit in `plugin.ref`, and the route runs the plugin's own `scripts/check.py` on each request. To move the demo to
a newer plugin, change `plugin.ref` to that commit and deploy.

## Nothing is stored

The upload is held in memory, passed to `check.py` on its standard input, and dropped when the answer is sent. No
file is written and nothing is recorded in a model (`check.py` only asks).

## The model, and seeding it

The answer comes from one Ada model in the demo's org, `demo-screener-closeness`
(the plugin's `docs/closeness-model.md` is its whole spec). After a deploy that changes `plugin.ref`, on the
platform machine:

```
GLYPHH_API_KEY=$DEMO_GLYPHH_API_KEY python3 /opt/screener/scripts/seed.py --prefix demo-screener-
```

It makes the models that are missing and loads the plugin's 1,980 generated examples into
`demo-screener-closeness` as fakes. It can be run again safely.

**Once, when moving from the first version of this demo:** that version kept the examples in
`demo-screener-others`. Delete it first, so it is made again empty:

```
GLYPHH_API_KEY=$DEMO_GLYPHH_API_KEY glyphh delete demo-screener-others --confirm demo-screener-others
```

**The real side.** The plugin ships no real resumes. Without any, the page shows "closest real: none held" and
says only how close a resume is to fakes. To give the demo a real side, put resumes (PDF, DOCX or text) that Glyphh
has the right to use in a folder on the machine and run:

```
GLYPHH_API_KEY=$DEMO_GLYPHH_API_KEY python3 /opt/screener/scripts/seed.py --prefix demo-screener- --real <folder>
```

Only the words of each resume's sections are kept, under a label that is the source, never a name.

Optional settings: `DEMO_SCREENER_DAILY` (checks a day for the whole page, default 300) and
`DEMO_SCREENER_SCRIPTS` (where the plugin's scripts are, default `/opt/screener/scripts`).
