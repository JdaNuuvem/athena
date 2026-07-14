interface PageHeaderProps {
  title: string;
  subtitle: string;
}

export default function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <div>
      <h1 className="text-lg font-bold text-neutral-100">{title}</h1>
      <p className="text-xs text-neutral-500 mt-1">{subtitle}</p>
    </div>
  );
}
