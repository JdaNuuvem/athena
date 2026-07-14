import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Area, ComposedChart
} from "recharts";
import type { ForecastDataPoint } from "../types";

interface ForecastChartProps {
  data: ForecastDataPoint[];
  height?: number;
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-400 mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4">
          <span className="text-neutral-400">{p.name}:</span>
          <span className="text-neutral-200 font-mono">
            {p.value != null ? `R$ ${(p.value / 1000).toFixed(1)}k` : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function ForecastChart({ data, height = 280 }: ForecastChartProps) {
  const divPoint = data.findIndex(d => d.previsao !== undefined && d.historico === 0);

  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="periodo"
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            interval={Math.floor(data.length / 10)}
          />
          <YAxis
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            x={data[divPoint]?.periodo}
            stroke="#71717a"
            strokeDasharray="5 5"
            label={{ value: "Hoje", position: "top", fill: "#71717a", fontSize: 10 }}
          />
          {/* Confidence band */}
          <Area
            type="monotone"
            dataKey="limiteSuperior"
            stroke="none"
            fill="#818cf8"
            fillOpacity={0.08}
            name="Limite Superior"
          />
          <Area
            type="monotone"
            dataKey="limiteInferior"
            stroke="none"
            fill="#818cf8"
            fillOpacity={0.08}
            name="Limite Inferior"
          />
          {/* Historical */}
          <Line
            type="monotone"
            dataKey="historico"
            stroke="#22c55e"
            strokeWidth={2}
            dot={false}
            name="Histórico"
            connectNulls
          />
          {/* Forecast */}
          <Line
            type="monotone"
            dataKey="previsao"
            stroke="#818cf8"
            strokeWidth={2}
            strokeDasharray="4 4"
            dot={false}
            name="Previsão"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
