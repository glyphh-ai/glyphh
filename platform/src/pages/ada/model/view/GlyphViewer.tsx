import { useEffect, useRef, useState, type PointerEvent } from 'react';
import type { ModelMap } from '@/api/ada';
import { reducedMotion } from '@/lib/tokens';
import { nearestOnScreen } from './glyphs';
import { GlyphScene, type Look } from './scene';
import styles from './view.module.css';

type ViewerProps = Look & {
  map: ModelMap;
  groups: number[];
  frozen: boolean;
  labels: boolean;
  /** The point the camera turns about, once chosen. */
  focus: number | null;
  onPick: (index: number | null) => void;
};

/** Labels for every point while there are this few, else for the highlighted ones only. */
const LABEL_ALL = 200;
const PICK_RADIUS = 14;

/** The three.js canvas of the 3D view (scene.ts), loaded only when the tab is opened. */
export default function GlyphViewer({ map, groups, frozen, labels, focus, onPick, ...look }: ViewerProps) {
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const tags = useRef<HTMLDivElement>(null);
  const scene = useRef<GlyphScene | null>(null);
  const [failed, setFailed] = useState(false);
  const lookRef = useRef(look);
  lookRef.current = look;
  const labelsRef = useRef(labels);
  labelsRef.current = labels;

  useEffect(() => {
    let made: GlyphScene;
    try {
      made = new GlyphScene(canvas.current!, map, groups, reducedMotion());
    } catch {
      setFailed(true);
      return;
    }
    scene.current = made;
    made.setLook(lookRef.current);
    const fit = () => made.resize(box.current!.clientWidth, box.current!.clientHeight);
    fit();
    const watch = new ResizeObserver(fit);
    watch.observe(box.current!);
    made.onDraw = () => placeTags(made);
    made.start();
    return () => {
      watch.disconnect();
      made.dispose();
      scene.current = null;
    };
    // A new map (another layer) is a new scene, laid out afresh; groups follow the map.
  }, [map]);

  useEffect(() => {
    scene.current?.setLook(look);
    // The look's parts, not the object made anew each render.
  }, [look.colours, look.same, look.showSame, look.showDifferent, look.highlight, look.explode, look.ink]);

  useEffect(() => {
    if (scene.current) scene.current.frozen = frozen;
  }, [frozen]);

  useEffect(() => {
    if (focus !== null) scene.current?.focus(focus);
  }, [focus]);

  /** The labels over the canvas: each point's id at its place on screen. */
  function placeTags(made: GlyphScene) {
    const layer = tags.current;
    if (!layer) return;
    const { highlight } = lookRef.current;
    const shown = !labelsRef.current ? [] : map.points.length <= LABEL_ALL ? map.points.map((_, i) => i) : [...(highlight ?? [])];
    const screen = made.onScreen(layer.clientWidth, layer.clientHeight);
    while (layer.children.length > shown.length) layer.lastChild!.remove();
    shown.forEach((i, k) => {
      const tag = (layer.children[k] as HTMLElement | undefined) ?? layer.appendChild(document.createElement('span'));
      tag.textContent = map.points[i]!.id;
      tag.className = (highlight && !highlight.has(i) ? styles.tagDim : styles.tag) ?? '';
      tag.style.display = screen[i * 3 + 2]! > 1 ? 'none' : '';
      tag.style.transform = `translate(${screen[i * 3]!}px, ${screen[i * 3 + 1]!}px) translate(-50%, -130%)`;
    });
  }

  /** A click (not a drag) picks the point under it, or clears the pick. */
  const down = useRef<{ x: number; y: number } | null>(null);
  function pointerUp(event: PointerEvent) {
    const start = down.current;
    const made = scene.current;
    if (!start || !made || Math.hypot(event.clientX - start.x, event.clientY - start.y) > 4) return;
    const rect = canvas.current!.getBoundingClientRect();
    const screen = made.onScreen(rect.width, rect.height);
    onPick(nearestOnScreen(screen, event.clientX - rect.left, event.clientY - rect.top, PICK_RADIUS));
  }

  if (failed) return <p className={styles.failed}>This browser cannot draw the 3D view: WebGL is off or not supported.</p>;
  return (
    <div ref={box} className={styles.canvasBox}>
      <canvas
        ref={canvas}
        className={styles.canvas}
        aria-label={`${map.points.length.toLocaleString('en-GB')} precedents in 3D`}
        onPointerDown={(e) => (down.current = { x: e.clientX, y: e.clientY })}
        onPointerUp={pointerUp}
      />
      <div ref={tags} className={styles.tags} aria-hidden="true" />
    </div>
  );
}
