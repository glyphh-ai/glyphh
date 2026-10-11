import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { z } from "zod";
import { Field } from "../Field/Field";
import { useForm } from "../hooks/useForm";
import { SubmitButton } from "../SubmitButton/SubmitButton";
import { TextInput } from "../TextInput/TextInput";
import { Form } from "./Form";

const schema = z.object({ name: z.string().min(1, "Give it a name"), email: z.email("Not an email") });

function Demo({ send }: { send: (v: z.output<typeof schema>) => Promise<void> }) {
  const form = useForm(schema, { name: "", email: "" }, send);
  return (
    <Form form={form} label="Invite">
      <Field field={form.field("name")} label="Name" hint="Their first name">{(f) => <TextInput {...f} />}</Field>
      <Field field={form.field("email")} label="Email">{(f) => <TextInput {...f} type="email" />}</Field>
      <SubmitButton>Invite</SubmitButton>
    </Form>
  );
}

describe("a form", () => {
  it("shows a field's error once it is left, not before", async () => {
    render(<Demo send={vi.fn()} />);
    const name = screen.getByLabelText("Name");
    expect(screen.getByText("Their first name")).toBeInTheDocument();
    await userEvent.click(name);
    expect(screen.queryByText("Give it a name")).toBeNull();
    await userEvent.tab();
    expect(screen.getByText("Give it a name")).toBeInTheDocument();
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name).toHaveAttribute("aria-describedby", expect.stringContaining("-error"));
  });

  it("submitting invalid shows every error and sends nothing", async () => {
    const send = vi.fn();
    render(<Demo send={send} />);
    await userEvent.click(screen.getByRole("button", { name: "Invite" }));
    expect(screen.getByText("Give it a name")).toBeInTheDocument();
    expect(screen.getByText("Not an email")).toBeInTheDocument();
    expect(send).not.toHaveBeenCalled();
  });

  it("sends the parsed values once, busy while it does", async () => {
    let finish = () => {};
    const send = vi.fn(() => new Promise<void>((resolve) => { finish = resolve; }));
    render(<Demo send={send} />);
    await userEvent.type(screen.getByLabelText("Name"), "Ada");
    await userEvent.type(screen.getByLabelText("Email"), "ada@acme.test");
    const button = screen.getByRole("button", { name: /Invite/ });
    await userEvent.click(button);
    expect(button).toBeDisabled();
    await act(async () => { screen.getByRole("form", { name: "Invite" }).dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
    expect(send).toHaveBeenCalledOnce();
    expect(send).toHaveBeenCalledWith({ name: "Ada", email: "ada@acme.test" });
    await act(async () => finish());
    expect(button).toBeEnabled();
  });

  it("puts the server's field error on its field until that field changes", async () => {
    const send = vi.fn().mockRejectedValue({ status: 422, body: { error: { problems: [{ loc: ["body", "email"], msg: "Already invited" }] } } });
    render(<Demo send={send} />);
    await userEvent.type(screen.getByLabelText("Name"), "Ada");
    await userEvent.type(screen.getByLabelText("Email"), "ada@acme.test");
    await userEvent.click(screen.getByRole("button", { name: "Invite" }));
    expect(await screen.findByText("Already invited")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    await userEvent.type(screen.getByLabelText("Email"), "x");
    expect(screen.queryByText("Already invited")).toBeNull();
  });

  it("shows any other refusal once at the top, with its code and trace id", async () => {
    const send = vi.fn().mockRejectedValue({ status: 403, code: "E_FORBIDDEN", traceId: "t-9", message: "Only an org admin can invite." });
    render(<Demo send={send} />);
    await userEvent.type(screen.getByLabelText("Name"), "Ada");
    await userEvent.type(screen.getByLabelText("Email"), "ada@acme.test");
    await userEvent.click(screen.getByRole("button", { name: "Invite" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Only an org admin can invite.");
    expect(alert).toHaveTextContent("E_FORBIDDEN · trace t-9");
  });
});
