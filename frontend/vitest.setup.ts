import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest runs without globals, so Testing Library's automatic cleanup never
// registers — without this hook, rendered DOM bleeds between tests in a file.
afterEach(() => {
  cleanup();
});
