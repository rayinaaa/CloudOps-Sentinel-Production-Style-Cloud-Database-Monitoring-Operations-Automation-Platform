import React from "react";
import { Inbox, LucideIcon } from "lucide-react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: LucideIcon;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = "No records found",
  description = "No operational events matching the current filter criteria.",
  icon: Icon = Inbox,
  actionText,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-sentinel-800 bg-sentinel-900/40 p-10 text-center">
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-850 p-3 text-slate-400">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="mt-3 text-sm font-semibold text-slate-200">{title}</h3>
      <p className="mt-1 max-w-sm text-xs text-slate-400">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="mt-4 rounded-lg bg-sky-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-sky-500 transition-colors"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};

