import { render, screen } from "@testing-library/react";
import { ProgressSteps } from "./ProgressSteps";

const steps = [{ key: "waiting", label: "Waiting" }, { key: "registered", label: "Registered" },
  { key: "starting", label: "Starting" }, { key: "ready", label: "Ready" }];

describe("ProgressSteps", () => {
  it("marks the steps before as done, the current one, and those after as pending", () => {
    render(<ProgressSteps label="Deploying" steps={steps} current="starting" />);
    const items = screen.getAllByRole("listitem");
    expect(items.map((i) => i.getAttribute("data-state"))).toEqual(["done", "done", "current", "pending"]);
    expect(items[2]).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("list", { name: "Deploying" })).toBeInTheDocument();
  });

  it("marks a failed step as failed", () => {
    render(<ProgressSteps label="Deploying" steps={steps} current="registered" failed />);
    expect(screen.getByText("Registered").parentElement).toHaveAttribute("data-state", "failed");
  });
});
