import { useCallback, useEffect, useRef } from "react";
import { driver, type DriveStep } from "driver.js";
import "driver.js/dist/driver.css";

const TOUR_CSV_SEEN_KEY = "cpg-forecast-tour-csv-seen";
const TOUR_EDI_SEEN_KEY = "cpg-forecast-tour-edi-seen";

type InputMode = "orders" | "edi";

const csvTourSteps: DriveStep[] = [
  {
    element: "[data-tour='csv-badge']",
    popover: {
      title: "CSV Data Tour",
      description:
        "This tour covers the CSV flow: order table data, date/SKU/quantity/channel. Load sample data or enter your own rows.",
      side: "bottom",
      align: "start",
    },
  },
  {
    element: "[data-tour='orders-table']",
    popover: {
      title: "Orders table",
      description:
        "Load sample data or enter orders. Each row: date, SKU, quantity, and channel. Click 'Add row' for more.",
      side: "bottom",
      align: "start",
    },
  },
  {
    element: "[data-tour='forecast-btn']",
    popover: {
      title: "Run forecast",
      description: "Click Forecast to run the pipeline. The model aggregates orders, fits a time series, and produces a 90-day demand forecast.",
      side: "top",
      align: "end",
    },
  },
  {
    element: "[data-tour='forecast-results']",
    popover: {
      title: "Results",
      description:
        "After running forecast, you'll see the chart (historical demand + 90-day forecast per SKU) and reorder recommendations below.",
      side: "top",
      align: "start",
    },
  },
];

const ediTourSteps: DriveStep[] = [
  {
    element: "[data-tour='edi-badge']",
    popover: {
      title: "EDI 850 Tour",
      description:
        "This tour covers the EDI flow: X12 850 Purchase Orders. Copy sample content, paste it, and run the forecast. Different from the CSV table flow.",
      side: "bottom",
      align: "start",
    },
  },
  {
    element: "[data-tour='edi-sample-panel']",
    popover: {
      title: "Sample EDI content",
      description: "This panel shows sample X12 850 content. Copy it to try the demo without your own file.",
      side: "left",
      align: "start",
    },
  },
  {
    element: "[data-tour='edi-copy-btn']",
    popover: {
      title: "Copy to clipboard",
      description: "Click Copy, then paste the content into the text area on the left.",
      side: "bottom",
      align: "end",
    },
  },
  {
    element: "[data-tour='edi-textarea']",
    popover: {
      title: "Paste EDI here",
      description: "Paste the X12 850 content you copied. Then click Forecast to parse and run the forecast.",
      side: "right",
      align: "start",
    },
  },
  {
    element: "[data-tour='forecast-btn']",
    popover: {
      title: "Run forecast",
      description: "Click Forecast to parse the EDI, aggregate orders, and generate the 90-day demand forecast.",
      side: "top",
      align: "end",
    },
  },
  {
    element: "[data-tour='forecast-results']",
    popover: {
      title: "Chart and recommendations",
      description:
        "View the forecast chart (historical + 90-day projection per SKU) and reorder recommendations. Use the SKU tabs to switch between products.",
      side: "top",
      align: "start",
    },
  },
];

function runDriver(
  steps: DriveStep[],
  mode: InputMode,
  onModeChange?: (mode: InputMode) => void,
  onDestroy?: () => void,
  onDriver?: (d: ReturnType<typeof driver>) => void
) {
  const seenKey = mode === "edi" ? TOUR_EDI_SEEN_KEY : TOUR_CSV_SEEN_KEY;

  const run = () => {
    const d = driver({
      showProgress: true,
      progressText: mode === "edi" ? "EDI {{current}} of {{total}}" : "CSV {{current}} of {{total}}",
      allowClose: true,
      overlayColor: "rgba(0,0,0,0.5)",
      steps,
      onDestroyStarted: (_element, _step, opts) => {
        try {
          localStorage.setItem(seenKey, "1");
        } catch {
          // ignore
        }
        onDestroy?.();
        opts.driver.destroy();
      },
    });
    onDriver?.(d);
    d.drive();
  };
  if (mode === "edi" && onModeChange) {
    onModeChange("edi");
    setTimeout(run, 200);
  } else {
    run();
  }
}

export function useTutorial(inputMode: InputMode, onModeChange?: (mode: InputMode) => void) {
  const driverRef = useRef<ReturnType<typeof driver> | null>(null);
  const hasAutoStartedCsv = useRef(false);
  const hasAutoStartedEdi = useRef(false);

  const startTutorial = useCallback(() => {
    if (driverRef.current) {
      driverRef.current.destroy();
      driverRef.current = null;
    }

    const mode = inputMode;
    const steps = mode === "edi" ? ediTourSteps : csvTourSteps;

    runDriver(steps, mode, onModeChange, () => {
      driverRef.current = null;
    }, (d) => {
      driverRef.current = d;
    });
  }, [inputMode, onModeChange]);

  // Auto-start CSV tour on first visit when in orders mode
  useEffect(() => {
    if (inputMode !== "orders") return;
    try {
      if (localStorage.getItem(TOUR_CSV_SEEN_KEY)) return;
    } catch {
      return;
    }

    const timeout = setTimeout(() => {
      if (hasAutoStartedCsv.current) return;
      hasAutoStartedCsv.current = true;
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
      runDriver(csvTourSteps, "orders", onModeChange, () => {
        driverRef.current = null;
      }, (d) => {
        driverRef.current = d;
      });
    }, 2000);

    return () => clearTimeout(timeout);
  }, [inputMode, onModeChange]);

  // Auto-start EDI tour when user switches to EDI and hasn't seen it
  useEffect(() => {
    if (inputMode !== "edi") return;
    try {
      if (localStorage.getItem(TOUR_EDI_SEEN_KEY)) return;
    } catch {
      return;
    }

    const timeout = setTimeout(() => {
      if (hasAutoStartedEdi.current) return;
      hasAutoStartedEdi.current = true;
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
      runDriver(ediTourSteps, "edi", onModeChange, () => {
        driverRef.current = null;
      }, (d) => {
        driverRef.current = d;
      });
    }, 400);

    return () => clearTimeout(timeout);
  }, [inputMode, onModeChange]);

  return { startTutorial };
}
