import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useToast } from "../hooks/useToast";
import { ToastProvider } from "./Toast";

function Trigger() {
  const toast = useToast();
  return (
    <>
      <button type="button" onClick={() => toast.show({ message: "Saved", tone: "ok" })}>ok</button>
      <button type="button" onClick={() => toast.show({ message: "Couldn't save", tone: "danger", traceId: "t-2" })}>bad</button>
      <button type="button" onClick={() => toast.show({ message: "Plain" })}>plain</button>
    </>
  );
}

describe("toasts", () => {
  it("show, then go after their time; errors stay longer and interrupt", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ToastProvider durationMs={1000}><Trigger /></ToastProvider>);
    await user.click(screen.getByRole("button", { name: "ok" }));
    await user.click(screen.getByRole("button", { name: "bad" }));
    expect(screen.getByText("Saved").closest("[role=status]")).toHaveAttribute("data-tone", "ok");
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't save · trace t-2");
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(screen.queryByText("Saved")).toBeNull();
    expect(screen.getByText(/Couldn't save/)).toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(screen.queryByText(/Couldn't save/)).toBeNull();
    vi.useRealTimers();
  });

  it("can be dismissed, and a plain one is info", async () => {
    render(<ToastProvider><Trigger /></ToastProvider>);
    await userEvent.click(screen.getByRole("button", { name: "plain" }));
    expect(screen.getByText("Plain").closest("[role=status]")).toHaveAttribute("data-tone", "info");
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Plain")).toBeNull();
  });

  it("useToast without a provider fails loudly", () => {
    vi.mocked(console.error).mockImplementation(() => {});
    expect(() => renderHook(() => useToast())).toThrow("ToastProvider");
  });
});
