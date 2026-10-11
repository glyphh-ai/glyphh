import { render, screen } from "@testing-library/react";
import { Alert } from "../Alert/Alert";
import { StatusDot } from "../StatusDot/StatusDot";
import { Badge } from "./Badge";

describe("Badge, StatusDot and Alert", () => {
  it("a badge carries its tone", () => {
    render(<><Badge tone="ok">Pro</Badge><Badge>Free</Badge></>);
    expect(screen.getByText("Pro")).toHaveAttribute("data-tone", "ok");
    expect(screen.getByText("Free")).toHaveAttribute("data-tone", "neutral");
  });

  it.each([["online", "Online"], ["offline", "Offline"], ["working", "Working"], ["waiting", "Waiting for you"], ["failed", "Failed"]] as const)(
    "a %s dot says so to screen readers", (status, word) => {
      render(<StatusDot status={status} />);
      expect(screen.getByText(word)).toHaveClass("hidden");
    });

  it("a dot can show its word", () => {
    render(<StatusDot status="online" showLabel />);
    expect(screen.getByText("Online")).toHaveClass("label");
  });

  it("a danger alert interrupts and shows its code and trace id", () => {
    render(<Alert tone="danger" title="Couldn't save" code="E_INTERNAL" traceId="t-1">Try again.</Alert>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Couldn't save");
    expect(alert).toHaveTextContent("Try again.");
    expect(alert).toHaveTextContent("E_INTERNAL · trace t-1");
  });

  it("an info alert waits its turn, and shows only what it has", () => {
    render(<Alert>Heads up</Alert>);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("data-tone", "info");
    expect(status.querySelectorAll("p")).toHaveLength(0);
    render(<Alert tone="warn" title="Only a title" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Only a title");
  });
});
