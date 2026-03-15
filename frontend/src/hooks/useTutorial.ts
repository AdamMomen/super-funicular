import { useCallback, useRef } from "react";
import { driver, type DriveStep } from "driver.js";
import "driver.js/dist/driver.css";

type InputMode = "orders" | "edi";

const csvTourSteps: DriveStep[] = [
  {
    element: "[data-tour='csv-badge']",
    popover: {
      title: "CSV: Order table data",
      description:
        "Start with CSV. Your order history as a table: date, SKU, quantity, and channel. Load sample data or enter your own.",
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
      title: "EDI 850: Retailer purchase orders",
      description: "Switch to EDI 850 to use X12 Purchase Order format. Retailers send POs in this standard.",
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

export function useTutorial(inputMode: InputMode, onModeChange?: (mode: InputMode) => void) {
  const driverRef = useRef<ReturnType<typeof driver> | null>(null);

  const startTutorial = useCallback(() => {
    if (driverRef.current) {
      driverRef.current.destroy();
      driverRef.current = null;
    }

    const mode = inputMode;
    const steps = mode === "edi" ? ediTourSteps : csvTourSteps;

    // If starting EDI tour from orders mode, switch to EDI first so the panel renders
    if (mode === "edi" && onModeChange) {
      onModeChange("edi");
      setTimeout(() => {
        driverRef.current = driver({
          showProgress: true,
          allowClose: true,
          overlayColor: "rgba(0,0,0,0.5)",
          steps,
          onDestroyStarted: () => {
            driverRef.current?.destroy();
            driverRef.current = null;
          },
        });
        driverRef.current.drive();
      }, 200);
    } else {
      driverRef.current = driver({
        showProgress: true,
        allowClose: true,
        overlayColor: "rgba(0,0,0,0.5)",
        steps,
        onDestroyStarted: () => {
          driverRef.current?.destroy();
          driverRef.current = null;
        },
      });
      driverRef.current.drive();
    }
  }, [inputMode, onModeChange]);

  return { startTutorial };
}
