const API_BASE = "/api";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  getIndices: () => request("/indices/"),
  getOHLCV: (ticker: string, period = "1y") =>
    request(`/indices/${ticker}/ohlcv?period=${period}`),
  getIndicators: (ticker: string, indicators = "all") =>
    request(`/indices/${ticker}/indicators?indicators=${indicators}`),
  getSignal: (ticker: string) => request(`/indices/${ticker}/signal`),

  getFunds: () => request("/funds/"),
  getFundPerformance: (ticker: string) =>
    request(`/funds/${ticker}/performance`),
  getFundNAV: (ticker: string, period = "1y") =>
    request(`/funds/${ticker}/nav?period=${period}`),
};
