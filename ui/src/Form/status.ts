import { createContext, useContext } from "react";
import type { FormProblem } from "../hooks/formProblems";

export interface FormStatus {
  submitting: boolean;
  problem: FormProblem | null;
}

export const FormStatusContext = createContext<FormStatus>({ submitting: false, problem: null });

/** Is the enclosing form sending, and did its last send fail? */
export function useFormStatus(): FormStatus {
  return useContext(FormStatusContext);
}
