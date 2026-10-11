import { type FormEvent, useCallback, useId, useState } from "react";
import type { z } from "zod";
import type { FormProblem } from "./formProblems";
import { useSubmit } from "./useSubmit";

/** What every input takes: the same shape for text, choices, switches and sliders. */
export interface ControlProps<T> {
  id: string;
  name: string;
  value: T;
  invalid: boolean;
  describedBy: string | undefined;
  onChange: (value: T) => void;
  onBlur: () => void;
}

/** A field's control props, plus what its Field shows around it. */
export interface FieldBinding<T> extends ControlProps<T> {
  error: string | undefined;
  hintId: string;
  errorId: string;
  labelId: string;
}

type Values = Record<string, unknown>;
type Errors = Record<string, string>;

export interface FormApi<V extends Values> {
  values: V;
  errors: Errors;
  problem: FormProblem | null;
  submitting: boolean;
  field<K extends keyof V & string>(name: K): FieldBinding<V[K]>;
  setValue<K extends keyof V & string>(name: K, value: V[K]): void;
  handleSubmit: (event?: FormEvent) => Promise<void>;
}

export function errorsOf(schema: z.ZodType, values: Values): Errors {
  const result = schema.safeParse(values);
  const errors: Errors = {};
  for (const issue of result.success ? [] : result.error.issues) {
    const name = String(issue.path[0] ?? "");
    if (name && !(name in errors)) errors[name] = issue.message;
  }
  return errors;
}

function binding<T>(id: string, name: string, value: T, error: string | undefined,
  onChange: (value: T) => void, onBlur: () => void): FieldBinding<T> {
  return { id, name, value, error, invalid: Boolean(error), onChange, onBlur, hintId: `${id}-hint`,
    errorId: `${id}-error`, labelId: `${id}-label`, describedBy: error ? `${id}-error` : `${id}-hint` };
}

/** One form: values, validation by its zod schema, and a submit that cannot run twice at once.
 *  A field's error shows once it has been left or the form submitted; the server's own field
 *  errors show until that field changes. */
export function useForm<S extends z.ZodType<Values>, V extends Values = z.input<S> & Values>(
  schema: S, initial: V, onSubmit: (values: z.output<S>) => Promise<void>,
): FormApi<V> {
  const prefix = useId();
  const [values, setValues] = useState<V>(initial);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitted, setSubmitted] = useState(false);
  const [server, setServer] = useState<Errors>({});
  const submit = useSubmit(onSubmit);
  const errors: Errors = { ...server };
  for (const [name, message] of Object.entries(errorsOf(schema, values))) {
    if (submitted || touched[name]) errors[name] = message;
  }
  const setValue = useCallback(<K extends keyof V & string>(name: K, value: V[K]) => {
    setValues((v) => ({ ...v, [name]: value }));
    setServer(({ [name]: _cleared, ...rest }) => rest);
  }, []);
  const field = <K extends keyof V & string>(name: K) => binding(`${prefix}-${name}`, name, values[name],
    errors[name], (value: V[K]) => setValue(name, value), () => setTouched((t) => ({ ...t, [name]: true })));
  const handleSubmit = async (event?: FormEvent) => {
    event?.preventDefault();
    setSubmitted(true);
    const parsed = schema.safeParse(values);
    if (!parsed.success) return;
    const failed = await submit.run(parsed.data as z.output<S>);
    if (failed) setServer(failed.fields);
  };
  return { values, errors, problem: submit.problem, submitting: submit.submitting, field, setValue, handleSubmit };
}
