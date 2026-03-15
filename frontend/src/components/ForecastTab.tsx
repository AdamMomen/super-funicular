import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ForecastChart } from "@/components/ForecastChart";
import { AlertCircle, HelpCircle, Loader2, Plus, Trash2 } from "lucide-react";

interface OrderRow {
  order_date: string;
  sku: string;
  quantity: number;
  channel: string;
}

interface RecommendationRow {
  sku: string;
  forecast_90d: number;
  daily_avg: number;
  reorder_point: number;
  reorder_qty: number;
  current_inv: number;
  recommendation: string;
  days_to_stockout: number | null;
}

const emptyOrder = (): OrderRow => ({
  order_date: new Date().toISOString().slice(0, 10),
  sku: "",
  quantity: 0,
  channel: "",
});

interface ForecastTabProps {
  inputMode?: "orders" | "edi";
}

export function ForecastTab({ inputMode = "orders" }: ForecastTabProps) {
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [algorithm, setAlgorithm] = useState<
    "holt_winters" | "simple_mean" | "naive" | "rolling_ma" | "exp_smoothing"
  >("holt_winters");
  const [rollingWindow, setRollingWindow] = useState(14);
  const [showAllRows, setShowAllRows] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingSample, setLoadingSample] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartsBySku, setChartsBySku] = useState<Record<string, object>>({});
  const [algorithmUsed, setAlgorithmUsed] = useState<string | null>(null);
  const [fallback, setFallback] = useState(false);
  const [recommendations, setRecommendations] = useState<RecommendationRow[]>([]);
  const [rawRowCount, setRawRowCount] = useState<number | null>(null);
  const [skusCount, setSkusCount] = useState<number | null>(null);
  const [ediText, setEdiText] = useState("");

  useEffect(() => {
    fetch("/api/forecast/sample-orders")
      .then((r) => r.json())
      .then((d: { orders?: OrderRow[] }) => setOrders(d.orders ?? []))
      .catch(() => setOrders([emptyOrder()]))
      .finally(() => setLoadingSample(false));
  }, []);

  const updateOrder = (i: number, field: keyof OrderRow, value: string | number) => {
    setOrders((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], [field]: value };
      return next;
    });
  };

  const addRow = () => setOrders((prev) => [...prev, emptyOrder()]);

  const removeRow = (i: number) =>
    setOrders((prev) => (prev.length <= 1 ? prev : prev.filter((_, j) => j !== i)));

  const runForecast = async () => {
    setError(null);
    setAlgorithmUsed(null);
    setFallback(false);
    setLoading(true);

    try {
      if (inputMode === "edi") {
        const trimmed = ediText.trim();
        if (!trimmed) {
          setError("Paste EDI 850 content to run forecast");
          setLoading(false);
          return;
        }
        const blob = new Blob([trimmed], { type: "text/plain" });
        const formData = new FormData();
        formData.append("orders", blob, "orders.edi");
        formData.append("horizon", "90");
        formData.append("freq", "D");

        const res = await fetch("/api/forecast", { method: "POST", body: formData });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error((err as { detail?: string }).detail || "Request failed");
        }
        const data = (await res.json()) as {
          charts_by_sku?: Record<string, object>;
          chart_json?: object;
          table_data?: RecommendationRow[];
          raw_row_count?: number;
          skus_count?: number;
        };
        setChartsBySku(data.charts_by_sku ?? (data.chart_json ? { "All SKUs": data.chart_json } : {}));
        setRecommendations(data.table_data ?? []);
        setRawRowCount(data.raw_row_count ?? null);
        setSkusCount(data.skus_count ?? null);
        setAlgorithmUsed(null);
        setFallback(false);
      } else {
        const valid = orders.filter((o) => o.sku.trim() && o.quantity > 0);
        if (valid.length === 0) {
          setError("Add at least one order with SKU and quantity");
          setLoading(false);
          return;
        }
        const res = await fetch("/api/forecast/json", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            orders: valid.map((o) => ({
              order_date: o.order_date,
              sku: o.sku.trim(),
              quantity: Number(o.quantity),
              channel: o.channel || undefined,
            })),
            algorithm: algorithm || "holt_winters",
            ...(algorithm === "rolling_ma" && { rolling_window: rollingWindow }),
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error((err as { detail?: string }).detail || "Request failed");
        }
        const data = (await res.json()) as {
          charts_by_sku?: Record<string, object>;
          table_data?: RecommendationRow[];
          raw_row_count?: number;
          skus_count?: number;
          algorithm_used?: string;
          model_used?: string;
          fallback?: boolean;
        };
        setChartsBySku(data.charts_by_sku ?? {});
        setRecommendations(data.table_data ?? []);
        setRawRowCount(data.raw_row_count ?? null);
        setSkusCount(data.skus_count ?? null);
        setAlgorithmUsed(data.model_used ?? data.algorithm_used ?? null);
        setFallback(data.fallback ?? false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const downloadJson = () => {
    const blob = new Blob(
      [JSON.stringify({ table_data: recommendations, raw_row_count: rawRowCount, skus_count: skusCount }, null, 2)],
      { type: "application/json" }
    );
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "forecast-recommendations.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const formatNum = (n: number) => n.toLocaleString();
  const recBadge = (v: string) => {
    if (v === "ORDER_NOW") return <Badge variant="destructive">Order now</Badge>;
    if (v === "LOW_STOCK") return <Badge className="bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/30">Low stock</Badge>;
    return <Badge variant="secondary">OK</Badge>;
  };

  const urgencyOrder = (a: RecommendationRow, b: RecommendationRow) => {
    const order = { ORDER_NOW: 0, LOW_STOCK: 1, OK: 2 };
    return (order[a.recommendation as keyof typeof order] ?? 2) - (order[b.recommendation as keyof typeof order] ?? 2);
  };
  const sortedRecommendations = [...recommendations].sort(urgencyOrder);
  const urgentCount = recommendations.filter((r) => r.recommendation === "ORDER_NOW").length;
  const lowStockCount = recommendations.filter((r) => r.recommendation === "LOW_STOCK").length;

  const visibleOrders = showAllRows ? orders : orders.slice(0, 10);
  const hiddenCount = orders.length - 10;

  if (loadingSample) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground max-w-2xl">
        Forecast demand and get reorder recommendations from your historical order data. Enter orders below, run the forecast, and view the chart and recommendations.
      </p>

      {/* Input: Orders table or EDI textarea */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <h3 className="text-sm font-medium">{inputMode === "edi" ? "EDI 850" : "Orders"}</h3>
          <span
            className="text-muted-foreground cursor-help"
            title={
              inputMode === "edi"
                ? "Paste raw X12 850 Purchase Order content. The parser extracts BEG, PO1, and REF*VP segments."
                : "Your historical order data. Each row is one order: date, product SKU, quantity sold, and sales channel (e.g. DTC, Amazon). Load sample data or enter your own. Hover over column headers for field descriptions."
            }
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </span>
        </div>
        <p className="text-[12px] text-muted-foreground mb-2">
          {inputMode === "edi"
            ? "Paste X12 850 Purchase Order content below. Run the forecast to extract order lines and generate demand predictions."
            : "Add order dates, SKUs, quantities, and channels. Load sample data to try it, or enter your own."}
        </p>

        {inputMode === "edi" ? (
          <div className="rounded-lg border border-border overflow-hidden">
            <textarea
              id="edi-textarea"
              data-tour="edi-textarea"
              value={ediText}
              onChange={(e) => setEdiText(e.target.value)}
              placeholder="Paste X12 850 Purchase Order content here..."
              className="w-full min-h-[200px] p-4 text-[13px] font-mono bg-background text-foreground placeholder:text-muted-foreground resize-y focus:outline-none focus:ring-2 focus:ring-ring focus:ring-inset"
              spellCheck={false}
            />
            <div className="flex items-center justify-end px-4 py-2 border-t border-border">
              <Button
                data-tour="forecast-btn"
                onClick={runForecast}
                disabled={loading}
                title="Run ETL to parse EDI, aggregate orders, then forecast demand per SKU."
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Forecast"}
              </Button>
            </div>
          </div>
        ) : (
        <div data-tour="orders-table" className="rounded-lg border border-border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead title="Date the order was placed. Format: YYYY-MM-DD.">Date</TableHead>
              <TableHead title="Product identifier (stock keeping unit). Unique code for each product, e.g. SKU-001.">SKU</TableHead>
              <TableHead title="Number of units ordered. Must be a positive integer.">Qty</TableHead>
              <TableHead title="Sales channel where the order came from. Examples: DTC (direct-to-consumer), Amazon, Retail.">Channel</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleOrders.map((row, i) => (
              <TableRow key={i}>
                <TableCell className="p-1">
                  <Input
                    type="date"
                    value={row.order_date}
                    onChange={(e) => updateOrder(i, "order_date", e.target.value)}
                    className="h-8 border-0 bg-transparent text-[13px]"
                  />
                </TableCell>
                <TableCell className="p-1">
                  <Input
                    value={row.sku}
                    onChange={(e) => updateOrder(i, "sku", e.target.value)}
                    placeholder="SKU-001"
                    className="h-8 border-0 bg-transparent text-[13px]"
                  />
                </TableCell>
                <TableCell className="p-1">
                  <Input
                    type="number"
                    min={0}
                    value={row.quantity || ""}
                    onChange={(e) => updateOrder(i, "quantity", parseInt(e.target.value, 10) || 0)}
                    placeholder="0"
                    className="h-8 w-20 border-0 bg-transparent text-[13px]"
                  />
                </TableCell>
                <TableCell className="p-1">
                  <Input
                    value={row.channel}
                    onChange={(e) => updateOrder(i, "channel", e.target.value)}
                    placeholder="DTC"
                    className="h-8 border-0 bg-transparent text-[13px]"
                  />
                </TableCell>
                <TableCell className="p-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => removeRow(i)}
                    disabled={orders.length <= 1}
                    title="Remove this order row from the table."
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="flex items-center justify-between px-4 py-2 border-t border-border">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={addRow}
              title="Add a new blank order row to the table. Fill in date, SKU, quantity, and optionally channel."
            >
              <Plus className="h-4 w-4 mr-1" />
              Add row
            </Button>
            {orders.length > 10 && (
              showAllRows ? (
                <button
                  type="button"
                  onClick={() => setShowAllRows(false)}
                  className="text-[13px] text-primary hover:underline"
                  title="Collapse table to show only the first 10 rows."
                >
                  Show less
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowAllRows(true)}
                  className="text-[13px] text-primary hover:underline"
                  title="Expand table to show all order rows."
                >
                  Show more ({hiddenCount} more)
                </button>
              )
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {inputMode === "orders" && (
              <>
                <select
                  value={algorithm}
                  onChange={(e) =>
                    setAlgorithm(
                      e.target.value as
                        | "holt_winters"
                        | "simple_mean"
                        | "naive"
                        | "rolling_ma"
                        | "exp_smoothing"
                    )
                  }
                  className="h-9 rounded-md border border-border bg-background px-3 text-[13px] text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  title="Holt-Winters: trend + seasonality (curved). Simple mean, Naive, Rolling MA: constant forecast (flat line). Exp smoothing: smoothed level."
                >
                  <option value="holt_winters">Holt-Winters</option>
                  <option value="simple_mean">Simple mean</option>
                  <option value="naive">Naive</option>
                  <option value="rolling_ma">Rolling MA</option>
                  <option value="exp_smoothing">Exponential smoothing</option>
                </select>
                {algorithm === "rolling_ma" && (
                  <div className="flex items-center gap-1">
                    <label htmlFor="rolling-window" className="text-[12px] text-muted-foreground">
                      Window:
                    </label>
                    <input
                      id="rolling-window"
                      type="number"
                      min={1}
                      max={90}
                      value={rollingWindow}
                      onChange={(e) => setRollingWindow(Math.max(1, parseInt(e.target.value, 10) || 14))}
                      className="h-9 w-16 rounded-md border border-border bg-background px-2 text-[13px] text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                )}
              </>
            )}
            <Button
              data-tour="forecast-btn"
              onClick={runForecast}
              disabled={loading}
              title="Run ETL to clean and aggregate your orders, then forecast demand per SKU. Outputs a chart (historical + 90-day forecast) and a reorder recommendations table."
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Forecast"}
            </Button>
          </div>
        </div>
        </div>
        )}
      </div>

      {error && <p className="text-[13px] text-destructive">{error}</p>}

      <div data-tour="forecast-results" className="space-y-6">
        {loading && (
          <div className="flex items-center justify-center py-16 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        )}

        {!loading && Object.keys(chartsBySku).length > 0 && (
          <>
            <div data-tour="forecast-chart">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-sm font-medium">Forecast chart</h3>
              {algorithmUsed && (
                <Badge variant="outline" className="text-[11px] font-normal">
                  {algorithmUsed.replace(/_/g, " ")}
                </Badge>
              )}
              {fallback && (
                <span className="text-[11px] text-amber-600 dark:text-amber-400">
                  (Holt-Winters needs 30+ days; fell back)
                </span>
              )}
              <span
                className="text-muted-foreground cursor-help"
                title="Shows historical demand (past orders) and 90-day forecast per SKU. Use this to visualize trends and projected demand over time."
              >
                <HelpCircle className="h-3.5 w-3.5" />
              </span>
            </div>
            <Tabs defaultValue={Object.keys(chartsBySku)[0]} className="w-full">
              <TabsList className="mb-2">
                {Object.keys(chartsBySku).map((sku) => (
                  <TabsTrigger key={sku} value={sku}>
                    {sku}
                  </TabsTrigger>
                ))}
              </TabsList>
              {Object.entries(chartsBySku).map(([sku, chartJson]) => (
                <TabsContent key={sku} value={sku}>
                  <ForecastChart chartJson={chartJson} className="rounded-lg border border-border p-4" />
                </TabsContent>
              ))}
            </Tabs>
            </div>
          {recommendations.length > 0 && (
            <div data-tour="recommendations-table" className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium">Reorder recommendations</h3>
                  <span
                    className="text-muted-foreground cursor-help"
                    title="Per-SKU recommendations based on forecast, reorder point, and current inventory. Order now = urgent. Low stock = monitor. OK = no action needed."
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                  </span>
                </div>
                {(urgentCount > 0 || lowStockCount > 0) && (
                  <div className="flex items-center gap-3 text-[12px]">
                    {urgentCount > 0 && (
                      <span className="flex items-center gap-1 text-destructive font-medium">
                        <AlertCircle className="h-3.5 w-3.5" />
                        {urgentCount} {urgentCount === 1 ? "SKU" : "SKUs"} need{urgentCount === 1 ? "s" : ""} immediate reorder
                      </span>
                    )}
                    {lowStockCount > 0 && (
                      <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                        <AlertCircle className="h-3.5 w-3.5" />
                        {lowStockCount} {lowStockCount === 1 ? "SKU" : "SKUs"} low stock
                      </span>
                    )}
                  </div>
                )}
              </div>
              <div className="rounded-lg border border-border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead title="Product identifier (stock keeping unit).">SKU</TableHead>
                      <TableHead title="Order now (urgent), Low stock (monitor), or OK (no action).">Status</TableHead>
                      <TableHead title="Units currently in stock.">Current Inv</TableHead>
                      <TableHead title="Predicted units needed over the next 90 days.">90-Day Forecast</TableHead>
                      <TableHead title="How many units to order when restocking.">Reorder Qty</TableHead>
                      <TableHead title="Estimated days until stock runs out at current demand rate.">Days to Stockout</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedRecommendations.map((row, i) => (
                      <TableRow
                        key={row.sku}
                        className={
                          row.recommendation === "ORDER_NOW"
                            ? "bg-destructive/5"
                            : row.recommendation === "LOW_STOCK"
                              ? "bg-amber-500/5"
                              : i % 2 === 1
                                ? "bg-muted/20"
                                : ""
                        }
                      >
                        <TableCell className="font-medium py-3">{row.sku}</TableCell>
                        <TableCell className="py-3">{recBadge(row.recommendation)}</TableCell>
                        <TableCell className="py-3 tabular-nums">{formatNum(row.current_inv)}</TableCell>
                        <TableCell className="py-3 tabular-nums">{formatNum(row.forecast_90d)}</TableCell>
                        <TableCell className="py-3 tabular-nums">{formatNum(row.reorder_qty)}</TableCell>
                        <TableCell className="py-3 tabular-nums text-muted-foreground">
                          {row.days_to_stockout != null ? formatNum(row.days_to_stockout) : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <div className="px-4 py-2 border-t border-border text-[12px] text-muted-foreground flex justify-between items-center">
                  <span>{rawRowCount ?? 0} rows · {skusCount ?? 0} SKUs</span>
                  <button
                    type="button"
                    onClick={downloadJson}
                    className="hover:text-foreground transition-colors"
                    title="Download the full recommendations table as a JSON file."
                  >
                    Download JSON
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
        )}
      </div>
    </div>
  );
}
