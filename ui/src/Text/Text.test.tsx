import { render, screen } from "@testing-library/react";
import { Code } from "../Code/Code";
import { Heading } from "../Heading/Heading";
import { Text } from "./Text";

describe("Heading, Text and Code", () => {
  it.each([1, 2, 3, 4] as const)("Heading %i is that level", (level) => {
    render(<Heading level={level} className="x">Title {level}</Heading>);
    const heading = screen.getByRole("heading", { level });
    expect(heading).toHaveClass("heading", `h${level}`, "x");
  });

  it("Text takes its element, size, tone and weight", () => {
    render(<Text as="span" size="sm" tone="muted" weight="bold" className="y">hello</Text>);
    const text = screen.getByText("hello");
    expect(text.tagName).toBe("SPAN");
    expect(text).toHaveAttribute("data-size", "sm");
    expect(text).toHaveAttribute("data-tone", "muted");
    expect(text).toHaveAttribute("data-weight", "bold");
  });

  it("Text defaults to a paragraph", () => {
    render(<Text>plain</Text>);
    expect(screen.getByText("plain").tagName).toBe("P");
  });

  it("Code is inline code", () => {
    render(<Code>E_INVALID</Code>);
    expect(screen.getByText("E_INVALID").tagName).toBe("CODE");
  });
});
