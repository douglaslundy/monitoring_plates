import { LayoutGrid, List } from "lucide-react";
import type { ViewMode } from "@/hooks/useViewMode";

/** Alterna entre visualização em blocos (cards) e em lista (linhas compactas). */
export function ViewToggle({
  mode,
  onChange,
}: {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-lg border" role="group" aria-label="Modo de visualização">
      <button
        type="button"
        onClick={() => onChange("blocks")}
        aria-pressed={mode === "blocks"}
        title="Visualizar em blocos"
        className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-sm transition-colors ${
          mode === "blocks" ? "bg-primary text-primary-foreground" : "bg-white hover:bg-gray-50"
        }`}
      >
        <LayoutGrid className="h-4 w-4" aria-hidden="true" /> Blocos
      </button>
      <button
        type="button"
        onClick={() => onChange("list")}
        aria-pressed={mode === "list"}
        title="Visualizar em lista"
        className={`inline-flex items-center gap-1 border-l px-2.5 py-1.5 text-sm transition-colors ${
          mode === "list" ? "bg-primary text-primary-foreground" : "bg-white hover:bg-gray-50"
        }`}
      >
        <List className="h-4 w-4" aria-hidden="true" /> Lista
      </button>
    </div>
  );
}
