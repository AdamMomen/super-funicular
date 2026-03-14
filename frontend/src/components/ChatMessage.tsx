import { cn } from "@/lib/utils";
import { User, Bot } from "lucide-react";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export function ChatMessage({ role, content, isStreaming }: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "group flex gap-4 px-4 py-6",
        isUser ? "flex-row-reverse" : ""
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "flex-1 space-y-1 min-w-0",
          isUser ? "text-right" : ""
        )}
      >
        <div
          className={cn(
            "inline-block max-w-[85%] rounded-lg px-4 py-2.5 text-[13px] leading-relaxed",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-secondary rounded-bl-sm"
          )}
        >
          <p className="whitespace-pre-wrap">
            {content}
            {isStreaming && (
              <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-current align-middle" />
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
