import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerCostFooter } from "@/components/AnswerCostFooter";

describe("AnswerCostFooter", () => {
  it("formats model, tokens, cost, latency and grounding", () => {
    render(
      <AnswerCostFooter
        answer={{
          text: "t", citations: [], is_grounded: true, mode: "agentic",
          model_name: "gpt-5.4-mini", input_tokens: 1234, output_tokens: 56,
          estimated_cost_usd: 0.00118, latency_ms: 2345,
        }}
      />,
    );
    expect(screen.getByText(/gpt-5\.4-mini/)).toBeDefined();
    expect(screen.getByText(/1234 in \/ 56 out/)).toBeDefined();
    expect(screen.getByText(/\$0\.0012/)).toBeDefined();
    expect(screen.getByText(/2345 ms/)).toBeDefined();
    expect(screen.getByText(/grounded/i)).toBeDefined();
  });
});
