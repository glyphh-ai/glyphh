import { render, screen } from "@testing-library/react";
import { Row } from "../Row/Row";
import { Stack } from "./Stack";

describe("Stack and Row", () => {
  it("lay children out on the spacing scale", () => {
    render(<Stack gap={6} align="center" className="extra"><span>a</span></Stack>);
    const stack = screen.getByText("a").parentElement as HTMLElement;
    expect(stack).toHaveClass("stack", "extra");
    expect(stack.style.getPropertyValue("--stack-gap")).toBe("var(--space-6)");
    expect(stack.style.getPropertyValue("--stack-align")).toBe("center");
  });

  it("Row spaces, aligns, justifies and wraps", () => {
    render(<Row gap={0} justify="between" wrap><span>b</span></Row>);
    const row = screen.getByText("b").parentElement as HTMLElement;
    expect(row).toHaveClass("row", "wrap");
    expect(row.style.getPropertyValue("--row-gap")).toBe("0");
    expect(row.style.getPropertyValue("--row-justify")).toBe("space-between");
  });

  it("use their defaults", () => {
    render(<><Stack><i>c</i></Stack><Row><i>d</i></Row></>);
    expect((screen.getByText("c").parentElement as HTMLElement).style.getPropertyValue("--stack-gap")).toBe("var(--space-4)");
    expect(screen.getByText("d").parentElement).not.toHaveClass("wrap");
  });
});
