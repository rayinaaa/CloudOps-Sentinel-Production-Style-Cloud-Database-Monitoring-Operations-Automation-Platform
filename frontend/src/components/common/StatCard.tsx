import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subValue?: string;
  icon: LucideIcon;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  status?: "healthy" | "warning" | "danger" | "neutral";
  onClick?: () => void;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subValue,
  icon: Icon,
  trend,
  status = "neutral",
  onClick,
}) => {
  const statusColors = {
    healthy: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    warning: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    danger: "text-rose-400 bg-rose-500/10 border-rose-500/20",
    neutral: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  };

  return (
    <div
      onClick={onClick}
      className={`rounded-xl border border-sentinel-800 bg-sentinel-900/90 p-5 backdrop-blur-sm transition-all duration-150 ${
        onClick ? "cursor-pointer hover:border-sentinel-700 hover:bg-sentinel-850" : ""
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
          {title}
        </span>
        <div className={`rounded-lg border p-2 ${statusColors[status]}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-mono text-2xl font-bold tracking-tight text-white">
          {value}
        </span>
        {subValue && (
          <span className="text-xs text-slate-400 font-normal">
            {subValue}
          </span>
        )}
      </div>

      {trend && (
        <div className="mt-2.5 flex items-center text-xs">
          <span
            className={`font-medium ${
              trend.isPositive ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {trend.value}
          </span>
          <span className="ml-1.5 text-slate-500">vs target threshold</span>
        </div>
      )}
    </div>
  );
};

