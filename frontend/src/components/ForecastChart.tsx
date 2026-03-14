import Plot from "react-plotly.js";
import { Card } from "@/components/ui/card";

interface ForecastChartProps {
  chartJson: object | null;
  className?: string;
}

export function ForecastChart({ chartJson, className }: ForecastChartProps) {
  if (!chartJson || typeof chartJson !== "object") return null;

  const fig = chartJson as { data?: object[]; layout?: object };
  if (!fig.data?.length) return null;

  return (
    <Card className={className}>
      <Plot
        data={fig.data as object[]}
        layout={{
          ...fig.layout,
          autosize: true,
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { color: "hsl(var(--foreground))" },
          margin: { t: 80, r: 80, b: 60, l: 60 },
          legend: {
            ...(fig.layout as { legend?: object })?.legend,
            yanchor: "top",
            y: 1,
            xanchor: "right",
            x: 1,
            orientation: "h",
          },
        }}
        useResizeHandler
        style={{ width: "100%", minHeight: 300 }}
      />
    </Card>
  );
}
