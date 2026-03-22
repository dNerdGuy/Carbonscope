"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
  deleteAccount,
  type Company,
  type User,
} from "@/lib/api";
import { FormField } from "@/components/FormField";
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import Breadcrumbs from "@/components/Breadcrumbs";
import WebhookSection from "@/components/WebhookSection";
import ConfirmDialog from "@/components/ConfirmDialog";
import { useAuth } from "@/lib/auth-context";

import { INDUSTRIES, industryLabel } from "@/lib/constants";

export default function SettingsPage() {
  useDocumentTitle("Settings");
  const { user, loading } = useRequireAuth();
  const { logout } = useAuth();
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // User profile state
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

  // Delete account state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteErr, setDeleteErr] = useState("");

  const settingsQuery = useQuery<[User, Company]>({
    queryKey: ["settings", user?.company_id],
    queryFn: () => Promise.all([getProfile(), getCompany()]),
    enabled: !!user && !loading,
  });

  const mfaStatusQuery = useQuery<{ enabled: boolean }>({
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
  const mfaEnabled = mfaStatusQuery.data?.enabled ?? false;

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);
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
    }
  }

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileErr("");
    setProfileMsg("");
    setProfileSaving(true);
    try {
      await updateProfile({ full_name: fullName, email });
      await settingsQuery.refetch();
      setProfileMsg("Profile updated.");
    } catch (err: unknown) {
      setProfileErr(err instanceof Error ? err.message : "Update failed");
    } finally {
      setProfileSaving(false);
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

  async function handleDeleteAccount() {
    setDeleteErr("");
    setDeleting(true);
    try {
      await deleteAccount();
      await logout();
      router.replace("/login");
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
    <div className="max-w-2xl mx-auto p-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Settings" },
        ]}
      />
      <h1 className="text-2xl font-bold mb-2">Settings</h1>
      <p className="text-[var(--muted)] mb-8">
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
      <form onSubmit={handlePasswordChange} className="card space-y-4 mb-8">
        <h2 className="text-lg font-bold">Change Password</h2>
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
      <div className="card space-y-3 mt-8">
        <h2 className="text-lg font-bold">Two-Factor Authentication</h2>
        <p className="text-sm text-[var(--muted)]">
          {mfaEnabled
            ? "Two-factor authentication is enabled on your account."
            : "Protect your account with time-based one-time passwords (TOTP)."}
        </p>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
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
          <a href="/mfa" className="btn-secondary text-sm">
            {mfaEnabled ? "Manage 2FA" : "Enable 2FA"}
          </a>
        </div>
      </div>

      <WebhookSection />

      {/* Danger Zone */}
      <div
        className="card mt-8 space-y-3"
        style={{ borderColor: "var(--error, #ef4444)" }}
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
          className="rounded-md border px-4 py-2 text-sm font-medium transition-colors"
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
