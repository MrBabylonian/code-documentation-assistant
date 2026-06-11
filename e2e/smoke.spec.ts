import { expect, test } from "@playwright/test";

test("home page renders the ingest form", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /ingest a repository/i })).toBeVisible();
  await expect(page.getByPlaceholder(/github\.com/)).toBeVisible();
});

// Full journey: clones + embeds a real repository and asks a real question.
// Costs real OpenAI tokens (~cents) and several minutes — run manually before
// submission (and record it for the demo video): CODEDOC_E2E_FULL=1 npm test
test("full journey: ingest → ready → cited answer", async ({ page }) => {
  test.skip(!process.env.CODEDOC_E2E_FULL, "needs a running stack + real OPENAI key");
  test.setTimeout(8 * 60 * 1000);

  await page.goto("/");
  await page.getByPlaceholder(/github\.com/).fill("https://github.com/fastapi/full-stack-fastapi-template");
  await page.getByRole("button", { name: /ingest/i }).click();

  const repositoryCard = page.locator("article", { hasText: "fastapi/full-stack-fastapi-template" });
  await expect(repositoryCard.getByText("ready")).toBeVisible({ timeout: 6 * 60 * 1000 });

  await repositoryCard.getByRole("link", { name: /ask questions/i }).click();
  await page.getByRole("button", { name: "Single-shot" }).click();
  await page.getByPlaceholder(/ask about this codebase/i).fill("Where is the FastAPI app instantiated?");
  await page.keyboard.press("Enter");

  // a grounded answer arrives with at least one citation chip and the cost footer
  await expect(page.locator("button", { hasText: /backend\/app\// }).first()).toBeVisible({
    timeout: 2 * 60 * 1000,
  });
  await expect(page.getByText(/grounded/i)).toBeVisible();
});
