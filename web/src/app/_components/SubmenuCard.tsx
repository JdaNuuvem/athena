import Link from "next/link";
import type { SubmenuItem } from "@/lib/types/ui";

interface SubmenuCardProps {
  item: SubmenuItem;
}

export default function SubmenuCard({ item }: SubmenuCardProps) {
  return (
    <Link
      href={item.href}
      className={`${item.color} hover:opacity-90 text-white rounded-lg p-4 transition-opacity`}
    >
      <p className="text-sm font-semibold">{item.label}</p>
      <p className="text-[10px] opacity-80 mt-1">Gerenciar {item.label.toLowerCase()}</p>
    </Link>
  );
}
