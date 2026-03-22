
import { memo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface Datum {
  name: string;
  value: number;
  fill: string;
}

export default memo(function ScopeChart({ data }: { data: Datum[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <XAxis dataKey="name" tick={{ fill: "var(--muted)" }} />
        <YAxis
          tick={{ fill: "var(--muted)" }}
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          contentStyle={{
            background: "var(--card)",
            border: "1px solid var(--card-border)",
            borderRadius: 8,
          }}
          formatter={(v: number) => [
            `${v.toLocaleString()} tCO₂e`,
            "Emissions",
          ]}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
});
