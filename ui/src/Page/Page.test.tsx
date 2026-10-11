import { render, screen } from "@testing-library/react";
import { Section } from "../Section/Section";
import { Page } from "./Page";

describe("Page and Section", () => {
  it("a page has its title, description, actions and content", () => {
    render(<Page title="My machines" description="Where your super powers run" actions={<button type="button">Deploy</button>} width="wide">
      <p>body</p></Page>);
    expect(screen.getByRole("main")).toHaveAttribute("data-width", "wide");
    expect(screen.getByRole("heading", { level: 1, name: "My machines" })).toBeInTheDocument();
    expect(screen.getByText("Where your super powers run")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deploy" })).toBeInTheDocument();
  });

  it("a page without description or actions shows neither", () => {
    const { container } = render(<Page title="Account"><p>x</p></Page>);
    expect(container.querySelector("p.description")).toBeNull();
    expect(container.querySelector(".actions")).toBeNull();
  });

  it("a section is a named region with a level-2 heading", () => {
    render(<Section title="Plan" description="Your plan and seats" actions={<span>act</span>}><p>y</p></Section>);
    expect(screen.getByRole("region", { name: "Plan" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Plan" })).toBeInTheDocument();
    expect(screen.getByText("Your plan and seats")).toBeInTheDocument();
  });

  it("a section without a description has none", () => {
    const { container } = render(<Section title="Bare"><p>z</p></Section>);
    expect(container.querySelector(".description")).toBeNull();
  });
});
