import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IconButton } from "../IconButton/IconButton";
import { Link } from "../Link/Link";
import { Spinner } from "../Spinner/Spinner";
import { Button } from "./Button";

describe("Button", () => {
  it("is a plain button by default and calls back on click", async () => {
    const clicked = vi.fn();
    render(<Button onClick={clicked}>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("data-variant", "secondary");
    await userEvent.click(button);
    expect(clicked).toHaveBeenCalledOnce();
  });

  it("while busy shows a spinner and takes no clicks", async () => {
    const clicked = vi.fn();
    render(<Button busy variant="primary" size="lg" onClick={clicked} icon={<i>ic</i>}>Deploy</Button>);
    const button = screen.getByRole("button", { name: /Deploy/ });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status", { name: "Working" })).toBeInTheDocument();
    expect(screen.queryByText("ic")).toBeNull();
    await userEvent.click(button);
    expect(clicked).not.toHaveBeenCalled();
  });

  it("shows its icon, stretches when block, and can submit", () => {
    render(<Button icon={<i>ic</i>} block type="submit" disabled>Go</Button>);
    const button = screen.getByRole("button", { name: /Go/ });
    expect(screen.getByText("ic")).toBeInTheDocument();
    expect(button).toHaveClass("block");
    expect(button).toHaveAttribute("type", "submit");
    expect(button).toBeDisabled();
    expect(button).not.toHaveAttribute("aria-busy");
  });
});

describe("IconButton, Link and Spinner", () => {
  it("an icon button is named by its label", async () => {
    const clicked = vi.fn();
    render(<IconButton label="Close" icon={<i>x</i>} variant="secondary" onClick={clicked} />);
    const button = screen.getByRole("button", { name: "Close" });
    expect(button).toHaveAttribute("title", "Close");
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    expect(clicked).toHaveBeenCalledOnce();
  });

  it("an external link opens safely in a new tab and says so", () => {
    render(<Link href="https://glyphh.ai" external>Glyphh</Link>);
    const link = screen.getByRole("link", { name: /Glyphh/ });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveTextContent("opens in a new tab");
  });

  it("an internal link stays in the tab", () => {
    render(<Link href="/machines">Machines</Link>);
    expect(screen.getByRole("link", { name: "Machines" })).not.toHaveAttribute("target");
  });

  it("a spinner announces itself", () => {
    render(<Spinner />);
    expect(screen.getByRole("status", { name: "Loading" })).toHaveAttribute("data-size", "md");
  });
});
