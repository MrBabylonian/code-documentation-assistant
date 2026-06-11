import { defineConfig } from "@playwright/test";

// The compose stack is started EXTERNALLY (docker compose up) — no webServer block.
// Run via `make e2e` against a running stack; deliberately not a CI job (the full
// journey needs a real OpenAI key and is env-gated behind CODEDOC_E2E_FULL).
export default defineConfig({
  testDir: ".",
  use: { baseURL: "http://localhost:3000" },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
