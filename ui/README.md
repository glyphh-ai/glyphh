# @glyphh-ai/ui

Glyphh's component library: one set of components for **app.glyphh.ai**, **rrotor's UI** and the **cards in Claude and ChatGPT**, so no page reinvents a button, a form or an error.

How it looks belongs to the design agent; how it works belongs here (`../design/collaboration.md`).

## Using it

Import each component by its own path; there is no index file:

```tsx
import "@glyphh-ai/ui/tokens.css";
import "@glyphh-ai/ui/base.css";
import { Button } from "@glyphh-ai/ui/Button";
import { useForm } from "@glyphh-ai/ui/hooks/useForm";
```

## Forms: always the same way

```tsx
const schema = z.object({ email: z.email("Not an email") });

function Invite() {
  const form = useForm(schema, { email: "" }, (values) => glyphh.invite(values));
  return (
    <Form form={form} label="Invite">
      <Field field={form.field("email")} label="Email" hint="They'll get a link">
        {(f) => <TextInput {...f} type="email" />}
      </Field>
      <SubmitButton>Invite</SubmitButton>
    </Form>
  );
}
```

- The schema (zod) is the only validation; the browser's own is off.
- A field's error shows once the person leaves it, or on submit.
- The submit runs once at a time; the button is busy meanwhile.
- The server's `E_INVALID` problems land on their fields; any other refusal shows once at the top with its code and trace id; anything unrecognised fails closed ("Something went wrong. Try again.").

Loading a page's data is `useLoad(() => glyphh.listMachines())`: loading, ready, or failed with the same problem shape.

## The components

| Group | Components |
|---|---|
| Layout | Stack, Row, Page, Section |
| Text | Heading, Text, Code |
| Actions | Button, IconButton, Link, CopyButton |
| Forms | Form, Field, TextInput, TextArea, Select, Checkbox, Switch, RadioGroup, Slider, SubmitButton, FormError |
| Content | Card, Table, Badge, StatusDot, Avatar (the cats), CodeBlock |
| Feedback | Alert, Toast (`useToast`), Spinner, Skeleton, EmptyState, ProgressSteps |
| Overlays and navigation | Dialog (`useDisclosure`), Tabs, Menu |

Hooks: `useForm`, `useSubmit`, `useLoad`, `useToast`, `useDisclosure`, `useCopy`.

## Rules

- One folder per component: `Name.tsx`, `Name.module.css`, its test. Components use tokens only, never a raw colour or size.
- No file over 200 lines, no function over 40, no index files (`test/code-shape.test.ts` fails CI otherwise).
- 100% test coverage; any React warning fails its test.

## Test

    docker compose run --rm test-ui
