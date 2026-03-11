"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  getCompany,
  updateCompany,
  listWebhooks,
  createWebhook,
  deleteWebhook,
  type Company,
  type WebhookConfig,
} from "@/lib/api";

const INDUSTRIES = [
  "energy",
  "manufacturing",
  "technology",
  "transportation",
  "retail",
  "healthcare",
  "finance",
  "construction",
  "agriculture",
  "other",
];

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [company, setCompany] = useState<Company | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [region, setRegion] = useState("");
  const [employeeCount, setEmployeeCount] = useState("");
  const [revenueUsd, setRevenueUsd] = useState("");

  // Webhook state
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [whUrl, setWhUrl] = useState("");
  const [whEvents, setWhEvents] = useState<string[]>(["report.created"]);
  const [addingWh, setAddingWh] = useState(false);

  const ALL_EVENTS = [
    "report.created",
    "data.uploaded",
    "estimate.completed",
    "supply_chain.link_created",
    "supply_chain.link_verified",
    "confidence.improved",
  ];

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user) {
      getCompany().then((c) => {
        setCompany(c);
        setName(c.name);
        setIndustry(c.industry);
        setRegion(c.region);
        setEmployeeCount(c.employee_count?.toString() ?? "");
        setRevenueUsd(c.revenue_usd?.toString() ?? "");
      });
      listWebhooks()
        .then(setWebhooks)
        .catch(() => {});
    }
  }, [user, loading, router]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const updated = await updateCompany({
        name,
        industry,
        region,
        employee_count: employeeCount ? parseInt(employeeCount) : null,
        revenue_usd: revenueUsd ? parseFloat(revenueUsd) : null,
      });
      setCompany(updated);
      setSuccess("Company profile updated.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading || !company) {
    return <div className="p-8 text-[var(--muted)]">Loading settings...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-2">Settings</h1>
      <p className="text-[var(--muted)] mb-8">Manage your company profile.</p>

      <form onSubmit={handleSave} className="card space-y-4">
        {error && (
          <div className="text-sm text-[var(--danger)] bg-[var(--danger)]/10 rounded-md p-3">
            {error}
          </div>
        )}
        {success && (
          <div className="text-sm text-[var(--primary)] bg-[var(--primary)]/10 rounded-md p-3">
            {success}
          </div>
        )}

        <div>
          <label className="label">Company Name</label>
          <input
            type="text"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label">Industry</label>
          <select
            className="input"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          >
            {INDUSTRIES.map((i) => (
              <option key={i} value={i}>
                {i.charAt(0).toUpperCase() + i.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Region</label>
          <input
            type="text"
            className="input"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="e.g. US, EU, GB"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Employee Count</label>
            <input
              type="number"
              className="input"
              value={employeeCount}
              onChange={(e) => setEmployeeCount(e.target.value)}
              min={0}
            />
          </div>
          <div>
            <label className="label">Annual Revenue (USD)</label>
            <input
              type="number"
              className="input"
              value={revenueUsd}
              onChange={(e) => setRevenueUsd(e.target.value)}
              min={0}
              step="any"
            />
          </div>
        </div>

        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </form>

      {/* Webhooks */}
      <div className="mt-10">
        <h2 className="text-xl font-bold mb-2">Webhooks</h2>
        <p className="text-[var(--muted)] text-sm mb-4">
          Receive HTTP callbacks when events occur in your account.
        </p>

        <div className="card space-y-4 mb-4">
          <div>
            <label className="label">Endpoint URL</label>
            <input
              type="url"
              className="input"
              value={whUrl}
              onChange={(e) => setWhUrl(e.target.value)}
              placeholder="https://example.com/webhook"
            />
          </div>
          <div>
            <label className="label">Events</label>
            <div className="flex flex-wrap gap-2 mt-1">
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
              try {
                const wh = await createWebhook({
                  url: whUrl,
                  event_types: whEvents,
                });
                setWebhooks([...webhooks, wh]);
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
                      {wh.url}
                    </td>
                    <td className="py-2 text-xs">
                      {wh.event_types.join(", ")}
                    </td>
                    <td className="py-2">
                      <span
                        className={`text-xs ${
                          wh.active ? "text-green-400" : "text-[var(--muted)]"
                        }`}
                      >
                        {wh.active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="py-2">
                      <button
                        onClick={async () => {
                          await deleteWebhook(wh.id);
                          setWebhooks(webhooks.filter((w) => w.id !== wh.id));
                        }}
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
      </div>
    </div>
  );
}
