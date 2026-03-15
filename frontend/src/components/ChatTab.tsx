import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { FileUpload } from "@/components/FileUpload";
import { ChatMessage } from "@/components/ChatMessage";
import { ForecastChart } from "@/components/ForecastChart";
import { useChatStream } from "@/hooks/useChatStream";
import { Send, Loader2, Paperclip, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

const SUGGESTED_PROMPTS = [
  "Run a forecast with sample data",
  "What are the inventory recommendations?",
  "Show me the forecast chart for SKU-001",
];

export function ChatTab() {
  const [input, setInput] = useState("");
  const [ordersBase64, setOrdersBase64] = useState<string | null>(null);
  const [configBase64, setConfigBase64] = useState<string | null>(null);
  const [chatConfigured, setChatConfigured] = useState<boolean | null>(null);
  const [showContext, setShowContext] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    streamingMessage,
    chartJson,
    activeTool,
    isStreaming,
    error,
    sendMessage,
  } = useChatStream();

  useEffect(() => {
    fetch("/api/chat/configured")
      .then((r) => r.json())
      .then((d: { configured: boolean }) => setChatConfigured(d.configured))
      .catch(() => setChatConfigured(false));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMessage]);

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || isStreaming) return;
    setInput("");
    sendMessage({
      message: msg,
      orders_base64: ordersBase64 ?? undefined,
      config_base64: configBase64 ?? undefined,
    });
  };

  const handleOrdersFile = async (file: File) => {
    const buf = await file.arrayBuffer();
    const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
    setOrdersBase64(b64);
  };

  const handleConfigFile = async (file: File) => {
    const buf = await file.arrayBuffer();
    const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
    setConfigBase64(b64);
  };

  const isEmpty = messages.length === 0 && !streamingMessage;
  const isDisabled = !chatConfigured || isStreaming;

  return (
    <div className="flex flex-col flex-1 min-h-[480px]">
      {/* Collapsible context */}
      <div className="mb-2">
        <button
          type="button"
          onClick={() => setShowContext(!showContext)}
          className="flex items-center gap-2 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
        >
          <Paperclip className="h-4 w-4" />
          <span>Upload data for context</span>
          {showContext ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {showContext && (
          <div className="mt-3 p-4 rounded-lg border border-border bg-secondary/30">
            <FileUpload
              onFileSelect={handleOrdersFile}
              onConfigSelect={handleConfigFile}
              accept=".csv,.edi,.x12"
              label="Upload orders CSV or EDI 850 for chat context"
            />
          </div>
        )}
      </div>

      {/* Alerts */}
      {chatConfigured === false && (
        <Alert className="mb-4 border-amber-500/50 bg-amber-500/10">
          <AlertTitle>Chat not configured</AlertTitle>
          <AlertDescription>
            Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN. The Forecast tab works without these.
          </AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert className="mb-4 border-destructive/50 bg-destructive/10">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-h-0 rounded-lg border border-border bg-card">
        <div className="flex-1 overflow-y-auto">
          {isEmpty && chatConfigured && (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <h2 className="text-[17px] font-medium text-foreground mb-2">
                How can I help you today?
              </h2>
              <p className="text-[13px] text-muted-foreground mb-8 max-w-md">
                Ask about forecasts, inventory recommendations, or run analysis with sample data.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setInput(prompt)}
                    className="px-4 py-2 rounded-lg border border-border bg-transparent hover:bg-secondary text-[13px] transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <ChatMessage key={i} role={m.role} content={m.content} />
          ))}
          {streamingMessage && (
            <ChatMessage role="assistant" content={streamingMessage} isStreaming />
          )}
          {activeTool && (
            <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              <span>Running {activeTool}...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Charts inline */}
        {chartJson && (
          <div className="border-t border-border/50 p-4">
            <ForecastChart chartJson={chartJson} />
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-border p-4">
          <div className="flex gap-2 items-end max-w-3xl mx-auto">
            <div className="flex-1 relative rounded-lg border border-border bg-secondary/30 px-4 py-3 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background">
              <Textarea
                placeholder="Message CPG Forecast..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                rows={1}
                className="min-h-[24px] max-h-[200px] resize-none border-0 bg-transparent p-0 pr-8 focus-visible:ring-0 focus-visible:ring-offset-0"
                disabled={isDisabled}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className={cn(
                  "absolute right-2 bottom-2 h-8 w-8 rounded-full",
                  input.trim() ? "bg-primary text-primary-foreground hover:bg-primary/90" : ""
                )}
                onClick={handleSend}
                disabled={isDisabled || !input.trim()}
              >
                {isStreaming ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
          <p className="text-[12px] text-muted-foreground text-center mt-2">
            CPG Forecast can make mistakes. Check important forecasts.
          </p>
        </div>
      </div>
    </div>
  );
}
