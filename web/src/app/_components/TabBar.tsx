import type { TabOption } from "@/lib/types/ui";

interface TabBarProps {
  tabs: TabOption[];
  active: string;
  onChange: (key: string) => void;
}

export default function TabBar({ tabs, active, onChange }: TabBarProps) {
  return (
    <div className="flex gap-1 bg-neutral-800 rounded-lg p-1 w-fit">
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={`px-4 py-1.5 text-xs rounded-md transition-colors ${
            active === t.key ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
