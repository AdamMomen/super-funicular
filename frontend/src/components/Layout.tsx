import { useState } from "react";
import { DataSourcesFlow } from "@/components/DataSourcesFlow";
import { ForecastTab } from "@/components/ForecastTab";

export function Layout() {
  const [inputMode, setInputMode] = useState<"orders" | "edi">("orders");

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className="mx-auto max-w-3xl w-full px-6 py-10 flex flex-col flex-1 min-h-0">
        <header className="mb-6">
          <h1 className="text-[17px] font-medium text-foreground">
            CPG Demand Forecast
          </h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Order history → 90-day forecast and reorder recommendations
          </p>
          <div className="mt-4">
            <DataSourcesFlow
              selectedSource={inputMode === "orders" ? "csv" : "edi"}
              onSourceChange={(s) => setInputMode(s === "csv" ? "orders" : "edi")}
            />
          </div>
        </header>
        <div className="mt-6 flex-1">
          <ForecastTab inputMode={inputMode} />
        </div>
      </div>
    </div>
  );
}
