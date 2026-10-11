import { act, renderHook, waitFor } from "@testing-library/react";
import { useLoad } from "./useLoad";

describe("useLoad", () => {
  it("loads, then is ready with the data", async () => {
    const { result } = renderHook(() => useLoad(() => Promise.resolve(["laptop"])));
    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.data).toEqual(["laptop"]);
  });

  it("a failure is a problem with its code and trace id, and reload tries again", async () => {
    const load = vi.fn().mockRejectedValueOnce({ status: 503, code: "E_UNAVAILABLE", traceId: "t-3", message: "Down" })
      .mockResolvedValueOnce("ok");
    const { result } = renderHook(() => useLoad(load));
    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(result.current.problem).toEqual({ message: "Down", code: "E_UNAVAILABLE", traceId: "t-3" });
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.status).toBe("ready"));
  });

  it("a field-level refusal still fails closed with a plain problem", async () => {
    const load = () => Promise.reject({ status: 422, body: { error: { problems: [{ loc: ["q"], msg: "bad" }] } } });
    const { result } = renderHook(() => useLoad(load));
    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(result.current.problem).toEqual({ message: "Something went wrong. Try again." });
  });

  it("an answer that arrives after a newer request, or after unmount, is dropped", async () => {
    let first: (v: string) => void = () => {};
    let firstFail: (e: unknown) => void = () => {};
    const load = vi.fn()
      .mockReturnValueOnce(new Promise((resolve) => { first = resolve; }))
      .mockReturnValueOnce(Promise.resolve("second"))
      .mockReturnValueOnce(new Promise((_, reject) => { firstFail = reject; }));
    const { result, unmount } = renderHook(() => useLoad(load));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.data).toBe("second"));
    await act(async () => first("stale"));
    expect(result.current.data).toBe("second");
    act(() => result.current.reload());
    unmount();
    await act(async () => firstFail({ status: 500 }));
  });
});
