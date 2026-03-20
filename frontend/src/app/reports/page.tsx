"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { listReports, exportReports, type EmissionReport } from "@/lib/api";
import { CardSkeleton } from "@/components/Skeleton";

const PAGE_SIZE = 10;

export default function ReportsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Initialise state from URL params
  const [offset, setOffset] = useState(() => {
    const p = searchParams.get("page");
    return p ? (Math.max(1, Number(p)) - 1) * PAGE_SIZE : 0;
  });
  const [sortBy, setSortBy] = useState<
    "created_at" | "year" | "total" | "confidence"
  >(() => {
    const s = searchParams.get("sort");
    return (["created_at", "year", "total", "confidence"] as const).includes(
      s as never,
    )
      ? (s as "created_at" | "year" | "total" | "confidence")
      : "created_at";
  });
  const [order, setOrder] = useState<"asc" | "desc">(() =>
    searchParams.get("order") === "asc" ? "asc" : "desc",
  );
  const [yearFilter, setYearFilter] = useState<string>(
    () => searchParams.get("year") ?? "",
  );
  const [debouncedYear, setDebouncedYear] = useState(yearFilter);
  const yearTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const [actionError, setActionError] = useState("");
  const [exporting, setExporting] = useState(false);

  // Debounce year filter input (400ms)
  useEffect(() => {
    clearTimeout(yearTimerRef.current);
    yearTimerRef.current = setTimeout(() => setDebouncedYear(yearFilter), 400);
    return () => clearTimeout(yearTimerRef.current);
  }, [yearFilter]);

  // Sync state changes back to URL
  useEffect(() => {
    const params = new URLSearchParams();
    const page = Math.floor(offset / PAGE_SIZE) + 1;
    if (page > 1) params.set("page", String(page));
    if (sortBy !== "created_at") params.set("sort", sortBy);
    if (order !== "desc") params.set("order", order);
    if (debouncedYear) params.set("year", debouncedYear);
    const qs = params.toString();
    router.replace(`/reports${qs ? `?${qs}` : ""}`, { scroll: false });
  }, [offset, sortBy, order, debouncedYear, router]);

  const reportsQuery = useQuery({
    queryKey: ["reports", offset, sortBy, order, debouncedYear],
    queryFn: () =>
      listReports({
        limit: PAGE_SIZE,
        offset,
        sortBy,
        order,
        year: debouncedYear ? Number(debouncedYear) : undefined,
      }),
    enabled: !!user && !loading,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  const reports: EmissionReport[] = reportsQuery.data?.items ?? [];
  const total = reportsQuery.data?.total ?? 0;
  const error =
    reportsQuery.error instanceof Error ? reportsQuery.error.message : "";
  const fetching = reportsQuery.isLoading || reportsQuery.isFetching;

  if (!loading && !user) {
    return null;
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const handleExport = async (format: "csv" | "json") => {
    setActionError("");
    setExporting(true);
    try {
      const blob = await exportReports(
        format,
        yearFilter ? Number(yearFilter) : undefined,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `reports.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  if (loading || (fetching && reports.length === 0)) {
    return (
      <div className="max-w-5xl mx-auto p-8 space-y-3">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Emission Reports</h1>
        <button
          onClick={() => router.push("/upload")}
          className="btn-primary text-sm"
        >
          + New Estimate
        </button>
      </div>

      {/* Filters & controls */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <label htmlFor="year-filter" className="sr-only">
          Filter by year
        </label>
        <input
          id="year-filter"
          type="number"
          placeholder="Filter by year"
          value={yearFilter}
          onChange={(e) => {
            setYearFilter(e.target.value);
            setOffset(0);
          }}
          className="input w-36 text-sm"
          min={2000}
          max={2030}
        />
        <label htmlFor="sort-by" className="sr-only">
          Sort by
        </label>
        <select
          id="sort-by"
          value={sortBy}
          onChange={(e) => {
            setSortBy(e.target.value as typeof sortBy);
            setOffset(0);
          }}
          className="input text-sm"
        >
          <option value="created_at">Date</option>
          <option value="year">Year</option>
          <option value="total">Total Emissions</option>
          <option value="confidence">Confidence</option>
        </select>
        <button
          onClick={() => setOrder(order === "desc" ? "asc" : "desc")}
          className="btn-secondary text-sm"
          aria-label={`Sort ${order === "desc" ? "ascending" : "descending"}`}
          title={`Sort ${order === "desc" ? "ascending" : "descending"}`}
        >
          {order === "desc" ? "↓" : "↑"}
        </button>
        <div className="ml-auto flex gap-2">
          <button
            onClick={() => handleExport("csv")}
            className="btn-secondary text-sm"
            disabled={exporting}
          >
            {exporting ? "Exporting..." : "Export CSV"}
          </button>
          <button
            onClick={() => handleExport("json")}
            className="btn-secondary text-sm"
            disabled={exporting}
          >
            {exporting ? "Exporting..." : "Export JSON"}
          </button>
        </div>
      </div>

      {error && <div className="text-[var(--danger)] mb-4">{error}</div>}
      {actionError && (
        <div className="text-[var(--danger)] mb-4">{actionError}</div>
      )}

      {reports.length === 0 && !fetching ? (
        <div className="card text-center py-12">
          <p className="text-[var(--muted)] mb-4">
            No reports yet. Upload data to generate your first emission
            estimate.
          </p>
          <button
            onClick={() => router.push("/upload")}
            className="btn-primary"
          >
            Upload Data
          </button>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {reports.map((r) => (
              <Link
                key={r.id}
                href={`/reports/${r.id}`}
                className="card block hover:border-[var(--primary)] transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-lg">{r.year}</span>
                    <span className="text-[var(--muted)] ml-3 text-sm">
                      {new Date(r.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="text-right">
                    <p className="font-bold">
                      {r.total.toLocaleString(undefined, {
                        maximumFractionDigits: 1,
                      })}{" "}
                      tCO₂e
                    </p>
                    <p className="text-sm text-[var(--muted)]">
                      {(r.confidence * 100).toFixed(0)}% confidence
                    </p>
                  </div>
                </div>
                <div className="flex gap-6 mt-2 text-sm">
                  <span style={{ color: "var(--scope1)" }}>
                    S1:{" "}
                    {r.scope1.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </span>
                  <span style={{ color: "var(--scope2)" }}>
                    S2:{" "}
                    {r.scope2.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </span>
                  <span style={{ color: "var(--scope3)" }}>
                    S3:{" "}
                    {r.scope3.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </span>
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <p className="text-sm text-[var(--muted)]">
                Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of{" "}
                {total}
              </p>
              <div className="flex gap-2">
                <button
                  disabled={currentPage <= 1}
                  onClick={() => setOffset(offset - PAGE_SIZE)}
                  className="btn-secondary text-sm disabled:opacity-40"
                >
                  ← Previous
                </button>
                <span className="text-sm leading-8">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  disabled={currentPage >= totalPages}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  className="btn-secondary text-sm disabled:opacity-40"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
