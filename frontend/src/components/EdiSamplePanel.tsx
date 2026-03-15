import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Check, Loader2 } from "lucide-react";

export function EdiSamplePanel() {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch("/api/forecast/sample-edi")
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error("Failed to load"))))
      .then(setContent)
      .catch(() => setContent(null))
      .finally(() => setLoading(false));
  }, []);

  const handleCopy = async () => {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <aside
      data-tour="edi-sample-panel"
      className="w-96 shrink-0 border-l border-border bg-muted/20 flex flex-col min-h-0"
    >
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">Sample EDI 850</h3>
        <Button
          data-tour="edi-copy-btn"
          variant="outline"
          size="sm"
          onClick={handleCopy}
          disabled={!content || loading}
          className="gap-1.5"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-green-600" />
              Copied!
            </>
          ) : loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : content ? (
          <pre className="text-[11px] font-mono text-foreground/90 whitespace-pre-wrap break-all">
            {content}
          </pre>
        ) : (
          <p className="text-sm text-muted-foreground">Sample EDI not available.</p>
        )}
      </div>
    </aside>
  );
}
