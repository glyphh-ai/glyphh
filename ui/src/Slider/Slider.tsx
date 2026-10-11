import type { ControlProps } from "../hooks/useForm";
import styles from "./Slider.module.css";

export interface SliderProps extends ControlProps<number> {
  min: number;
  max: number;
  step?: number;
  /** A word for each step, from min: "Serious" … "Playful". Shown and read out instead of the number. */
  marks?: string[];
  disabled?: boolean;
}

/** A value on a scale: the personality sliders, effort. */
export function Slider({ id, name, value, describedBy, onChange, onBlur, min, max, step = 1, marks, disabled }: SliderProps) {
  const word = marks?.[Math.round((value - min) / step)];
  return (
    <div className={styles.slider}>
      <input type="range" id={id} name={name} min={min} max={max} step={step} value={value} disabled={disabled}
        aria-describedby={describedBy} aria-valuetext={word} onChange={(e) => onChange(Number(e.target.value))}
        onBlur={onBlur} />
      <output className={styles.value} htmlFor={id}>{word ?? value}</output>
    </div>
  );
}
