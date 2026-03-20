"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import {
  getCompany,
  updateCompany,
  getProfile,
  updateProfile,
  changePassword,
  type Company,
  type User,
} from "@/lib/api";
import { FormField } from "@/components/FormField";
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import WebhookSection from "@/components/WebhookSection";

import { INDUSTRIES, industryLabel } from "@/lib/constants";

export default function SettingsPage() {
  useDocumentTitle("Settings");
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

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user) {
      Promise.all([getProfile(), getCompany()])
        .then(([p, c]) => {
          setProfile(p);
          setFullName(p.full_name);
          setEmail(p.email);
          setCompany(c);
          setName(c.name);
          setIndustry(c.industry);
          setRegion(c.region);
          setEmployeeCount(c.employee_count?.toString() ?? "");
          setRevenueUsd(c.revenue_usd?.toString() ?? "");
        })
        .catch(() => setProfileErr("Failed to load settings"));
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

      <WebhookSection />
    </div>
  );
}
