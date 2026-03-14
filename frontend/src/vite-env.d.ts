/// <reference types="vite/client" />

declare module "react-plotly.js" {
  const Plot: React.ComponentType<{
    data: object[];
    layout?: object;
    config?: object;
    style?: object;
    className?: string;
    useResizeHandler?: boolean;
  }>;
  export default Plot;
}
