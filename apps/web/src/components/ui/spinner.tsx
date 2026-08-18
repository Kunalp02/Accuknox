import { cn } from "../../lib/cn";

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-5 w-5 animate-spin rounded-full border-2 border-gray-200 border-t-primary",
        className
      )}
    />
  );
}

export function PageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <Spinner className="h-8 w-8" />
    </div>
  );
}
