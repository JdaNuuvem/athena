type AlertType = "success" | "error" | "info";

const styles: Record<AlertType, string> = {
  success: "border-emerald-800 bg-emerald-900/20 text-emerald-400",
  error: "border-red-800 bg-red-900/20 text-red-400",
  info: "border-indigo-800 bg-indigo-900/20 text-indigo-400",
};

interface AlertProps {
  message: string | null;
  type?: AlertType;
}

export default function Alert({ message, type = "info" }: AlertProps) {
  if (!message) return null;
  return (
    <div className={`border rounded-lg p-3 text-xs ${styles[type]}`}>
      {message}
    </div>
  );
}
