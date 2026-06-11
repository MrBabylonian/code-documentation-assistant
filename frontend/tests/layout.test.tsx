import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RootLayout from "@/app/layout";

describe("RootLayout", () => {
  it("renders children inside the app shell", () => {
    render(
      <RootLayout>
        <p>shell-child</p>
      </RootLayout>,
    );
    expect(screen.getByText("shell-child")).toBeDefined();
  });
});
