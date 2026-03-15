import { useState } from "react";
import { DataSourcesFlow } from "@/components/DataSourcesFlow";
import { EdiSamplePanel } from "@/components/EdiSamplePanel";
import { ForecastTab } from "@/components/ForecastTab";
import { useTutorial } from "@/hooks/useTutorial";
import { BookOpen } from "lucide-react";

export function Layout() {
  const [inputMode, setInputMode] = useState<"orders" | "edi">("orders");
  const { startTutorial } = useTutorial(inputMode, setInputMode);

  const maxWidth = inputMode === "edi" ? "max-w-6xl" : "max-w-3xl";

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className={`mx-auto ${maxWidth} w-full px-6 py-10 flex flex-col flex-1 min-h-0`}>
        <header className="mb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-[17px] font-medium text-foreground">
                CPG Demand Forecast
              </h1>
              <p className="mt-0.5 text-[13px] text-muted-foreground">
                Order history → 90-day forecast and reorder recommendations
              </p>
            </div>
            <button
              type="button"
              onClick={startTutorial}
              className="flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors shrink-0"
            >
              <BookOpen className="h-4 w-4" />
              Take a tour
            </button>
          </div>
          <div className="mt-4">
            <DataSourcesFlow
              selectedSource={inputMode === "orders" ? "csv" : "edi"}
              onSourceChange={(s) => setInputMode(s === "csv" ? "orders" : "edi")}
            />
          </div>
        </header>
        <div className="mt-6 flex-1 flex gap-6 min-h-0">
          <div className="flex-1 min-w-0">
            <ForecastTab inputMode={inputMode} />
          </div>
          {inputMode === "edi" && (
            <EdiSamplePanel />
          )}
        </div>
      </div>
    </div>
  );
}
