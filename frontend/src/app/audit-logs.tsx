import {
  createFileRoute,
  useNavigate,
  useLocation,
} from "@tanstack/react-router";
import { Suspense, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAuditLogs, AuditLogEntry, ApiError } from "@/lib/api";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { DataTable, type Column } from "@/components/DataTable";
import { TableSkeleton } from "@/components/Skeleton";
import Breadcrumbs from "@/components/Breadcrumbs";
import { StatusMessage } from "@/components/StatusMessage";

const PAGE_SIZE = 25;

export const Route = createFileRoute("/audit-logs")({
  component: AuditLogsPage,
});

function AuditLogsPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
          <TableSkeleton />
        </div>
      }
    >
      <AuditLogsPageInner />
    </Suspense>
  );
}

function AuditLogsPageInner() {
  useDocumentTitle("Audit Logs");
  const { user, loading: authLoading } = useRequireAuth();
  const { search } = useLocation();
  const navigate = useNavigate();
  const [offset, setOffset] = useState(() => {
    const p = new URLSearchParams(search).get("page");
    const num = Number(p);
    return p && Number.isFinite(num) && num > 0
      ? (Math.max(1, Math.floor(num)) - 1) * PAGE_SIZE
      : 0;
  });

  const logsQuery = useQuery<{ items: AuditLogEntry[]; total: number }>({
    queryKey: ["audit-logs", user?.company_id, offset],
    queryFn: () => listAuditLogs({ limit: PAGE_SIZE, offset }),
    enabled: !!user && !authLoading,
  });

  const logs = logsQuery.data?.items ?? [];
  const total = logsQuery.data?.total ?? 0;
  const loading = logsQuery.isLoading;
  const error =
    logsQuery.error instanceof ApiError
      ? logsQuery.error.message
      : logsQuery.error
        ? "Failed to load audit logs"
        : "";

  // Sync page to URL
  useEffect(() => {
    const page = Math.floor(offset / PAGE_SIZE) + 1;
    const params = new URLSearchParams();
    if (page > 1) params.set("page", String(page));
    const qs = params.toString();
    navigate({
      to: `/audit-logs${qs ? `?${qs}` : ""}`,
      replace: true,
      resetScroll: false,
    });
  }, [offset, navigate]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const columns: Column<AuditLogEntry>[] = [
    {
      key: "created_at",
      header: "Timestamp",
      render: (entry) => (
        <span className="whitespace-nowrap text-[var(--muted)]">
          {new Date(entry.created_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: "action",
      header: "Action",
      render: (entry) => (
        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--primary)]/10 text-[var(--primary)]">
          {entry.action}
        </span>
      ),
    },
    {
      key: "resource_type",
      header: "Resource",
      render: (entry) => (
        <>
          <span className="text-[var(--muted)]">{entry.resource_type}</span>
          {entry.resource_id && (
            <span className="text-xs text-[var(--muted)] ml-1">
              #{entry.resource_id.slice(0, 8)}
            </span>
          )}
        </>
      ),
    },
    {
      key: "details",
      header: "Details",
      render: (entry) => (
        <span className="text-[var(--muted)] max-w-xs truncate block">
          {entry.details || "—"}
        </span>
      ),
    },
  ];

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Audit Log" },
        ]}
      />
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">Audit Log</h1>

      {error && <StatusMessage message={error} variant="error" />}

      <div className="card">
        <DataTable<AuditLogEntry>
          columns={columns}
          data={logs}
          loading={loading}
          emptyMessage="No audit log entries found."
          caption="Audit log entries"
          total={total}
          limit={PAGE_SIZE}
          offset={offset}
          onPageChange={setOffset}
        />
      </div>
    </div>
  );
}
