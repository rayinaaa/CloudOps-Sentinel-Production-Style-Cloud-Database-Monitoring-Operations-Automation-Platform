import React from "react";

export type BadgeVariant =
  | "CRITICAL"
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | "OPEN"
  | "ACKNOWLEDGED"
  | "RESOLVED"
  | "HEALTHY"
  | "WARNING"
  | "COMPLETED"
  | "ACTIVE"
  | "SUSPENDED"
  | "PENDING"
  | "FREE"
  | "STARTER"
  | "PRO"
  | "ENTERPRISE"
  | "DEFAULT";

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
  size?: "sm" | "md";
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, { bg: string; text: string; border: string; dotColor: string }> = {
  CRITICAL: {
    bg: "bg-red-500/10",
    text: "text-red-400",
    border: "border-red-500/20",
    dotColor: "bg-red-500",
  },
  HIGH: {
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/20",
    dotColor: "bg-amber-500",
  },
  MEDIUM: {
    bg: "bg-sky-500/10",
    text: "text-sky-400",
    border: "border-sky-500/20",
    dotColor: "bg-sky-500",
  },
  LOW: {
    bg: "bg-slate-500/10",
    text: "text-slate-400",
    border: "border-slate-500/20",
    dotColor: "bg-slate-400",
  },
  OPEN: {
    bg: "bg-rose-500/10",
    text: "text-rose-400",
    border: "border-rose-500/20",
    dotColor: "bg-rose-500",
  },
  ACKNOWLEDGED: {
    bg: "bg-amber-500/10",
    text: "text-amber-300",
    border: "border-amber-500/20",
    dotColor: "bg-amber-400",
  },
  RESOLVED: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
    dotColor: "bg-emerald-500",
  },
  HEALTHY: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
    dotColor: "bg-emerald-500",
  },
  WARNING: {
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/20",
    dotColor: "bg-amber-500",
  },
  COMPLETED: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
    dotColor: "bg-emerald-500",
  },
  ACTIVE: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
    dotColor: "bg-emerald-500",
  },
  SUSPENDED: {
    bg: "bg-slate-500/10",
    text: "text-slate-400",
    border: "border-slate-500/20",
    dotColor: "bg-slate-400",
  },
  PENDING: {
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/20",
    dotColor: "bg-amber-400",
  },
  ENTERPRISE: {
    bg: "bg-indigo-500/15",
    text: "text-indigo-300",
    border: "border-indigo-500/30",
    dotColor: "bg-indigo-400",
  },
  PRO: {
    bg: "bg-cyan-500/10",
    text: "text-cyan-300",
    border: "border-cyan-500/20",
    dotColor: "bg-cyan-400",
  },
  STARTER: {
    bg: "bg-teal-500/10",
    text: "text-teal-300",
    border: "border-teal-500/20",
    dotColor: "bg-teal-400",
  },
  FREE: {
    bg: "bg-slate-500/10",
    text: "text-slate-400",
    border: "border-slate-500/20",
    dotColor: "bg-slate-400",
  },
  DEFAULT: {
    bg: "bg-slate-800",
    text: "text-slate-300",
    border: "border-slate-700",
    dotColor: "bg-slate-400",
  },
};

export const Badge: React.FC<BadgeProps> = ({
  label,
  variant,
  size = "sm",
  dot = true,
}) => {
  const normKey = (variant || label).toUpperCase() as BadgeVariant;
  const style = variantStyles[normKey] || variantStyles.DEFAULT;

  const sizeClass = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-mono tracking-wide ${style.bg} ${style.text} ${style.border} ${sizeClass}`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${style.dotColor}`} />}
      {label}
    </span>
  );
};

