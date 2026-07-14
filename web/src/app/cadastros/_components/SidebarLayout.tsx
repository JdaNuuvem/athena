"use client";

import { useState, ReactNode } from "react";

interface SubItem { key: string; label: string; children?: SubItem[]; }

export default function SidebarLayout({ subItems, renderContent }: { subItems: SubItem[]; renderContent: (activeKey: string) => ReactNode }) {
  const [active, setActive] = useState(subItems[0]?.key ?? "");
  return (
    <div className="flex gap-0 min-h-[60vh]">
      <nav className="w-48 shrink-0 bg-neutral-800/50 border-r border-neutral-700/50 rounded-l-lg">
        <div className="p-2 space-y-0.5">
          {subItems.map((item) => (
            <div key={item.key}>
              <button onClick={() => setActive(item.key)}
                className={`w-full text-left px-3 py-1.5 rounded text-xs transition-colors ${active === item.key ? "bg-indigo-600/20 text-indigo-300 font-medium" : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-700/50"} ${item.children ? "font-semibold" : ""}`}>{item.label}</button>
              {item.children && (
                <div className="ml-3 space-y-0.5 mt-0.5">
                  {item.children.map((child) => (
                    <button key={child.key} onClick={() => setActive(child.key)}
                      className={`w-full text-left px-3 py-1 rounded text-[11px] transition-colors ${active === child.key ? "bg-indigo-600/20 text-indigo-300" : "text-neutral-500 hover:text-neutral-300"}`}>{child.label}</button>
                  ))}</div>
              )}</div>
          ))}</div>
      </nav>
      <div className="flex-1 bg-neutral-800 border border-neutral-700 border-l-0 rounded-r-lg p-4 min-w-0">{renderContent(active)}</div>
    </div>
  );
}
