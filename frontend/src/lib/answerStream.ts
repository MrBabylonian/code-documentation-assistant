import type { AnswerStreamEvent } from "@/lib/apiTypes";

export class AnswerStreamReader {
  async *read(response: Response): AsyncGenerator<AnswerStreamEvent> {
    if (response.body === null) {
      throw new Error("SSE response has no body");
    }
    const byteReader = response.body.getReader();
    const utf8Decoder = new TextDecoder("utf-8");
    let frameBuffer = "";
    for (;;) {
      const { done, value } = await byteReader.read();
      // stream:true keeps multibyte sequences split across chunks intact
      frameBuffer += utf8Decoder.decode(value ?? new Uint8Array(), { stream: !done });
      frameBuffer = frameBuffer.replace(/\r\n/g, "\n");
      let frameBoundaryIndex = frameBuffer.indexOf("\n\n");
      while (frameBoundaryIndex !== -1) {
        const frameText = frameBuffer.slice(0, frameBoundaryIndex);
        frameBuffer = frameBuffer.slice(frameBoundaryIndex + 2);
        const dataPayload = frameText
          .split("\n")
          .filter((frameLine) => frameLine.startsWith("data:"))
          // strip "data:" plus ONE optional leading space — never trim the payload itself
          .map((frameLine) => frameLine.slice(5).replace(/^ /, ""))
          .join("\n");
        if (dataPayload.length > 0) {
          yield JSON.parse(dataPayload) as AnswerStreamEvent;
        }
        frameBoundaryIndex = frameBuffer.indexOf("\n\n");
      }
      if (done) return;
    }
  }
}
