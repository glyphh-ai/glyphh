import { render, screen } from "@testing-library/react";
import { EmptyState } from "../EmptyState/EmptyState";
import { Skeleton } from "../Skeleton/Skeleton";
import { Table } from "../Table/Table";
import { Card } from "./Card";

const rows = [{ id: "1", name: "Ada", credits: 12 }, { id: "2", name: "Bob", credits: 3 }];

describe("Card, Table, EmptyState and Skeleton", () => {
  it("a card is named by its title and holds its parts", () => {
    render(<Card title="Laptop" description="Fly, iad" leading={<i>cat</i>} actions={<button type="button">Open</button>}>body</Card>);
    expect(screen.getByRole("article", { name: "Laptop" })).toHaveTextContent("body");
    expect(screen.getByRole("heading", { level: 3, name: "Laptop" })).toBeInTheDocument();
    expect(screen.getByText("Fly, iad")).toBeInTheDocument();
  });

  it("a bare card has no header", () => {
    const { container } = render(<Card>just body</Card>);
    expect(container.querySelector("header")).toBeNull();
  });

  it("a card with only a title has no description or actions", () => {
    const { container } = render(<Card title="Only" />);
    expect(container.querySelector(".description")).toBeNull();
    expect(container.querySelector(".actions")).toBeNull();
  });

  it("a table has its caption, headers and rows", () => {
    render(<Table caption="Usage by member" rows={rows} rowKey={(r) => r.id} empty={<p>none</p>}
      columns={[{ key: "name", header: "Member", cell: (r) => r.name }, { key: "c", header: "Credits", cell: (r) => r.credits, align: "end" }]} />);
    expect(screen.getByRole("table", { name: "Usage by member" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Member", "Credits"]);
    expect(screen.getAllByRole("row")).toHaveLength(3);
  });

  it("an empty table shows its empty state instead", () => {
    render(<Table caption="Runs" rows={[]} rowKey={() => "x"} columns={[]}
      empty={<EmptyState title="No runs yet" description="Run a super power" art={<i>cat</i>} action={<button type="button">Run</button>} />} />);
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByRole("heading", { name: "No runs yet" })).toBeInTheDocument();
    expect(screen.getByText("Run a super power")).toBeInTheDocument();
  });

  it("an empty state without a description has none", () => {
    const { container } = render(<EmptyState title="Nothing" />);
    expect(container.querySelector("p")).toBeNull();
  });

  it("a skeleton says Loading once, as lines or as a box", () => {
    const { container } = render(<><Skeleton lines={2} /><Skeleton height={120} /><Skeleton /></>);
    expect(screen.getAllByRole("status", { name: "Loading" })).toHaveLength(3);
    expect(container.querySelectorAll(".line")).toHaveLength(5);
    expect((container.querySelector(".box") as HTMLElement).style.getPropertyValue("--skeleton-h")).toBe("120px");
  });
});
