import { defineConfig } from "@playwright/test";

// The compose stack is started EXTERNALLY (docker compose up) — no webServer block.
// CI brings the stack up in a prior step; locally, reuse whatever is running.
export default defineConfig({
  testDir: ".",
  use: { baseURL: "http://localhost:3000" },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
