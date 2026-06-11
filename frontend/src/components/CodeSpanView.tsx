"use client";

import { useEffect, useState } from "react";

import type { FileSpanResponse } from "@/lib/apiTypes";

const EXTENSION_TO_SHIKI_LANGUAGE: Record<string, string> = {
  py: "python", ts: "typescript", tsx: "tsx", js: "javascript", jsx: "jsx",
  md: "markdown", json: "json", yaml: "yaml", yml: "yaml", toml: "toml",
};

interface HighlightedSpan {
  fileSpan: FileSpanResponse;
  html: string;
}

export function CodeSpanView({ fileSpan }: { fileSpan: FileSpanResponse }) {
  // remembering WHICH span the html belongs to (instead of resetting state in the
  // effect) keeps stale highlights out without a synchronous setState-in-effect
  const [highlightedSpan, setHighlightedSpan] = useState<HighlightedSpan | null>(null);

  useEffect(() => {
    let isCancelled = false;
    async function highlight() {
      try {
        const { codeToHtml } = await import("shiki"); // lazy: keeps the main bundle lean
        const fileExtension = fileSpan.file_path.split(".").pop() ?? "";
        const renderedHtml = await codeToHtml(fileSpan.content, {
          lang: EXTENSION_TO_SHIKI_LANGUAGE[fileExtension] ?? "text",
          theme: "github-dark",
        });
        if (!isCancelled) setHighlightedSpan({ fileSpan, html: renderedHtml });
      } catch {
        // highlighting is progressive enhancement — the numbered fallback below stays
      }
    }
    void highlight();
    return () => {
      isCancelled = true;
    };
  }, [fileSpan]);

  const highlightedHtml =
    highlightedSpan !== null && highlightedSpan.fileSpan === fileSpan
      ? highlightedSpan.html
      : null;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <div className="border-b border-slate-800 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-400">
        {`${fileSpan.file_path}:${fileSpan.start_line}-${fileSpan.end_line}`}
      </div>
      {highlightedHtml !== null ? (
        <div
          className="overflow-x-auto text-sm [&_pre]:p-3"
          dangerouslySetInnerHTML={{ __html: highlightedHtml }}
        />
      ) : (
        <pre className="overflow-x-auto p-3 font-mono text-sm text-slate-300">
          {fileSpan.content.split("\n").map((contentLine, lineOffset) => (
            <div key={lineOffset}>
              <span className="mr-4 inline-block w-10 select-none text-right text-slate-600">
                {fileSpan.start_line + lineOffset}
              </span>
              {contentLine}
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}
