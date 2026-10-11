import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "../Button/Button";
import { useDisclosure } from "../hooks/useDisclosure";
import { Dialog } from "./Dialog";

function Demo() {
  const d = useDisclosure();
  return (
    <>
      <Button onClick={d.show}>Disconnect</Button>
      <Dialog open={d.open} onClose={d.hide} title="Disconnect Codex?" description="Its tokens stop working at once."
        actions={<><Button onClick={d.hide}>Cancel</Button><Button variant="danger" onClick={d.hide}>Disconnect it</Button></>}>
        <p>body</p>
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("opens as a modal named by its title, and closes", async () => {
    render(<Demo />);
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog).not.toHaveAttribute("open");
    await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(dialog).toHaveAttribute("open");
    expect(dialog).toHaveAccessibleName("Disconnect Codex?");
    expect(screen.getByText("Its tokens stop working at once.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(dialog).not.toHaveAttribute("open");
  });

  it("closing from the browser (Escape) tells its owner", () => {
    const onClose = vi.fn();
    render(<Dialog open onClose={onClose} title="Bare" />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.querySelector("p")).toBeNull();
    (dialog as HTMLDialogElement).close();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("useDisclosure toggles", async () => {
    function T() { const d = useDisclosure(true); return <Button onClick={d.toggle}>{d.open ? "open" : "shut"}</Button>; }
    render(<T />);
    await userEvent.click(screen.getByRole("button", { name: "open" }));
    expect(screen.getByRole("button", { name: "shut" })).toBeInTheDocument();
  });
});
