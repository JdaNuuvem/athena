"use client";

import LeadsPanel from "./_components/LeadsPanel";

export default function Page() {
  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Leads</h1>
        <p className="text-xs text-neutral-500 mt-1">Capte e gerencie novos leads</p>
      </div>
      <LeadsPanel />
    </div>
  );
}
