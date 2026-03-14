import { ForecastTab } from "@/components/ForecastTab";

export function Layout() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className="mx-auto max-w-3xl w-full px-6 py-10 flex flex-col flex-1 min-h-0">
        <header className="mb-10">
          <h1 className="text-[17px] font-medium text-foreground">
            CPG Demand Forecast
          </h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Order history → 90-day forecast and reorder recommendations
          </p>
        </header>
        <div className="mt-6 flex-1">
          <ForecastTab />
        </div>
      </div>
    </div>
  );
}
