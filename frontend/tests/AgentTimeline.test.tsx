import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentTimeline } from "@/components/AgentTimeline";

describe("AgentTimeline", () => {
  it("renders one row per entry with its label", () => {
    render(
      <AgentTimeline
        entries={[
          { kind: "tool_call", label: "search_code", detail: '{"query":"auth"}' },
          { kind: "tool_result", label: "search_code", detail: "<evidence …>" },
          { kind: "notice", label: "retry", detail: "answer had no citations" },
        ]}
      />,
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getAllByText("search_code")).toHaveLength(2);
    expect(screen.getByText(/no citations/)).toBeDefined();
  });
});
