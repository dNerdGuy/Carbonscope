"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  getCompany,
  updateCompany,
  getProfile,
  updateProfile,
  changePassword,
  listWebhooks,
  createWebhook,
  deleteWebhook,
  toggleWebhook,
  type Company,
  type User,
  type WebhookConfig,
} from "@/lib/api";
import ConfirmDialog from "@/components/ConfirmDialog";
import { FormField } from "@/components/FormField";
import { PageSkeleton } from "@/components/Skeleton";

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

  // User profile state
  const [profile, setProfile] = useState<User | null>(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");
  const [profileErr, setProfileErr] = useState("");

  // Password change state
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState("");
  const [pwErr, setPwErr] = useState("");

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
  const [deleteWhTarget, setDeleteWhTarget] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Fallback ignored — clipboard not available
    }
  }, []);

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
      getProfile()
        .then((p) => {
          setProfile(p);
          setFullName(p.full_name);
          setEmail(p.email);
        })
        .catch(() => {});
      getCompany().then((c) => {
        setCompany(c);
        setName(c.name);
        setIndustry(c.industry);
        setRegion(c.region);
        setEmployeeCount(c.employee_count?.toString() ?? "");
        setRevenueUsd(c.revenue_usd?.toString() ?? "");
      });
      listWebhooks()
        .then((res) => setWebhooks(res.items))
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

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileErr("");
    setProfileMsg("");
    setProfileSaving(true);
    try {
      const updated = await updateProfile({ full_name: fullName, email });
      setProfile(updated);
      setProfileMsg("Profile updated.");
    } catch (err: unknown) {
      setProfileErr(err instanceof Error ? err.message : "Update failed");
    } finally {
      setProfileSaving(false);
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setPwErr("");
    setPwMsg("");
    setPwSaving(true);
    try {
      await changePassword(currentPw, newPw);
      setPwMsg("Password changed successfully.");
      setCurrentPw("");
      setNewPw("");
    } catch (err: unknown) {
      setPwErr(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setPwSaving(false);
    }
  }

  if (loading || !company) {
    return <PageSkeleton />;
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-2">Settings</h1>
      <p className="text-[var(--muted)] mb-8">
        Manage your profile and company.
      </p>

      {/* User Profile */}
      {profile && (
        <form onSubmit={handleProfileSave} className="card space-y-4 mb-8">
          <h2 className="text-lg font-bold">Your Profile</h2>
          {profileErr && (
            <div className="text-sm text-[var(--danger)] bg-[var(--danger)]/10 rounded-md p-3">
              {profileErr}
            </div>
          )}
          {profileMsg && (
            <div className="text-sm text-[var(--primary)] bg-[var(--primary)]/10 rounded-md p-3">
              {profileMsg}
            </div>
          )}
          <FormField
            label="Full Name"
            type="text"
            className="input"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            minLength={1}
            maxLength={255}
          />
          <FormField
            label="Email"
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button
            type="submit"
            className="btn-primary"
            disabled={profileSaving}
          >
            {profileSaving ? "Saving..." : "Update Profile"}
          </button>
        </form>
      )}

      {/* Password Change */}
      <form onSubmit={handlePasswordChange} className="card space-y-4 mb-8">
        <h2 className="text-lg font-bold">Change Password</h2>
        {pwErr && (
          <div className="text-sm text-[var(--danger)] bg-[var(--danger)]/10 rounded-md p-3">
            {pwErr}
          </div>
        )}
        {pwMsg && (
          <div className="text-sm text-[var(--primary)] bg-[var(--primary)]/10 rounded-md p-3">
            {pwMsg}
          </div>
        )}
        <FormField
          label="Current Password"
          type="password"
          className="input"
          value={currentPw}
          onChange={(e) => setCurrentPw(e.target.value)}
          required
        />
        <FormField
          label="New Password"
          type="password"
          className="input"
          value={newPw}
          onChange={(e) => setNewPw(e.target.value)}
          required
          minLength={8}
          maxLength={128}
          hint="Min 8 characters, must include an uppercase letter and a digit."
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={pwSaving || !currentPw || !newPw}
        >
          {pwSaving ? "Changing..." : "Change Password"}
        </button>
      </form>

      {/* Company Profile */}
      <form onSubmit={handleSave} className="card space-y-4">
        <h2 className="text-lg font-bold">Company Profile</h2>
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

        <FormField
          label="Company Name"
          type="text"
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <FormField label="Industry">
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
        </FormField>
        <FormField
          label="Region"
          type="text"
          className="input"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          placeholder="e.g. US, EU, GB"
        />
        <div className="grid grid-cols-2 gap-4">
          <FormField
            label="Employee Count"
            type="number"
            className="input"
            value={employeeCount}
            onChange={(e) => setEmployeeCount(e.target.value)}
            min={0}
          />
          <FormField
            label="Annual Revenue (USD)"
            type="number"
            className="input"
            value={revenueUsd}
            onChange={(e) => setRevenueUsd(e.target.value)}
            min={0}
            step="any"
          />
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
                    <td className="py-2 text-xs">
                      {wh.event_types.join(", ")}
                    </td>
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
      </div>

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
