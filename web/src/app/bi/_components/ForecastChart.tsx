"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Area, ComposedChart
} from "recharts";
import type { ForecastDataPoint } from "../types";
import { useTheme, chartAxisColors } from "@/lib/theme-context";

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
  const { theme } = useTheme();
  const { grid: gridColor, axis: axisColor } = chartAxisColors(theme);
  const forecastColor = theme === "dark" ? "#818cf8" : "#4338ca";
  const historicoColor = theme === "dark" ? "#22c55e" : "#15803d";
  const divPoint = data.findIndex(d => d.previsao !== undefined && d.historico === 0);

  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis
            dataKey="periodo"
            tick={{ fill: axisColor, fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            interval={Math.floor(data.length / 10)}
          />
          <YAxis
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            tick={{ fill: axisColor, fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            x={data[divPoint]?.periodo}
            stroke={axisColor}
            strokeDasharray="5 5"
            label={{ value: "Hoje", position: "top", fill: axisColor, fontSize: 10 }}
          />
          {/* Confidence band */}
          <Area
            type="monotone"
            dataKey="limiteSuperior"
            stroke="none"
            fill={forecastColor}
            fillOpacity={0.08}
            name="Limite Superior"
          />
          <Area
            type="monotone"
            dataKey="limiteInferior"
            stroke="none"
            fill={forecastColor}
            fillOpacity={0.08}
            name="Limite Inferior"
          />
          {/* Historical */}
          <Line
            type="monotone"
            dataKey="historico"
            stroke={historicoColor}
            strokeWidth={2}
            dot={false}
            name="Histórico"
            connectNulls
          />
          {/* Forecast */}
          <Line
            type="monotone"
            dataKey="previsao"
            stroke={forecastColor}
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
