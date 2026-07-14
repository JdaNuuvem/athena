import type { StatusBadgeVariant } from "@/lib/types/ui";
import { STATUS_BADGE_VARIANTS } from "@/lib/types/ui";

interface StatusBadgeProps {
  label: string;
  variant: StatusBadgeVariant;
}

export default function StatusBadge({ label, variant }: StatusBadgeProps) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium ${STATUS_BADGE_VARIANTS[variant]}`}>
      {label}
    </span>
  );
}
