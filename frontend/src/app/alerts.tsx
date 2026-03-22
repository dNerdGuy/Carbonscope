import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useMemo, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import { useToast } from "@/components/Toast";
import { useEventSource } from "@/hooks/useEventSource";
import Breadcrumbs from "@/components/Breadcrumbs";
import {
  listAlerts,
  acknowledgeAlert,
  triggerAlertCheck,
  type AlertOut,
  type PaginatedResponse,
} from "@/lib/api";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-l-4 border-red-500 bg-red-500/10",
  warning: "border-l-4 border-yellow-500 bg-yellow-500/10",
  info: "border-l-4 border-blue-500 bg-blue-500/10",
};

const SEVERITY_BADGES: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400",
  warning: "bg-yellow-500/20 text-yellow-400",
  info: "bg-blue-500/20 text-blue-400",
};

export const Route = createFileRoute("/alerts")({ component: AlertsPage });

function AlertsPage() {
  useDocumentTitle("Alerts");
  const { user, loading } = useRequireAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [checking, setChecking] = useState(false);

  const alertsQuery = useQuery<PaginatedResponse<AlertOut>>({
    queryKey: ["alerts", user?.company_id, unreadOnly],
    queryFn: () => listAlerts({ unread_only: unreadOnly, limit: 50 }),
    enabled: !!user && !loading,
  });

  const data = alertsQuery.data ?? null;

  useEffect(() => {
    if (alertsQuery.error) {
      setError(
        alertsQuery.error instanceof Error
          ? alertsQuery.error.message
          : "Failed to load alerts",
      );
    }
  }, [alertsQuery.error]);

  // Auto-refresh when backend pushes SSE events
  const invalidateAlerts = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
    [queryClient],
  );
  const sseHandlers = useMemo(
    () => ({
      "alert.created": invalidateAlerts,
      "alert.acknowledged": invalidateAlerts,
    }),
    [invalidateAlerts],
  );
  useEventSource(sseHandlers, !!user);

  async function handleAcknowledge(id: string) {
    try {
      await acknowledgeAlert(id);
      await alertsQuery.refetch();
      toast("Alert acknowledged", "success");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to acknowledge");
    }
  }

  async function handleCheck() {
    setChecking(true);
    try {
      await triggerAlertCheck();
      await alertsQuery.refetch();
      toast("Alert check completed", "success");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Check failed");
    } finally {
      setChecking(false);
    }
  }

  if (loading || (alertsQuery.isLoading && !error)) {
    return <PageSkeleton />;
  }

  if (error && !data) {
    return (
      <div className="p-8">
        <StatusMessage message={error} variant="error" />
      </div>
    );
  }

  const alerts = data?.items ?? [];

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-6">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Alerts" },
        ]}
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Alerts</h1>
          <p className="text-[var(--muted)]">
            Automated monitoring for emission changes and data quality.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            className="btn-primary text-sm px-4 py-2"
            onClick={handleCheck}
            disabled={checking}
          >
            {checking ? "Checking..." : "Run Check"}
          </button>
        </div>
      </div>

      {error && <StatusMessage message={error} variant="error" />}

      {/* Filter */}
      <div className="flex gap-3 items-center">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="accent-[var(--primary)]"
          />
          Unread only
        </label>
        <span className="text-sm text-[var(--muted)]">
          {data?.total ?? 0} alert{data?.total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Alert list */}
      {alerts.length === 0 ? (
        <div className="card p-12 text-center text-[var(--muted)]">
          <p className="text-4xl mb-3">🔔</p>
          <p>No alerts to display.</p>
          <p className="text-sm mt-1">
            Click &ldquo;Run Check&rdquo; to scan for emission changes.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`card p-4 ${SEVERITY_STYLES[alert.severity] ?? ""} ${
                alert.is_read ? "opacity-60" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        SEVERITY_BADGES[alert.severity] ?? ""
                      }`}
                    >
                      {alert.severity}
                    </span>
                    <span className="text-xs text-[var(--muted)]">
                      {alert.alert_type.replace(/_/g, " ")}
                    </span>
                    {alert.is_read && (
                      <span className="text-xs text-[var(--muted)]">
                        ✓ acknowledged
                      </span>
                    )}
                  </div>
                  <h3 className="font-semibold">{alert.title}</h3>
                  <p className="text-sm text-[var(--muted)] mt-1">
                    {alert.message}
                  </p>
                  <p className="text-xs text-[var(--muted)] mt-2">
                    {new Date(alert.created_at).toLocaleString()}
                  </p>
                </div>
                {!alert.is_read && (
                  <button
                    className="text-xs px-3 py-1.5 rounded-md bg-[var(--card-border)] hover:bg-[var(--primary)] hover:text-black transition-colors shrink-0"
                    onClick={() => handleAcknowledge(alert.id)}
                  >
                    Acknowledge
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
