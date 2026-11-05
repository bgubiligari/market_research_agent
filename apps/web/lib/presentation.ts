import type { Metric } from "./contracts";
import { decimal } from "./client";
export const metricNames: Record<string, string> = {
  revenue: "Revenue / net sales",
  revenue_growth: "Revenue growth",
  gross_margin: "Gross margin",
  operating_margin: "Operating margin",
  operating_cash_flow_growth: "Operating cash flow growth",
};
export const fieldNames: Record<string, string> = {
  products_brands: "Products & brands",
  differentiators: "Differentiators",
  customers: "Customers",
  positioning: "Positioning",
  geography: "Geography",
  recent_developments: "Recent developments",
};
export const fields = Object.keys(fieldNames);
export const companyColors = ["#1f766b", "#6c60b6", "#c4863e", "#4c83ae"];
export function metricValue(m: Metric | undefined, compact = false) {
  if (!m || m.status === "unavailable") return "Unavailable";
  if (m.status === "not_meaningful") return "Not meaningful";
  const value = decimal(m.value);
  if (value === null) return "Unavailable";
  if (m.unit === "percent")
    return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
  const amount =
    compact && Math.abs(value) >= 1e9
      ? `${(value / 1e9).toLocaleString(undefined, { maximumFractionDigits: 2 })}bn`
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return `${m.unit} ${amount}`;
}
