import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionButtonProps {
  label: string;
  icon?: LucideIcon;
  onClick: () => void;
}

function ActionButton({ label, icon: Icon, onClick }: ActionButtonProps) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition"
    >
      {Icon && <Icon className="h-4 w-4" />}
      {label}
    </button>
  );
}

interface PageHeaderProps {
  title: string;
  description?: string;
  action?: ActionButtonProps;
  className?: string;
}

export function PageHeader({ title, description, action, className }: PageHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between mb-6", className)}>
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        {description && <p className="text-muted-foreground mt-1">{description}</p>}
      </div>
      {action && <ActionButton {...action} />}
    </div>
  );
}
