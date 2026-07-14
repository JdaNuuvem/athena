interface LoadingStateProps {
  message?: string;
}

export default function LoadingState({ message = "Carregando..." }: LoadingStateProps) {
  return <p className="text-neutral-500 text-sm">{message}</p>;
}
