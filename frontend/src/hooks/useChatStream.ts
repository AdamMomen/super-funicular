import { useCallback, useState } from "react";
import { flushSync } from "react-dom";
import type { ChatRequest, ChatStreamEvent } from "@/api/chat";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface UseChatStreamState {
  messages: ChatMessage[];
  streamingMessage: string;
  chartJson: object | null;
  activeTool: string | null;
  isStreaming: boolean;
  error: string | null;
}

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingMessage, setStreamingMessage] = useState("");
  const [chartJson, setChartJson] = useState<object | null>(null);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (req: ChatRequest) => {
      setError(null);
      setStreamingMessage("");
      setChartJson(null);
      setActiveTool(null);
      setIsStreaming(true);

      const userMsg: ChatMessage = { role: "user", content: req.message };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: req.message,
            session_id: sessionId ?? req.session_id,
            orders_base64: req.orders_base64,
            config_base64: req.config_base64,
          }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error((err as { detail?: string }).detail || "Request failed");
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        if (!reader) throw new Error("No response body");

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() ?? "";

          for (const chunk of lines) {
            if (chunk.startsWith("event: ")) {
              const eventMatch = chunk.match(/event: (\w+)/);
              const dataMatch = chunk.match(/data: (.+)/);
              const event = eventMatch?.[1];
              const data = dataMatch?.[1]
                ? (JSON.parse(dataMatch[1]) as ChatStreamEvent)
                : null;

              if (event === "session" && data && "session_id" in data) {
                setSessionId((data as { session_id: string }).session_id);
              } else if (event === "tool_start" && data && "tool" in data) {
                setActiveTool((data as { tool: string }).tool);
              } else if (event === "tool_complete") {
                setActiveTool(null);
              } else if (event === "text" && data && "delta" in data) {
                const delta = (data as { delta: string }).delta;
                flushSync(() => {
                  setStreamingMessage((prev) => prev + delta);
                });
              } else if (event === "chart" && data && "data" in data) {
                setChartJson((data as { data: object }).data);
              } else if (event === "done" && data && "response" in data) {
                const full = (data as { response: string }).response;
                setStreamingMessage("");
                setMessages((prev) => [
                  ...prev,
                  { role: "assistant", content: full },
                ]);
              } else if (event === "error" && data && "message" in data) {
                setError((data as { message: string }).message);
              }
            }
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setIsStreaming(false);
        setActiveTool(null);
      }
    },
    [sessionId]
  );

  return {
    messages,
    streamingMessage,
    chartJson,
    activeTool,
    isStreaming,
    error,
    sendMessage,
    sessionId,
  };
}
