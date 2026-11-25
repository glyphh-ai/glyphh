# Ada, live: expense approvals

A standalone demo for the launch video. Ada decides expense claims from 40 past decisions, says when she isn't
sure, and learns from one correction. It runs against the real model `launch-demo-expenses` in your Glyphh
account, through the Glyphh SDK. Every answer on screen is Ada Cloud's.

## Run it

```bash
npm install
GLYPHH_API_KEY=glyphh_ak_your_key npm start
```

Then open http://localhost:4321 full screen at 1920×1080. Make the key at platform.glyphh.ai → API Keys.

On start, the server makes sure `launch-demo-expenses` exists and holds the 40 past expenses in `history.json`.
**Reset demo** puts it back to exactly those 40, which removes anything decided during a take.

## The take (about three minutes)

| Click | Ada, as rehearsed on the model |
|---|---|
| **Uber to JFK · $62**, Ask Ada | **Approve**, 98%, from three Uber and taxi rides |
| **Business class to London · $2,400**, Ask Ada | **Reject**, 79%, from the rejected business-class flight to New York |
| **Coffee, receipt lost · $30**, Ask Ada | **Not sure**, 72% leaning reject, under her 75% bar: two rejected meals without receipts |
| **Reject it**, then **Ask again** | **Reject**, 84%, from the decision you just recorded |
| **Uber to JFK** again | The same answer, and "Asked 2× · the same answer every time" |

The milliseconds shown are the round trip from your machine to Ada Cloud.

## Files

- `server.mjs`: holds the key, calls Ada Cloud with the SDK (`@glyphh-ai/glyphh`), serves the page.
- `history.json`: the 40 past expenses, under one written-down policy (receipts over $25; limits per category;
  over the limit needs pre-approval; conferences always do).
- `public/`: the page.
