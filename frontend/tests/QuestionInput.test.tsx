import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QuestionInput } from "@/components/QuestionInput";

describe("QuestionInput", () => {
  it("submits the trimmed question via the Ask button and clears the draft", () => {
    const onSubmit = vi.fn();
    render(<QuestionInput onSubmit={onSubmit} disabled={false} />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "  where is auth?  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    expect(onSubmit).toHaveBeenCalledWith("where is auth?");
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
  });

  it("disables the button while empty and while streaming", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(<QuestionInput onSubmit={onSubmit} disabled={false} />);

    const askButton = screen.getByRole("button", { name: /ask/i });
    expect(askButton).toHaveProperty("disabled", true); // empty draft

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "question" } });
    expect(askButton).toHaveProperty("disabled", false);

    rerender(<QuestionInput onSubmit={onSubmit} disabled={true} />);
    expect(askButton).toHaveProperty("disabled", true); // streaming

    fireEvent.click(askButton);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("still submits on Enter", () => {
    const onSubmit = vi.fn();
    render(<QuestionInput onSubmit={onSubmit} disabled={false} />);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "via enter" } });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", shiftKey: false });

    expect(onSubmit).toHaveBeenCalledWith("via enter");
  });
});
