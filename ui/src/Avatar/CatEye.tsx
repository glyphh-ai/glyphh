import type { Eye } from "./catShapes";

const WHITE = "#fff";
const RING = "M45 104 C43 89 70 66 96 64 C116 62 124 80 121 97 C118 116 100 126 86 122 C70 118 47 112 45 104 Z";

function Ring() {
  return <path d={RING} fill="none" stroke={WHITE} strokeWidth={8} />;
}

/** One group, so the blink shuts pupil and glint together. */
function Pupil({ cx, cy, r = 12, ink }: { cx: number; cy: number; r?: number; ink: string }) {
  return (
    <g className="eye">
      <circle cx={cx} cy={cy} r={r} fill={WHITE} />
      <circle cx={cx + r * 0.35} cy={cy - r * 0.35} r={Math.max(3, r * 0.3)} fill={ink} />
    </g>
  );
}

/** The eye makes the character: the ringed eye, or the mood's own. */
export function CatEye({ eye, ink }: { eye: Eye; ink: string }) {
  switch (eye) {
    case "look": return <><Ring /><Pupil cx={68} cy={97} ink={ink} /></>;
    case "up": return <><Ring /><Pupil cx={94} cy={80} ink={ink} /></>;
    case "big": return <><Ring /><Pupil cx={88} cy={94} r={19} ink={ink} /></>;
    case "sleepy": return (
      <><path d="M45 104 C60 96 100 90 121 97 C118 116 100 126 86 122 C70 118 47 112 45 104 Z" fill="none" stroke={WHITE} strokeWidth={8} />
        <circle className="eye" cx={92} cy={107} r={9} fill={WHITE} /></>);
    case "wink": return (
      <><Ring /><path d="M66 96 Q92 114 118 96" fill="none" stroke={WHITE} strokeWidth={9} strokeLinecap="round" />
        <path d="M75 106 L70 114 M92 110 L92 119 M109 106 L114 114" stroke={WHITE} strokeWidth={5} strokeLinecap="round" />
        <path d="M104 70 L106.5 76.5 L113 79 L106.5 81.5 L104 88 L101.5 81.5 L95 79 L101.5 76.5 Z" fill={WHITE} /></>);
    case "star": return (
      <><Ring /><path className="eye" d="M93 77 L97.8 87.6 L109 88.3 L100.4 95.6 L103 106.8 L93 100.8 L83 106.8 L85.6 95.6 L77 88.3 L88.2 87.6 Z" fill={WHITE} /></>);
    default: return <><Ring /><Pupil cx={92} cy={94} ink={ink} /></>;
  }
}
