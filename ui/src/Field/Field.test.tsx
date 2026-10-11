import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Checkbox } from "../Checkbox/Checkbox";
import { FormError } from "../FormError/FormError";
import type { FieldBinding } from "../hooks/useForm";
import { RadioGroup } from "../RadioGroup/RadioGroup";
import { Select } from "../Select/Select";
import { Slider } from "../Slider/Slider";
import { Switch } from "../Switch/Switch";
import { TextArea } from "../TextArea/TextArea";
import { Field } from "./Field";

function useBinding<T>(name: string, initial: T, error?: string): FieldBinding<T> {
  const [value, setValue] = useState(initial);
  const id = `f-${name}`;
  return { id, name, value, error, invalid: Boolean(error), onChange: setValue, onBlur: () => {}, hintId: `${id}-hint`,
    errorId: `${id}-error`, labelId: `${id}-label`, describedBy: `${id}-hint` };
}

function Controls() {
  const notify = useBinding("notify", false);
  const agree = useBinding("agree", false);
  const plan = useBinding("plan", "");
  const role = useBinding("role", "user");
  const mood = useBinding("mood", 3);
  const bio = useBinding("bio", "", "Too short");
  return (
    <>
      <Field field={notify} label="Notify me" layout="inline">{(f) => <Switch {...f} labelledBy={f.labelId} />}</Field>
      <Field field={agree} label="I agree" layout="inline">{(f) => <Checkbox {...f} />}</Field>
      <Field field={plan} label="Plan">{(f) => <Select {...f} placeholder="Choose a plan" options={[{ value: "free", label: "Free" }, { value: "pro", label: "Pro" }]} />}</Field>
      <Field field={role} label="Role">{(f) => <RadioGroup {...f} labelledBy={f.labelId} options={[{ value: "user", label: "User" }, { value: "org_admin", label: "Org admin" }]} />}</Field>
      <Field field={mood} label="Personality">{(f) => <Slider {...f} min={1} max={5} marks={["Serious", "Calm", "Balanced", "Warm", "Playful"]} />}</Field>
      <Field field={bio} label="Bio">{(f) => <TextArea {...f} rows={2} />}</Field>
    </>
  );
}

describe("the controls", () => {
  it("a switch flips and says so", async () => {
    render(<Controls />);
    const toggle = screen.getByRole("switch", { name: "Notify me" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("a checkbox ticks, a select chooses, a radio group picks", async () => {
    render(<Controls />);
    await userEvent.click(screen.getByLabelText("I agree"));
    expect(screen.getByLabelText("I agree")).toBeChecked();
    expect(screen.getByRole("option", { name: "Choose a plan" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Plan"), "pro");
    expect(screen.getByLabelText("Plan")).toHaveValue("pro");
    expect(screen.getByRole("radiogroup", { name: "Role" })).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Org admin"));
    expect(screen.getByLabelText("Org admin")).toBeChecked();
  });

  it("a slider reads out its word, not its number", () => {
    render(<Controls />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuetext", "Balanced");
    expect(screen.getByText("Balanced")).toBeInTheDocument();
    fireEvent.change(slider, { target: { value: "4" } });
    expect(screen.getByText("Warm")).toBeInTheDocument();
    expect(slider).toHaveAttribute("aria-valuetext", "Warm");
  });

  it("a field shows its error in place of its hint", async () => {
    render(<Controls />);
    expect(screen.getByText("Too short")).toHaveAttribute("id", "f-bio-error");
    await userEvent.type(screen.getByLabelText("Bio"), "hi");
    expect(screen.getByLabelText("Bio")).toHaveValue("hi");
  });

  it("a slider without words shows its number, and no problem shows nothing", () => {
    function Bare() {
      const n = useBinding("n", 7);
      const note = useBinding("note", "");
      return (
        <>
          <Field field={n} label="Count">{(f) => <Slider {...f} min={0} max={10} />}</Field>
          <Field field={note} label="Note">{(f) => <TextArea {...f} />}</Field>
        </>
      );
    }
    render(<><Bare /><FormError problem={null} /><FormError problem={{ message: "Plain" }} /></>);
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByLabelText("Note")).not.toHaveAttribute("aria-invalid");
    expect(screen.getByRole("alert")).toHaveTextContent("Plain");
    expect(screen.getByRole("alert").querySelector("p:nth-child(2)")).toBeNull();
  });
});
