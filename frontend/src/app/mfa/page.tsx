"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { PageSkeleton } from "@/components/Skeleton";
import {
  getMFAStatus,
  setupMFA,
  verifyMFA,
  disableMFA,
  type MFAStatus,
  type MFASetup,
} from "@/lib/api";

export default function MFAPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [setup, setSetup] = useState<MFASetup | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const statusQuery = useQuery<MFAStatus>({
    queryKey: ["mfa-status"],
    queryFn: getMFAStatus,
    enabled: !!user && !loading,
  });

  const status = statusQuery.data ?? null;

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  const handleSetup = async () => {
    setError("");
    setSuccess("");
    try {
      const s = await setupMFA();
      setSetup(s);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "MFA setup failed");
    }
  };

  const handleVerify = async () => {
    setError("");
    try {
      await verifyMFA(totpCode);
      setSuccess("MFA enabled successfully!");
      setSetup(null);
      setTotpCode("");
      statusQuery.refetch();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid TOTP code");
    }
  };

  const handleDisable = async () => {
    setError("");
    try {
      await disableMFA(disableCode);
      setSuccess("MFA disabled.");
      setDisableCode("");
      statusQuery.refetch();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to disable MFA");
    }
  };

  if (loading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="mb-8 text-3xl font-bold">Multi-Factor Authentication</h1>

      {error && (
        <p className="mb-4 rounded bg-red-900/30 p-3 text-red-400">{error}</p>
      )}
      {success && (
        <p className="mb-4 rounded bg-emerald-900/30 p-3 text-emerald-400">
          {success}
        </p>
      )}

      {status && (
        <div className="mb-6 rounded-lg border border-gray-700 bg-gray-800 p-6">
          <div className="flex items-center gap-3">
            <div
              className={`h-3 w-3 rounded-full ${
                status.mfa_enabled ? "bg-emerald-500" : "bg-gray-500"
              }`}
            />
            <p className="text-lg font-medium">
              MFA is {status.mfa_enabled ? "enabled" : "disabled"}
            </p>
          </div>
        </div>
      )}

      {/* Setup flow */}
      {status && !status.mfa_enabled && !setup && (
        <button
          onClick={handleSetup}
          className="rounded-lg bg-emerald-600 px-6 py-3 text-white hover:bg-emerald-700"
        >
          Enable MFA
        </button>
      )}

      {setup && (
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-6">
          <h2 className="mb-4 text-xl font-semibold">Setup TOTP</h2>

          <div className="mb-4">
            <p className="mb-1 text-sm text-gray-400">
              Scan this QR code with your authenticator app, or enter the secret
              manually:
            </p>
            <code className="block rounded bg-gray-900 p-3 text-sm text-emerald-400 break-all">
              {setup.secret}
            </code>
          </div>

          <div className="mb-4">
            <p className="mb-1 text-sm text-gray-400">
              Backup codes (save securely):
            </p>
            <div className="grid grid-cols-2 gap-1">
              {setup.backup_codes.map((code, i) => (
                <code key={i} className="rounded bg-gray-900 px-2 py-1 text-sm">
                  {code}
                </code>
              ))}
            </div>
          </div>

          <div className="flex gap-3">
            <input
              className="rounded bg-gray-700 px-3 py-2 text-white"
              placeholder="Enter TOTP code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              maxLength={6}
            />
            <button
              onClick={handleVerify}
              className="rounded bg-emerald-600 px-4 py-2 text-white"
            >
              Verify & Enable
            </button>
          </div>
        </div>
      )}

      {/* Disable MFA */}
      {status?.mfa_enabled && (
        <div className="mt-6 rounded-lg border border-red-800 bg-red-900/10 p-6">
          <h2 className="mb-2 text-lg font-semibold text-red-400">
            Disable MFA
          </h2>
          <p className="mb-4 text-sm text-gray-400">
            Enter your current TOTP code to disable multi-factor authentication.
          </p>
          <div className="flex gap-3">
            <input
              className="rounded bg-gray-700 px-3 py-2 text-white"
              placeholder="TOTP code"
              value={disableCode}
              onChange={(e) => setDisableCode(e.target.value)}
              maxLength={6}
            />
            <button
              onClick={handleDisable}
              className="rounded bg-red-600 px-4 py-2 text-white"
            >
              Disable
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
