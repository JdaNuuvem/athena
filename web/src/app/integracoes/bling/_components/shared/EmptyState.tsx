interface EmptyStateProps {
  icon: string;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-3xl mb-3">{icon}</span>
      <p className="text-xs text-neutral-200 font-medium mb-1">{title}</p>
      <p className="text-xs text-neutral-500 max-w-xs mb-4">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
