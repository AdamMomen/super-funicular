/** Compact visualization of data sources flowing into the forecast pipeline. */

import { FileSpreadsheet, FileCode, ChevronRight, BarChart3 } from "lucide-react";

interface DataSourcesFlowProps {
  selectedSource?: "csv" | "edi";
  onSourceChange?: (source: "csv" | "edi") => void;
}

export function DataSourcesFlow({ selectedSource = "csv", onSourceChange }: DataSourcesFlowProps) {
  const csvSelected = selectedSource === "csv";
  const ediSelected = selectedSource === "edi";

  return (
    <div className="rounded-lg border border-border bg-muted/30 px-4 py-3">
      <p className="text-[11px] font-medium text-muted-foreground mb-2 uppercase tracking-wide">
        Data sources → forecast
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => onSourceChange?.("csv")}
          className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 transition-colors ${
            csvSelected
              ? "bg-primary/10 border-primary ring-2 ring-ring"
              : "bg-background border-border hover:bg-muted/50"
          }`}
          title="order_date, sku, quantity, channel"
        >
          <FileSpreadsheet className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[12px] font-medium">CSV</span>
        </button>
        <button
          type="button"
          onClick={() => onSourceChange?.("edi")}
          className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 transition-colors ${
            ediSelected
              ? "bg-primary/10 border-primary ring-2 ring-ring"
              : "bg-background border-border hover:bg-muted/50"
          }`}
          title="X12 850 Purchase Order — BEG, PO1, REF*VP"
        >
          <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[12px] font-medium">EDI 850</span>
        </button>
        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <BarChart3 className="h-3.5 w-3.5" />
          <span className="text-[12px]">ETL → Forecast → Recommendations</span>
        </div>
      </div>
    </div>
  );
}
