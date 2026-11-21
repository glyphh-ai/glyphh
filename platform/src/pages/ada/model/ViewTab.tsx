import { lazy, Suspense, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useAdaMap, useAdaPrecedent, type AdaModel, type ModelMap } from '@/api/ada';
import { date, plural } from '@/lib/format';
import { useInk, type Ink } from '@/lib/tokens';
import { Card, Chip, EmptyState, LoadingCard, TextField } from '@/ui';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { colourOutput, findPoint, legendOf, neighbourhood, outcomeOf, rolesOfCase } from './view/glyphs';
import styles from './view/view.module.css';
import adaStyles from '../ada.module.css';

const GlyphViewer = lazy(() => import('./view/GlyphViewer'));

/** One precedent, picked in the view: its outcome, its case and who recorded it when. */
function CasePanel({ model, id, output }: { model: string; id: string; output: string | null }) {
  const found = useAdaPrecedent(model, id);
  if (found.isPending) return <LoadingCard lines={3} />;
  if (!found.data) return <AdaErrorNotice error={found.error} />;
  const p = found.data;
  const outcomes = Object.entries(p.outcomes);
  return (
    <Card>
      <div className={adaStyles.stack}>
        <div className={adaStyles.chips}>
          <span className={adaStyles.mono}>{p.id}</span>
          {output === null && <Chip tone={p.outcome ? 'violet' : 'neutral'}>{p.outcome ?? 'Ungraded'}</Chip>}
          {outcomes.map(([name, value]) => (
            <Chip key={name} tone="violet">
              {name}: {value}
            </Chip>
          ))}
        </div>
        <dl className={styles.case}>
          {rolesOfCase(p.situation).map((r) => (
            <div key={r.path}>
              <dt className={adaStyles.mono}>{r.path}</dt>
              <dd>{r.value}</dd>
            </div>
          ))}
        </dl>
        <p className={adaStyles.meta}>
          Recorded {date(new Date(p.ts * 1000).toISOString())} by <span className={adaStyles.mono}>{p.author}</span>
        </p>
      </div>
    </Card>
  );
}

type Show = { same: boolean; different: boolean; labels: boolean; explode: boolean; frozen: boolean };

function Overlays({ map, layer, show, set, onSearch, legend, ink }: { map: ModelMap; layer: string | null; show: Show; set: (s: Partial<Show>) => void; onSearch: (text: string) => void; legend: ReturnType<typeof legendOf>['legend']; ink: Ink }) {
  const [text, setText] = useState('');
  const search = (event: FormEvent) => {
    event.preventDefault();
    onSearch(text);
  };
  const toggle = (key: keyof Show, label: string, swatch?: string) => (
    <label className={styles.toggle}>
      <input type="checkbox" checked={show[key]} onChange={(e) => set({ [key]: e.target.checked })} />
      {swatch && <span className={styles.swatch} style={{ background: swatch }} aria-hidden="true" />}
      {label}
    </label>
  );
  return (
    <>
      <div className={`${styles.panel} ${styles.topLeft}`}>
        <span className={styles.panelTitle}>Layer</span>
        {[null, ...map.layers].slice(0, 10).map((name, i) => (
          <span key={name ?? ''} className={name === layer ? styles.on : undefined}>
            {i} · {name ?? 'Whole case'}
          </span>
        ))}
        <span className={styles.keys}>
          E explode {show.explode ? 'on' : 'off'} · F freeze {show.frozen ? 'on' : 'off'} · L labels · Esc clear
        </span>
        <span className={styles.keys}>Drag to turn, scroll to zoom, click a point to see its case</span>
      </div>
      <div className={`${styles.panel} ${styles.topRight}`}>
        <span className={styles.panelTitle}>Lines to the nearest</span>
        {toggle('same', 'Same outcome', ink.lineStrong)}
        {toggle('different', 'Different outcome', ink.series[3])}
        {toggle('labels', 'Labels')}
      </div>
      <div className={`${styles.panel} ${styles.bottomLeft}`}>
        {legend.map((entry) => (
          <span key={entry.name} className={styles.legendRow}>
            <span className={styles.swatch} style={{ background: entry.colour }} aria-hidden="true" />
            {entry.name} <span className={styles.count}>{entry.count.toLocaleString('en-GB')}</span>
          </span>
        ))}
      </div>
      <form className={`${styles.panel} ${styles.bottomRight}`} onSubmit={search} onKeyDown={(e) => e.stopPropagation()}>
        <TextField label="Find a precedent" placeholder="Its id, or the start of it" mono value={text} onChange={(e) => setText(e.target.value)} />
      </form>
    </>
  );
}

/**
 * The 3D view: a sample of the model's precedents (the server's map: up to 2,000), each a cloud of its glyph's
 * bits, laid out by their nearest and coloured by outcome, after the old GlyphViewer: layers on 0–9, explode, freeze,
 * labels, lines by kind, a highlighted neighbourhood, search by id; a picked point's case beside it.
 */
export function ViewTab({ model }: { model: AdaModel }) {
  const [layer, setLayer] = useState<string | null>(null);
  const map = useAdaMap(model.name, layer);
  const ink = useInk();
  const [show, setShow] = useState<Show>(() => ({ same: true, different: true, labels: true, explode: false, frozen: false }));
  const [picked, setPicked] = useState<number | null>(null);
  const [focus, setFocus] = useState<number | null>(null);
  const output = colourOutput(model.spec);
  const set = (s: Partial<Show>) => setShow((now) => ({ ...now, ...s }));
  const data = map.data;

  const drawn = useMemo(() => {
    if (!data) return null;
    const { legend, colourOf, group } = legendOf(data, output, ink.series, ink.secondary, ink.lineStrong);
    const outcomes = data.points.map((p) => outcomeOf(p, output));
    return {
      legend,
      colours: outcomes.map(colourOf),
      groups: outcomes.map(group),
      same: data.edges.map(([a, b]) => outcomes[a] === outcomes[b]),
    };
  }, [data, output, ink]);

  const highlight = useMemo(
    () => (data && drawn && picked !== null ? neighbourhood(data.edges, (e) => (drawn.same[e] ? show.same : show.different), picked) : null),
    [data, drawn, picked, show.same, show.different],
  );

  const pick = (index: number | null) => {
    setPicked(index);
    if (index !== null) setFocus(index);
  };

  const keys = (event: KeyboardEvent) => {
    if (!data) return;
    const key = event.key.toLowerCase();
    const n = Number(event.key);
    if (/^[0-9]$/.test(event.key) && n <= data.layers.length) {
      setPicked(null);
      setLayer(n === 0 ? null : data.layers[n - 1]!);
    } else if (key === 'e') set({ explode: !show.explode });
    else if (key === 'f') set({ frozen: !show.frozen });
    else if (key === 'l') set({ labels: !show.labels });
    else if (key === 'escape') setPicked(null);
    else return;
    event.preventDefault();
  };

  if (map.isPending) return <LoadingCard lines={4} />;
  if (!data || !drawn) return <AdaErrorNotice error={map.error} />;
  if (!data.points.length) {
    return (
      <Card>
        <EmptyState icon="model" title="Nothing to show yet">
          The 3D view shows this model’s precedents once it holds some. Import or record cases first.
        </EmptyState>
      </Card>
    );
  }
  const sample = data.points.length < data.total ? `A sample of ${data.points.length.toLocaleString('en-GB')} of ${plural(data.total, 'precedent')}` : plural(data.total, 'precedent');
  return (
    <div className={adaStyles.stack}>
      <p className={adaStyles.meta}>
        {sample}, each a cloud of its glyph’s bits, near the ones most like it. Coloured by {output ?? 'outcome'}.
      </p>
      <div className={styles.viewer} tabIndex={0} onKeyDown={keys} aria-label="3D view: 0 to 9 change the layer, E explodes, F freezes, L shows labels, Esc clears the highlight">
        <Suspense fallback={<LoadingCard lines={2} />}>
          <GlyphViewer
            map={data}
            groups={drawn.groups}
            colours={drawn.colours}
            same={drawn.same}
            showSame={show.same}
            showDifferent={show.different}
            highlight={highlight}
            explode={show.explode}
            ink={ink}
            frozen={show.frozen}
            labels={show.labels}
            focus={focus}
            onPick={pick}
          />
        </Suspense>
        <Overlays
          map={data}
          layer={layer}
          show={show}
          set={set}
          legend={drawn.legend}
          ink={ink}
          onSearch={(text) => {
            const found = findPoint(data.points, text);
            pick(found);
          }}
        />
      </div>
      {picked !== null && data.points[picked] && <CasePanel model={model.name} id={data.points[picked].id} output={output} />}
    </div>
  );
}
