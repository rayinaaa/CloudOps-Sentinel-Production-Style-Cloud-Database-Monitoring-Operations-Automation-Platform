import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { TableStorageMetric } from "../../types";

interface TableStorageChartProps {
  tables: TableStorageMetric[];
}

export const TableStorageChart: React.FC<TableStorageChartProps> = ({ tables }) => {
  // Parse human readable or display KB values
  const data = tables.map((t) => {
    // extract numeric approximation
    let sizeKb = 100;
    if (t.total_disk_size.includes("kB")) {
      sizeKb = parseFloat(t.total_disk_size) || 100;
    } else if (t.total_disk_size.includes("MB")) {
      sizeKb = (parseFloat(t.total_disk_size) || 1) * 1024;
    } else if (t.total_disk_size.includes("bytes")) {
      sizeKb = Math.round((parseFloat(t.total_disk_size) || 8192) / 1024);
    }
    return {
      name: t.table_name,
      diskKb: sizeKb,
      dataSize: t.table_data_size,
      indexSize: t.index_size,
      pct: t.pct_of_public_schema || 0,
    };
  });

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 10, right: 20, left: 20, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
          <XAxis
            type="number"
            stroke="#64748B"
            tick={{ fill: "#64748B", fontSize: 11 }}
            unit=" kB"
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            stroke="#64748B"
            tick={{ fill: "#94A3B8", fontSize: 12, fontFamily: "JetBrains Mono, monospace" }}
            tickLine={false}
            width={90}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0D1424",
              borderColor: "#1E293B",
              borderRadius: "8px",
              fontSize: "12px",
              fontFamily: "JetBrains Mono, monospace",
            }}
            formatter={(value: any, name: any, item: any) => [
              `${value} kB (${item.payload.pct}% of schema)`,
              "Disk Footprint",
            ]}
          />
          <Bar
            dataKey="diskKb"
            name="Disk Space (kB)"
            fill="#0284C7"
            radius={[0, 4, 4, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

