import { CatEye } from "./CatEye";
import { type Mood, catOf } from "./catShapes";
import styles from "./Avatar.module.css";

export interface AvatarProps {
  /** Which face, 1–16 (design/brand/cats). Anything else is Glyphh's own. */
  variant?: number;
  mood?: Mood;
  size?: number;
  /** A picture in place of the face. */
  image?: string;
  label: string;
}

const INK = "var(--cat-ink, #0b0a0f)";
const WHITE = "#fff";

/** A super power's cat: its face, its mood in its eye, and the blink. */
export function Avatar({ variant = 1, mood = "idle", size = 40, image, label }: AvatarProps) {
  if (image) return <img className={styles.avatar} src={image} alt={label} width={size} height={size} draggable={false} />;
  const cat = catOf(variant, mood);
  return (
    <svg className={styles.avatar} data-mood={mood} data-variant={cat.id} viewBox="0 0 165 200" width={size}
      height={size} role="img" aria-label={label}>
      <g className={styles.body}>
        {cat.parts.extra === "cape" && <path d="M46 128 C30 140 16 162 10 182 L44 181 Z" fill={INK} stroke={WHITE} strokeWidth={7} />}
        <g fill={WHITE} stroke={WHITE} strokeWidth={16} strokeLinejoin="round">
          <path d={cat.body} /><path d={cat.leftEar} />
          {cat.parts.extra === "antenna" && <><path d="M86 46 L92 18" strokeWidth={20} strokeLinecap="round" /><circle cx={93} cy={14} r={9} /></>}
        </g>
        <path d={cat.body} fill={INK} stroke={INK} strokeWidth={1.5} strokeLinejoin="round" />
        <path d={cat.leftEar} fill={INK} stroke={INK} strokeWidth={1.5} strokeLinejoin="round" />
        <path d="M61 138 L99 150 L100 172 L51 171 Z" fill={WHITE} />
        {cat.parts.extra === "antenna" && <><path d="M86 46 L92 18" stroke={INK} strokeWidth={5} strokeLinecap="round" /><circle cx={93} cy={14} r={7} fill={INK} /></>}
        {cat.parts.extra === "bolt" && <path d="M74 142 L88 142 L82 152 L94 152 L72 170 L78 157 L68 157 Z" fill={INK} />}
        <CatEye eye={cat.eye} ink={INK} />
      </g>
    </svg>
  );
}
