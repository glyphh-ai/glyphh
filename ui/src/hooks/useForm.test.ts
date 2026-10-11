import { z } from "zod";
import { errorsOf } from "./useForm";

describe("errorsOf", () => {
  it("keeps the first message per field and skips rules about the whole form", () => {
    const schema = z.object({ code: z.string().min(4, "Too short").regex(/^\d+$/, "Digits only") })
      .refine(() => false, "Whole form is wrong");
    expect(errorsOf(schema, { code: "ab" })).toEqual({ code: "Too short" });
  });

  it("is empty when everything is valid", () => {
    expect(errorsOf(z.object({ a: z.string() }), { a: "x" })).toEqual({});
  });
});
