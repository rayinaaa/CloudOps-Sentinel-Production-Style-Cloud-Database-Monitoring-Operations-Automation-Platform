import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { PageId } from "../../types";

interface LayoutProps {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
  pageTitle: string;
  pageSubtitle: string;
  lastUpdated?: string;
  isRefreshing?: boolean;
  onRefresh: () => void;
  openIncidentCount?: number;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({
  activePage,
  onNavigate,
  pageTitle,
  pageSubtitle,
  lastUpdated,
  isRefreshing,
  onRefresh,
  openIncidentCount = 0,
  children,
}) => {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-sentinel-950 text-slate-100">
      {/* Sidebar Navigation */}
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        openIncidentCount={openIncidentCount}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar
          pageTitle={pageTitle}
          pageSubtitle={pageSubtitle}
          lastUpdated={lastUpdated}
          isRefreshing={isRefreshing}
          onRefresh={onRefresh}
          openIncidentCount={openIncidentCount}
        />
        <main className="flex-1 overflow-y-auto p-6 bg-sentinel-950">
          <div className="max-w-7xl mx-auto space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

