import type { Metric } from "./contracts";
import { decimal } from "./client";
/** A chart is always one metric and one unit; no currency conversion or zero filling. */
export function chartData(
  metrics: Metric[],
  companyIds: string[],
  metric: string,
  unit: string,
) {
  const selected = metrics.filter(
    (m) => m.metric === metric && m.unit === unit,
  );
  const years = [...new Set(selected.map((m) => m.period.fiscal_year))].sort(
    (a, b) => a - b,
  );
  return years.map((year) =>
    Object.fromEntries([
      ["year", year],
      ...companyIds.map((id) => {
        const m = selected.find(
          (m) => m.company_id === id && m.period.fiscal_year === year,
        );
        return [id, m?.status === "available" ? decimal(m.value) : null];
      }),
    ]),
  );
}
