import { render, screen } from "@testing-library/react";
import { Avatar } from "./Avatar";
import { type Mood, VARIANTS, catOf } from "./catShapes";

describe("Avatar", () => {
  it.each(VARIANTS.map((v) => v.id))("draws face %i, named for screen readers", (id) => {
    render(<Avatar variant={id} label={`Face ${id}`} />);
    const cat = screen.getByRole("img", { name: `Face ${id}` });
    expect(cat).toHaveAttribute("data-variant", String(id));
    expect(cat).toHaveAttribute("data-mood", "idle");
  });

  it.each(["idle", "thinking", "generating", "done", "listening", "error", "curious", "sleepy", "playful", "dizzy"] as Mood[])(
    "shows the mood %s in its eye", (mood) => {
      const { container } = render(<Avatar mood={mood} variant={5} label="Cat" size={24} />);
      expect(container.querySelector("svg")).toHaveAttribute("data-mood", mood);
      expect(container.querySelector("svg")).toHaveAttribute("width", "24");
    });

  it("an unknown face is Glyphh's own, and a picture replaces the drawing", () => {
    expect(catOf(99, "idle").name).toBe("Glyphh");
    expect(catOf(2, "done").eye).toBe("wink");
    expect(catOf(2, "idle").eye).toBe("look");
    render(<Avatar image="https://img.test/cat.png" label="Pic" />);
    expect(screen.getByRole("img", { name: "Pic" }).tagName).toBe("IMG");
  });
});
