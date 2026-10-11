import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Tabs } from "./Tabs";

const tabs = [{ key: "a", label: "Identity", content: <p>identity</p> }, { key: "b", label: "Powers", content: <p>powers</p> },
  { key: "c", label: "Runs", content: <p>runs</p> }];

function Demo({ start = "a" }: { start?: string }) {
  const [value, setValue] = useState(start);
  return <Tabs label="Super power" tabs={tabs} value={value} onChange={setValue} />;
}

describe("Tabs", () => {
  it("shows only the chosen tab's content", async () => {
    render(<Demo />);
    expect(screen.getByRole("tablist", { name: "Super power" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Identity" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("identity");
    await userEvent.click(screen.getByRole("tab", { name: "Runs" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("runs");
  });

  it("moves with the arrow keys, Home and End, wrapping round", async () => {
    render(<Demo />);
    screen.getByRole("tab", { name: "Identity" }).focus();
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Runs" })).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Identity" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("runs");
    await userEvent.keyboard("{Home}");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("identity");
    await userEvent.keyboard("x");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("identity");
  });

  it("an unknown value falls back to the first tab", () => {
    render(<Demo start="zzz" />);
    expect(screen.getByRole("tabpanel")).toHaveTextContent("identity");
  });

  it("no tabs shows an empty panel", () => {
    render(<Tabs label="None" tabs={[]} value="" onChange={() => {}} />);
    expect(screen.getByRole("tabpanel")).toBeEmptyDOMElement();
  });
});
