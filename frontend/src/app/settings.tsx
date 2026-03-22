import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import {
  getCompany,
  updateCompany,
  getProfile,
  updateProfile,
  changePassword,
  getMFAStatus,
  setupMFA,
  verifyMFA,
  disableMFA,
  deleteAccount,
  type Company,
  type User,
  type MFASetup,
} from "@/lib/api";
import { FormField } from "@/components/FormField";
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import Breadcrumbs from "@/components/Breadcrumbs";
import WebhookSection from "@/components/WebhookSection";
import ConfirmDialog from "@/components/ConfirmDialog";
import { useAuth } from "@/lib/auth-context";
import { QRCodeSVG } from "qrcode.react";

import { INDUSTRIES, industryLabel } from "@/lib/constants";

export const Route = createFileRoute("/settings")({ component: SettingsPage });

function SettingsPage() {
  useDocumentTitle("Settings");
  const { user, loading } = useRequireAuth();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [anySaving, setAnySaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // User profile state
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");
  const [profileErr, setProfileErr] = useState("");

  // Password change state
  const [showPasswordChange, setShowPasswordChange] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState("");
  const [pwErr, setPwErr] = useState("");

  // MFA state
  const [mfaSetup, setMfaSetup] = useState<MFASetup | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [mfaError, setMfaError] = useState("");
  const [mfaSuccess, setMfaSuccess] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [region, setRegion] = useState("");
  const [employeeCount, setEmployeeCount] = useState("");
  const [revenueUsd, setRevenueUsd] = useState("");

  // Delete account state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteErr, setDeleteErr] = useState("");

  const settingsQuery = useQuery<[User, Company]>({
    queryKey: ["settings", user?.company_id],
    queryFn: () => Promise.all([getProfile(), getCompany()]),
    enabled: !!user && !loading,
  });

  const mfaStatusQuery = useQuery<{ mfa_enabled: boolean }>({
    queryKey: ["mfa-status", user?.id],
    queryFn: getMFAStatus,
    enabled: !!user && !loading,
  });

  // Populate form fields when data loads
  useEffect(() => {
    if (settingsQuery.data) {
      const [p, c] = settingsQuery.data;
      setFullName(p.full_name);
      setEmail(p.email);
      setName(c.name);
      setIndustry(c.industry);
      setRegion(c.region);
      setEmployeeCount(c.employee_count?.toString() ?? "");
      setRevenueUsd(c.revenue_usd?.toString() ?? "");
    }
  }, [settingsQuery.data]);

  const company = settingsQuery.data?.[1] ?? null;
  const profile = settingsQuery.data?.[0] ?? null;
  const mfaEnabled = mfaStatusQuery.data?.mfa_enabled ?? false;

  async function handleMFASetup() {
    setMfaError("");
    setMfaSuccess("");
    try {
      const s = await setupMFA();
      setMfaSetup(s);
    } catch (e: unknown) {
      setMfaError(e instanceof Error ? e.message : "MFA setup failed");
    }
  }

  async function handleMFAVerify() {
    setMfaError("");
    try {
      await verifyMFA(totpCode);
      setMfaSuccess("MFA enabled successfully!");
      setMfaSetup(null);
      setTotpCode("");
      await mfaStatusQuery.refetch();
    } catch (e: unknown) {
      setMfaError(e instanceof Error ? e.message : "Invalid TOTP code");
    }
  }

  async function handleMFADisable() {
    setMfaError("");
    try {
      await disableMFA(disableCode);
      setMfaSuccess("MFA disabled.");
      setDisableCode("");
      await mfaStatusQuery.refetch();
    } catch (e: unknown) {
      setMfaError(e instanceof Error ? e.message : "Failed to disable MFA");
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (anySaving) return;
    setError("");
    setSuccess("");
    setSaving(true);
    setAnySaving(true);
    try {
      await updateCompany({
        name,
        industry,
        region,
        employee_count: employeeCount ? parseInt(employeeCount) : null,
        revenue_usd: revenueUsd ? parseFloat(revenueUsd) : null,
      });
      await settingsQuery.refetch();
      setSuccess("Company profile updated.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
      setAnySaving(false);
    }
  }

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    if (anySaving) return;
    setProfileErr("");
    setProfileMsg("");
    setProfileSaving(true);
    setAnySaving(true);
    try {
      await updateProfile({ full_name: fullName, email });
      await settingsQuery.refetch();
      setProfileMsg("Profile updated.");
    } catch (err: unknown) {
      setProfileErr(err instanceof Error ? err.message : "Update failed");
    } finally {
      setProfileSaving(false);
      setAnySaving(false);
    }
  }

  function validatePassword(pw: string): string | null {
    if (pw.length < 8) return "Password must be at least 8 characters.";
    if (!/[A-Z]/.test(pw)) return "Password must include an uppercase letter.";
    if (!/\d/.test(pw)) return "Password must include a digit.";
    return null;
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setPwErr("");
    setPwMsg("");
    const validationErr = validatePassword(newPw);
    if (validationErr) {
      setPwErr(validationErr);
      return;
    }
    if (anySaving) return;
    setPwSaving(true);
    setAnySaving(true);
    try {
      await changePassword(currentPw, newPw);
      setPwMsg("Password changed successfully.");
      setCurrentPw("");
      setNewPw("");
    } catch (err: unknown) {
      setPwErr(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setPwSaving(false);
      setAnySaving(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleteErr("");
    setDeleting(true);
    try {
      await deleteAccount();
      await logout();
      navigate({ to: "/login", replace: true });
    } catch (err: unknown) {
      setDeleteErr(
        err instanceof Error ? err.message : "Failed to delete account",
      );
      setDeleting(false);
    }
  }

  if (loading || !company) {
    return <PageSkeleton />;
  }

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Settings" },
        ]}
      />
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">Settings</h1>
      <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
        Manage your profile and company.
      </p>

      {/* User Profile */}
      {profile && (
        <form onSubmit={handleProfileSave} className="card space-y-4 mb-8">
          <h2 className="text-lg font-bold">Your Profile</h2>
          {profileErr && <StatusMessage message={profileErr} variant="error" />}
          {profileMsg && (
            <StatusMessage message={profileMsg} variant="success" />
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
      <div className="card mb-8">
        <button
          type="button"
          className="flex w-full items-center justify-between text-left"
          onClick={() => {
            setShowPasswordChange((v) => !v);
            setPwErr("");
            setPwMsg("");
          }}
          aria-expanded={showPasswordChange}
        >
          <h2 className="text-lg font-bold">Change Password</h2>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className={`transition-transform duration-200 ${showPasswordChange ? "rotate-180" : ""}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
        {showPasswordChange && (
          <form onSubmit={handlePasswordChange} className="mt-4 space-y-4">
            {pwErr && <StatusMessage message={pwErr} variant="error" />}
            {pwMsg && <StatusMessage message={pwMsg} variant="success" />}
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
        )}
      </div>

      {/* Company Profile */}
      <form onSubmit={handleSave} className="card space-y-4">
        <h2 className="text-lg font-bold">Company Profile</h2>
        {error && <StatusMessage message={error} variant="error" />}
        {success && <StatusMessage message={success} variant="success" />}

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
                {industryLabel(i)}
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

      {/* Two-Factor Authentication */}
      <div className="card space-y-4 mt-8">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Two-Factor Authentication</h2>
            <p className="text-sm text-[var(--muted)] mt-0.5">
              {mfaEnabled
                ? "TOTP two-factor authentication is active on your account."
                : "Add a second layer of security with a TOTP authenticator app."}
            </p>
          </div>
          <span
            className={`shrink-0 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
              mfaEnabled
                ? "bg-green-500/15 text-green-400"
                : "bg-gray-500/15 text-gray-400"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${mfaEnabled ? "bg-green-400" : "bg-gray-400"}`}
            />
            {mfaEnabled ? "Enabled" : "Disabled"}
          </span>
        </div>

        {mfaError && <StatusMessage message={mfaError} variant="error" />}
        {mfaSuccess && <StatusMessage message={mfaSuccess} variant="success" />}

        {/* Enable flow */}
        {!mfaEnabled && !mfaSetup && (
          <button onClick={handleMFASetup} className="btn-primary">
            Enable 2FA
          </button>
        )}

        {/* Setup: show secret + backup codes + verify input */}
        {mfaSetup && (
          <div className="space-y-4">
            <div>
              <p className="text-sm text-[var(--muted)] mb-4">
                Scan this QR code with your authenticator app, or enter the
                secret manually:
              </p>
              <div className="flex justify-center mb-4 bg-white p-4 rounded-xl border border-[var(--card-border)] w-fit mx-auto">
                <QRCodeSVG
                  value={mfaSetup.provisioning_uri}
                  size={180}
                  level="M"
                  marginSize={0}
                />
              </div>
              <code className="block rounded bg-[var(--background)] p-3 text-center text-sm text-[var(--primary)] font-mono tracking-wider break-all">
                {mfaSetup.secret}
              </code>
            </div>
            <div>
              <p className="text-sm text-[var(--muted)] mb-1">
                Backup codes — save these somewhere safe:
              </p>
              <div className="grid grid-cols-2 gap-1">
                {mfaSetup.backup_codes.map((code, i) => (
                  <code
                    key={i}
                    className="rounded bg-[var(--background)] px-2 py-1 text-sm font-mono"
                  >
                    {code}
                  </code>
                ))}
              </div>
            </div>
            <div className="flex gap-3">
              <input
                className="input"
                placeholder="Enter 6-digit TOTP code"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                maxLength={6}
                inputMode="numeric"
                pattern="[0-9]*"
                aria-label="TOTP verification code"
              />
              <button
                onClick={handleMFAVerify}
                className="btn-primary shrink-0"
              >
                Verify &amp; Enable
              </button>
            </div>
          </div>
        )}

        {/* Disable flow */}
        {mfaEnabled && (
          <div
            className="rounded-lg border p-4 space-y-3"
            style={{
              borderColor: "var(--error, #ef4444)",
              background:
                "color-mix(in srgb, var(--error, #ef4444) 8%, transparent)",
            }}
          >
            <p
              className="text-sm font-medium"
              style={{ color: "var(--error, #ef4444)" }}
            >
              Disable 2FA
            </p>
            <p className="text-sm text-[var(--muted)]">
              Enter your current TOTP code to disable multi-factor
              authentication.
            </p>
            <div className="flex gap-3">
              <input
                className="input"
                placeholder="6-digit TOTP code"
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                maxLength={6}
                inputMode="numeric"
                pattern="[0-9]*"
                aria-label="TOTP code to disable MFA"
              />
              <button
                onClick={handleMFADisable}
                className="btn-danger shrink-0"
              >
                Disable
              </button>
            </div>
          </div>
        )}
      </div>

      <WebhookSection />

      {/* Danger Zone */}
      <div
        className="card mt-8 space-y-3"
        style={{
          borderColor: "color-mix(in srgb, var(--danger) 50%, transparent)",
          backgroundColor: "color-mix(in srgb, var(--danger) 5%, transparent)",
        }}
      >
        <h2
          className="text-lg font-bold"
          style={{ color: "var(--error, #ef4444)" }}
        >
          Danger Zone
        </h2>
        <p className="text-sm text-[var(--muted)]">
          Permanently delete your account and all associated data. This action
          cannot be undone.
        </p>
        {deleteErr && <StatusMessage message={deleteErr} variant="error" />}
        <button
          type="button"
          className="rounded-md border px-4 py-2 text-sm font-medium"
          style={{
            borderColor: "var(--error, #ef4444)",
            color: "var(--error, #ef4444)",
          }}
          onClick={() => setShowDeleteConfirm(true)}
          disabled={deleting}
        >
          Delete My Account
        </button>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete Account"
        message="This will permanently delete your account, company data, and all emission reports. This action cannot be undone."
        confirmLabel={deleting ? "Deleting..." : "Delete Account"}
        onConfirm={handleDeleteAccount}
        onCancel={() => setShowDeleteConfirm(false)}
        variant="danger"
      />
    </div>
  );
}
