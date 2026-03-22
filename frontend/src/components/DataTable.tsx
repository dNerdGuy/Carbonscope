
import { memo, type ReactNode } from "react";
import { SkeletonRows } from "@/components/Skeleton";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyMessage?: string;
  caption?: string;
  total?: number;
  limit?: number;
  offset?: number;
  onPageChange?: (offset: number) => void;
}

function DataTableInner<T extends object>({
  columns,
  data,
  loading = false,
  emptyMessage = "No data found.",
  caption,
  total,
  limit,
  offset = 0,
  onPageChange,
}: DataTableProps<T>) {
  const hasPagination = total != null && limit != null && onPageChange != null;
  const totalPages = hasPagination ? Math.ceil(total / limit) : 0;
  const currentPage = hasPagination ? Math.floor(offset / limit) + 1 : 1;

  return (
    <div className="overflow-x-auto">
      {/* Desktop table */}
      <table
        className="hidden sm:table min-w-full divide-y divide-[var(--card-border)]"
        role="table"
        aria-label={caption ?? "Data table"}
      >
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-[var(--card)]">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--muted)]"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--card-border)] bg-[var(--background)]">
          {loading ? (
            <SkeletonRows rows={3} columns={columns.length} />
          ) : data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-[var(--muted)]"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, i) => (
              <tr
                key={
                  ((row as Record<string, unknown>).id as string) ?? `row-${i}`
                }
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className="whitespace-nowrap px-4 py-3 text-sm text-[var(--foreground)]"
                  >
                    {col.render
                      ? col.render(row)
                      : String((row as Record<string, unknown>)[col.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Mobile card layout */}
      <div
        className="sm:hidden space-y-3"
        role="list"
        aria-label={caption ?? "Data list"}
      >
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4 animate-pulse"
              >
                <div className="h-4 bg-[var(--muted)]/20 rounded w-3/4 mb-2" />
                <div className="h-3 bg-[var(--muted)]/20 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : data.length === 0 ? (
          <p className="px-4 py-8 text-center text-[var(--muted)]">
            {emptyMessage}
          </p>
        ) : (
          data.map((row, i) => (
            <div
              key={((row as Record<string, unknown>).id as string) ?? i}
              role="listitem"
              className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4 space-y-2"
            >
              {columns.map((col) => (
                <div
                  key={col.key}
                  className="flex justify-between gap-2 text-sm"
                >
                  <span className="font-medium text-[var(--muted)] shrink-0">
                    {col.header}
                  </span>
                  <span className="text-[var(--foreground)] text-right">
                    {col.render
                      ? col.render(row)
                      : String((row as Record<string, unknown>)[col.key] ?? "")}
                  </span>
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      {hasPagination && totalPages > 1 && (
        <nav
          aria-label="Table pagination"
          className="flex items-center justify-between border-t border-[var(--card-border)] px-4 py-3"
        >
          <span className="text-sm text-[var(--muted)]" aria-live="polite">
            Page {currentPage} of {totalPages} ({total} items)
          </span>
          <div className="flex gap-2">
            <button
              disabled={currentPage <= 1}
              onClick={() => onPageChange(offset - limit)}
              className="rounded border px-3 py-1 text-sm disabled:opacity-40"
              aria-label={`Go to previous page, page ${currentPage - 1}`}
            >
              Previous
            </button>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => onPageChange(offset + limit)}
              className="rounded border px-3 py-1 text-sm disabled:opacity-40"
              aria-label={`Go to next page, page ${currentPage + 1}`}
            >
              Next
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}

export const DataTable = memo(DataTableInner) as typeof DataTableInner;
