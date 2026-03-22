
import { useCallback, useEffect, useState } from "react";
import {
  listWebhooks,
  createWebhook,
  deleteWebhook,
  toggleWebhook,
  listDeliveries,
  retryDelivery,
  type WebhookConfig,
  type WebhookDelivery,
} from "@/lib/api";
import ConfirmDialog from "@/components/ConfirmDialog";
import { StatusMessage } from "@/components/StatusMessage";

const ALL_EVENTS = [
  "report.created",
  "data.uploaded",
  "estimate.completed",
  "supply_chain.link_created",
  "supply_chain.link_verified",
  "confidence.improved",
];

export default function WebhookSection() {
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [whUrl, setWhUrl] = useState("");
  const [whEvents, setWhEvents] = useState<string[]>(["report.created"]);
  const [addingWh, setAddingWh] = useState(false);
  const [deleteWhTarget, setDeleteWhTarget] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [selectedWh, setSelectedWh] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [newSecret, setNewSecret] = useState<string | null>(null);

  useEffect(() => {
    listWebhooks()
      .then((res) => setWebhooks(res.items))
      .catch(() => setError("Failed to load webhooks"));
  }, []);

  const copyToClipboard = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Clipboard not available
    }
  }, []);

  const loadDeliveries = useCallback(async (webhookId: string) => {
    setLoadingDeliveries(true);
    setError("");
    try {
      const res = await listDeliveries(webhookId, { limit: 20 });
      setDeliveries(res.items);
      setSelectedWh(webhookId);
    } catch {
      setError("Failed to load delivery logs");
    } finally {
      setLoadingDeliveries(false);
    }
  }, []);

  const handleRetry = useCallback(
    async (webhookId: string, deliveryId: string) => {
      setRetryingId(deliveryId);
      setError("");
      try {
        const updated = await retryDelivery(webhookId, deliveryId);
        setDeliveries((prev) =>
          prev.map((d) => (d.id === deliveryId ? updated : d)),
        );
      } catch {
        setError("Failed to retry delivery");
      } finally {
        setRetryingId(null);
      }
    },
    [],
  );

  return (
    <div className="mt-10">
      <h2 className="text-xl font-bold mb-2">Webhooks</h2>
      <p className="text-[var(--muted)] text-sm mb-4">
        Receive HTTP callbacks when events occur in your account.
      </p>

      {error && <StatusMessage message={error} variant="error" />}

      <div className="card space-y-4 mb-4">
        <div>
          <label htmlFor="webhook-url" className="label">
            Endpoint URL
          </label>
          <input
            id="webhook-url"
            type="url"
            className="input"
            value={whUrl}
            onChange={(e) => setWhUrl(e.target.value)}
            placeholder="https://example.com/webhook"
          />
        </div>
        <div>
          <label id="events-label" className="label">
            Events
          </label>
          <div
            className="flex flex-wrap gap-2 mt-1"
            role="group"
            aria-labelledby="events-label"
          >
            {ALL_EVENTS.map((evt) => (
              <label
                key={evt}
                className="flex items-center gap-1 text-sm text-[var(--muted)]"
              >
                <input
                  type="checkbox"
                  checked={whEvents.includes(evt)}
                  onChange={(e) =>
                    setWhEvents(
                      e.target.checked
                        ? [...whEvents, evt]
                        : whEvents.filter((x) => x !== evt),
                    )
                  }
                />
                {evt}
              </label>
            ))}
          </div>
        </div>
        <button
          className="btn-primary"
          disabled={addingWh || !whUrl || whEvents.length === 0}
          onClick={async () => {
            setAddingWh(true);
            setError("");
            try {
              const wh = await createWebhook({
                url: whUrl,
                event_types: whEvents,
              });
              if ((wh as unknown as Record<string, unknown>).secret) {
                setNewSecret(
                  (wh as unknown as Record<string, unknown>).secret as string,
                );
              }
              setWebhooks((prev) => [...prev, wh]);
              setWhUrl("");
              setWhEvents(["report.created"]);
            } catch {
              setError("Failed to create webhook");
            } finally {
              setAddingWh(false);
            }
          }}
        >
          {addingWh ? "Adding..." : "Add Webhook"}
        </button>
      </div>

      {newSecret && (
        <div
          className="card mb-4 p-4"
          style={{
            borderColor: "var(--warning)",
            background: "color-mix(in srgb, var(--warning) 10%, transparent)",
          }}
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <p
                className="font-semibold text-sm"
                style={{ color: "var(--warning)" }}
              >
                Webhook Signing Secret
              </p>
              <p className="text-xs text-[var(--muted)] mt-1">
                Copy this secret now — it won&apos;t be shown again.
              </p>
              <code className="mt-2 block rounded bg-[var(--background)] px-3 py-2 text-xs font-mono break-all">
                {newSecret}
              </code>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                className="text-xs px-3 py-1 rounded bg-[var(--card-border)] hover:bg-[var(--primary)] hover:text-black transition-colors"
                onClick={() => {
                  navigator.clipboard.writeText(newSecret).catch(() => {});
                }}
              >
                Copy
              </button>
              <button
                type="button"
                className="text-xs px-3 py-1 rounded text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
                onClick={() => setNewSecret(null)}
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {webhooks.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--muted)] text-left border-b border-[var(--card-border)]">
                <th className="pb-2">URL</th>
                <th className="pb-2">Events</th>
                <th className="pb-2">Status</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map((wh) => (
                <tr
                  key={wh.id}
                  className="border-b border-[var(--card-border)]"
                >
                  <td className="py-2 font-mono text-xs truncate max-w-[200px]">
                    <span className="flex items-center gap-1">
                      {wh.url}
                      <button
                        type="button"
                        aria-label="Copy URL"
                        onClick={() => copyToClipboard(wh.url, wh.id)}
                        className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors shrink-0"
                      >
                        {copiedId === wh.id ? (
                          <span className="text-[var(--primary)] text-xs font-medium">
                            Copied!
                          </span>
                        ) : (
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <rect x="9" y="9" width="13" height="13" rx="2" />
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                          </svg>
                        )}
                      </button>
                    </span>
                  </td>
                  <td className="py-2 text-xs">{wh.event_types.join(", ")}</td>
                  <td className="py-2">
                    <button
                      onClick={async () => {
                        const btn =
                          document.activeElement as HTMLButtonElement | null;
                        if (btn) btn.disabled = true;
                        try {
                          const updated = await toggleWebhook(
                            wh.id,
                            !wh.active,
                          );
                          setWebhooks((prev) =>
                            prev.map((w) => (w.id === wh.id ? updated : w)),
                          );
                        } catch {
                          setError("Failed to toggle webhook");
                        } finally {
                          if (btn) btn.disabled = false;
                        }
                      }}
                      className={`text-xs hover:underline`}
                      style={{
                        color: wh.active ? "var(--success)" : "var(--muted)",
                      }}
                    >
                      {wh.active ? "Active" : "Disabled"}
                    </button>
                  </td>
                  <td className="py-2">
                    <span className="flex items-center gap-2">
                      <button
                        onClick={() => loadDeliveries(wh.id)}
                        className="text-xs text-[var(--primary)] hover:underline"
                      >
                        Deliveries
                      </button>
                      <button
                        onClick={() => setDeleteWhTarget(wh.id)}
                        className="text-xs text-[var(--danger)] hover:underline"
                      >
                        Delete
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedWh && (
        <div className="card mt-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">
              Delivery Log
              {loadingDeliveries && (
                <span className="text-[var(--muted)] ml-2">Loading...</span>
              )}
            </h3>
            <button
              onClick={() => {
                setSelectedWh(null);
                setDeliveries([]);
              }}
              className="text-xs text-[var(--muted)] hover:underline"
            >
              Close
            </button>
          </div>
          {deliveries.length === 0 && !loadingDeliveries ? (
            <p className="text-sm text-[var(--muted)]">No deliveries yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[var(--muted)] text-left border-b border-[var(--card-border)]">
                    <th className="pb-1">Event</th>
                    <th className="pb-1">Status</th>
                    <th className="pb-1">Code</th>
                    <th className="pb-1">Latency</th>
                    <th className="pb-1">Time</th>
                    <th className="pb-1"></th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.map((d) => (
                    <tr
                      key={d.id}
                      className="border-b border-[var(--card-border)]"
                    >
                      <td className="py-1">{d.event_type}</td>
                      <td className="py-1">
                        <span
                          style={{
                            color: d.success
                              ? "var(--success)"
                              : "var(--danger)",
                          }}
                        >
                          {d.success ? "OK" : d.error || "Failed"}
                        </span>
                      </td>
                      <td className="py-1">{d.status_code ?? "—"}</td>
                      <td className="py-1">
                        {d.duration_ms != null ? `${d.duration_ms}ms` : "—"}
                      </td>
                      <td className="py-1">
                        {new Date(d.created_at).toLocaleString()}
                      </td>
                      <td className="py-1">
                        {!d.success && (
                          <button
                            disabled={retryingId === d.id}
                            onClick={() => handleRetry(selectedWh, d.id)}
                            className="text-[var(--primary)] hover:underline disabled:opacity-50"
                          >
                            {retryingId === d.id ? "Retrying..." : "Retry"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={!!deleteWhTarget}
        title="Delete Webhook"
        message="Are you sure you want to delete this webhook?"
        confirmLabel="Delete"
        variant="danger"
        onConfirm={async () => {
          try {
            if (deleteWhTarget) {
              await deleteWebhook(deleteWhTarget);
              setWebhooks((prev) =>
                prev.filter((w) => w.id !== deleteWhTarget),
              );
            }
          } catch {
            setError("Failed to delete webhook");
          } finally {
            setDeleteWhTarget(null);
          }
        }}
        onCancel={() => setDeleteWhTarget(null)}
      />
    </div>
  );
}
