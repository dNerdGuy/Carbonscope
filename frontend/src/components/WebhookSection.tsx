"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listWebhooks,
  createWebhook,
  deleteWebhook,
  toggleWebhook,
  type WebhookConfig,
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
                        }
                      }}
                      className={`text-xs ${wh.active ? "text-green-400" : "text-[var(--muted)]"} hover:underline`}
                    >
                      {wh.active ? "Active" : "Disabled"}
                    </button>
                  </td>
                  <td className="py-2">
                    <button
                      onClick={() => setDeleteWhTarget(wh.id)}
                      className="text-xs text-[var(--danger)] hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
