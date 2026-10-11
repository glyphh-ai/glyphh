import { problemsOf, UNKNOWN, UNREACHABLE } from "./formProblems";

describe("problemsOf", () => {
  it("puts the server's field problems on their fields, first message each", () => {
    const err = { status: 422, code: "E_INVALID", body: { error: { problems: [
      { loc: ["body", "email"], msg: "Not an email" }, { loc: ["body", "email"], msg: "second" },
      { loc: ["body", "name"], msg: "Required" }, { loc: [], msg: "no field" }, { loc: ["body", "x"] }] } } };
    expect(problemsOf(err)).toEqual({ fields: { email: "Not an email", name: "Required" }, problem: null });
  });

  it("anything else the server refused is one problem, with its code and trace id", () => {
    const err = { status: 409, code: "E_CONFLICT", traceId: "t-1", message: "That name is taken." };
    expect(problemsOf(err)).toEqual({ fields: {}, problem: { message: "That name is taken.", code: "E_CONFLICT", traceId: "t-1" } });
    expect(problemsOf({ status: 500 }).problem).toEqual({ message: UNKNOWN, code: undefined, traceId: undefined });
  });

  it("an unreachable server and an unknown error fail closed with plain words", () => {
    expect(problemsOf({ status: 0 }).problem).toEqual({ message: UNREACHABLE });
    for (const err of [new Error("raw internals"), "x", null, 3]) {
      expect(problemsOf(err)).toEqual({ fields: {}, problem: { message: UNKNOWN } });
    }
  });
});
