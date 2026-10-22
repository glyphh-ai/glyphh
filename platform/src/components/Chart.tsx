import { useEffect, useRef } from 'react';
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJs,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
  type ChartConfiguration,
} from 'chart.js';
import { reducedMotion, useInk } from '@/lib/tokens';
import styles from './Chart.module.css';

ChartJs.register(BarController, BarElement, CategoryScale, Filler, Legend, LinearScale, LineController, LineElement, PointElement, Tooltip);

export type Series = { label: string; data: Array<number | null>; color?: string };

type ChartProps = {
  kind: 'bar' | 'line';
  /** What the chart shows, for a screen reader; the table under it carries the numbers. */
  label: string;
  labels: string[];
  series: Series[];
  stacked?: boolean;
  /** Bars across, for categories with long names. */
  across?: boolean;
  /** Values are shares (0 to 1), shown as percentages. */
  percent?: boolean;
  height?: number;
};

const show = (value: number | null, percent: boolean) =>
  value === null ? '–' : percent ? `${Math.round(value * 100)}%` : value.toLocaleString('en-GB');

/**
 * A chart.js chart in the theme's ink (lib/tokens.ts), drawn again when the theme or the data change; with a table of
 * the same numbers for screen readers. No animation when the person asked for less motion.
 */
export function Chart({ kind, label, labels, series, stacked = false, across = false, percent = false, height = 220 }: ChartProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const ink = useInk();

  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    const scale = (axis: 'x' | 'y') => {
      const values = (axis === 'x') === across;
      return {
        stacked,
        beginAtZero: true,
        grid: { color: ink.line, display: values, drawTicks: false },
        border: { display: false },
        ticks: {
          color: ink.muted,
          font: { family: ink.mono, size: 11 },
          padding: 6,
          maxTicksLimit: values ? 5 : 8,
          maxRotation: 0,
          autoSkip: true,
          precision: percent ? undefined : 0,
          ...(values && percent ? { callback: (v: number | string) => `${Math.round(Number(v) * 100)}%` } : {}),
        },
        ...(values && percent ? { max: 1 } : {}),
      };
    };
    const config: ChartConfiguration<'bar' | 'line'> = {
      type: kind,
      data: {
        labels,
        datasets: series.map((s, i) => {
          const color = s.color ?? ink.series[i % ink.series.length]!;
          return kind === 'bar'
            ? { label: s.label, data: s.data, backgroundColor: color, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 28, borderColor: ink.bg, borderWidth: series.length > 1 ? 1 : 0 }
            : { label: s.label, data: s.data, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 0, pointHitRadius: 8, cubicInterpolationMode: 'monotone' as const, spanGaps: true };
        }),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: reducedMotion() ? false : { duration: 300 },
        indexAxis: across ? 'y' : 'x',
        interaction: { mode: 'index', intersect: false },
        scales: { x: scale('x'), y: scale('y') },
        plugins: {
          legend: { display: series.length > 1, align: 'start', labels: { color: ink.secondary, boxWidth: 10, boxHeight: 10, font: { family: ink.font, size: 12 } } },
          tooltip: {
            backgroundColor: ink.surface,
            borderColor: ink.lineStrong,
            borderWidth: 1,
            titleColor: ink.text,
            bodyColor: ink.secondary,
            titleFont: { family: ink.mono, size: 12 },
            bodyFont: { family: ink.font, size: 12 },
            callbacks: { label: (item) => `${item.dataset.label}: ${show(item.parsed[across ? 'x' : 'y'] as number, percent)}` },
          },
        },
      },
    };
    const chart = new ChartJs(context, config);
    return () => chart.destroy();
  }, [kind, labels, series, stacked, across, percent, ink]);

  return (
    <figure className={styles.figure}>
      <div className={styles.canvas} style={{ height }}>
        <canvas ref={canvas} role="img" aria-label={label} />
      </div>
      <table className={styles.hidden}>
        <caption>{label}</caption>
        <thead>
          <tr>
            <th scope="col" />
            {series.map((s) => (
              <th key={s.label} scope="col">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((name, i) => (
            <tr key={name}>
              <th scope="row">{name}</th>
              {series.map((s) => (
                <td key={s.label}>{show(s.data[i] ?? null, percent)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
