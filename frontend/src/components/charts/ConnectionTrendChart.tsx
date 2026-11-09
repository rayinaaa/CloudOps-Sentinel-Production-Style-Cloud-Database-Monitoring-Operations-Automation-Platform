import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface ConnectionTrendProps {
  currentActive: number;
  currentIdle: number;
  maxConnections: number;
}

export const ConnectionTrendChart: React.FC<ConnectionTrendProps> = ({
  currentActive,
  currentIdle,
  maxConnections,
}) => {
  // Generate synthetic timeseries points ending at live values
  const now = Date.now();
  const data = Array.from({ length: 12 }).map((_, i) => {
    const time = new Date(now - (11 - i) * 60000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    // Gradual realistic drift towards current value
    const factor = (i + 1) / 12;
    const active = Math.max(1, Math.round(currentActive * (0.8 + 0.4 * factor)));
    const idle = Math.max(1, Math.round(currentIdle * (0.9 + 0.2 * factor)));
    return {
      time,
      active,
      idle,
      max: maxConnections,
      saturation: Math.round(((active + idle) / maxConnections) * 100),
    };
  });

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="activeGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#38BDF8" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="idleGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#818CF8" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#818CF8" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
          <XAxis
            dataKey="time"
            stroke="#64748B"
            tick={{ fill: "#64748B", fontSize: 11 }}
            tickLine={false}
          />
          <YAxis
            stroke="#64748B"
            tick={{ fill: "#64748B", fontSize: 11 }}
            tickLine={false}
            domain={[0, Math.max(10, currentActive + currentIdle + 5)]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0D1424",
              borderColor: "#1E293B",
              borderRadius: "8px",
              fontSize: "12px",
              fontFamily: "JetBrains Mono, monospace",
            }}
            labelStyle={{ color: "#94A3B8" }}
          />
          <Area
            type="monotone"
            dataKey="active"
            name="Active Conns"
            stroke="#38BDF8"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#activeGrad)"
          />
          <Area
            type="monotone"
            dataKey="idle"
            name="Idle Conns"
            stroke="#818CF8"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            fillOpacity={1}
            fill="url(#idleGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

