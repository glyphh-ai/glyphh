import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Menu } from "./Menu";

function demo() {
  const rename = vi.fn();
  const remove = vi.fn();
  render(<><Menu label="Machine actions" trigger="⋯" items={[{ key: "r", label: "Rename", onSelect: rename },
    { key: "d", label: "Remove", onSelect: remove, danger: true }]} /><p>outside</p></>);
  return { rename, remove, button: screen.getByRole("button", { name: "Machine actions" }) };
}

describe("Menu", () => {
  it("opens, focuses the first item, and runs the chosen one", async () => {
    const { rename, button } = demo();
    expect(button).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menuitem", { name: "Rename" })).toHaveFocus();
    expect(screen.getByRole("menuitem", { name: "Remove" })).toHaveAttribute("data-danger");
    await userEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    expect(rename).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("arrows move round the items; Escape closes and returns focus", async () => {
    const { button } = demo();
    await userEvent.click(button);
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Remove" })).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Rename" })).toHaveFocus();
    await userEvent.keyboard("{ArrowUp}");
    expect(screen.getByRole("menuitem", { name: "Remove" })).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(button).toHaveFocus();
  });

  it("a click outside closes it; a click on its own button toggles", async () => {
    const { button } = demo();
    await userEvent.click(button);
    await userEvent.click(screen.getByRole("menu"));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await userEvent.click(screen.getByText("outside"));
    expect(screen.queryByRole("menu")).toBeNull();
    await userEvent.click(button);
    await userEvent.click(button);
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
