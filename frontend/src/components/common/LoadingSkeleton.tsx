import React from "react";

export const LoadingSkeleton: React.FC<{ rows?: number; height?: string }> = ({
  rows = 4,
  height = "h-12",
}) => {
  return (
    <div className="w-full space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, idx) => (
        <div
          key={idx}
          className={`w-full rounded-lg bg-sentinel-800/60 ${height}`}
        />
      ))}
    </div>
  );
};

export const CardSkeleton: React.FC = () => {
  return (
    <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/60 p-5 animate-pulse">
      <div className="flex justify-between items-center">
        <div className="h-4 w-24 bg-sentinel-800 rounded" />
        <div className="h-8 w-8 bg-sentinel-800 rounded-lg" />
      </div>
      <div className="mt-4 h-7 w-32 bg-sentinel-800 rounded" />
      <div className="mt-2 h-3 w-20 bg-sentinel-800/80 rounded" />
    </div>
  );
};

