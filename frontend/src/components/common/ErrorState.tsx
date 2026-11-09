import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = "Failed to load telemetry",
  message = "A network error or database connectivity failure occurred while fetching live operational metrics.",
  onRetry,
}) => {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-red-500/20 bg-red-950/10 p-8 text-center backdrop-blur-sm">
      <div className="rounded-full bg-red-500/10 p-3 text-red-400">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h3 className="mt-3 text-base font-semibold text-red-200">{title}</h3>
      <p className="mt-1 max-w-md text-xs text-slate-400 font-mono">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/15 px-3.5 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/25 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry Probe
        </button>
      )}
    </div>
  );
};

