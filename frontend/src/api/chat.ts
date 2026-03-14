export interface ChatRequest {
  message: string;
  session_id?: string;
  orders_base64?: string;
  config_base64?: string;
}

export interface ChatResponse {
  response: string;
  chart_json?: object;
  session_id: string;
}

/** SSE event data shapes (flat, keyed by event type) */
export interface ChatStreamEvent {
  session_id?: string;
  tool?: string;
  summary?: string;
  delta?: string;
  data?: object;
  response?: string;
  message?: string;
}
