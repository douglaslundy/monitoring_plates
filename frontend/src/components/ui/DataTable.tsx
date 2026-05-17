"use client";

import { useState } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  render?: (value: unknown, row: T) => React.ReactNode;
  className?: string;
  sortable?: boolean;
}

interface DataTableProps<T extends { id: string | number }> {
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  emptyMessage?: string;
}

type SortDir = "asc" | "desc";

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />;
  return dir === "asc" ? (
    <ChevronUp className="h-3.5 w-3.5" />
  ) : (
    <ChevronDown className="h-3.5 w-3.5" />
  );
}

export function DataTable<T extends { id: string | number }>({
  data,
  columns,
  loading = false,
  emptyMessage = "Nenhum registro encontrado",
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const sorted = sortKey
    ? [...data].sort((a, b) => {
        const av = (a as Record<string, unknown>)[sortKey];
        const bv = (b as Record<string, unknown>)[sortKey];
        const as = String(av ?? "").toLowerCase();
        const bs = String(bv ?? "").toLowerCase();
        const cmp = as < bs ? -1 : as > bs ? 1 : 0;
        return sortDir === "asc" ? cmp : -cmp;
      })
    : data;

  if (loading) {
    return (
      <div className="w-full border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-left font-medium text-muted-foreground",
                    col.className
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b">
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3">
                    <div className="h-4 bg-gray-100 rounded animate-pulse" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="w-full border rounded-lg p-10 text-center text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden sm:block w-full border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={cn(
                      "px-4 py-3 text-left font-medium text-muted-foreground whitespace-nowrap",
                      col.sortable && "cursor-pointer select-none hover:text-foreground",
                      col.className
                    )}
                    onClick={col.sortable ? () => handleSort(col.key) : undefined}
                    aria-sort={
                      col.sortable && sortKey === col.key
                        ? sortDir === "asc"
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.header}
                      {col.sortable && (
                        <SortIcon
                          active={sortKey === col.key}
                          dir={sortDir}
                        />
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr
                  key={row.id}
                  className="border-b hover:bg-gray-50 transition-colors"
                >
                  {columns.map((col) => {
                    const value = (row as Record<string, unknown>)[col.key];
                    return (
                      <td
                        key={col.key}
                        className={cn(
                          "px-4 py-3 whitespace-nowrap",
                          col.className
                        )}
                      >
                        {col.render ? col.render(value, row) : String(value ?? "")}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile cards */}
      <div className="sm:hidden space-y-3">
        {sorted.map((row) => {
          const [first, ...rest] = columns;
          const firstValue = (row as Record<string, unknown>)[first.key];
          return (
            <div key={row.id} className="border rounded-xl bg-white shadow-sm p-4">
              <div className="mb-3">
                {first.render
                  ? first.render(firstValue, row)
                  : <p className="font-medium">{String(firstValue ?? "")}</p>}
              </div>
              <dl className="space-y-1.5">
                {rest.map((col) => {
                  const value = (row as Record<string, unknown>)[col.key];
                  return (
                    <div key={col.key} className="flex items-center justify-between gap-2 text-sm">
                      <dt className="text-muted-foreground shrink-0">{col.header}</dt>
                      <dd className="text-right">
                        {col.render ? col.render(value, row) : String(value ?? "")}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </div>
          );
        })}
      </div>
    </>
  );
}
