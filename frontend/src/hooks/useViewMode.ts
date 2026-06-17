import { useCallback, useEffect, useState } from "react";

export type ViewMode = "blocks" | "list";

/**
 * Modo de visualização (blocos | lista) persistido em localStorage por chave.
 * A leitura do localStorage acontece após a montagem (evita mismatch de SSR).
 */
export function useViewMode(key: string, initial: ViewMode = "blocks") {
  const [mode, setMode] = useState<ViewMode>(initial);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(key);
      if (saved === "blocks" || saved === "list") {
        setMode(saved);
      }
    } catch {
      /* localStorage indisponível */
    }
  }, [key]);

  const update = useCallback(
    (next: ViewMode) => {
      setMode(next);
      try {
        window.localStorage.setItem(key, next);
      } catch {
        /* ignore */
      }
    },
    [key]
  );

  return [mode, update] as const;
}
