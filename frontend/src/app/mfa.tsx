import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { getMFAStatus, setupMFA, verifyMFA, disableMFA } from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
import { ErrorCard } from "@/components/ErrorCard";

export const Route = createFileRoute("/mfa")({ component: MFAPage });

function MFAPage() {
  useDocumentTitle("Multi-Factor Authentication");
  const { user, loading } = useRequireAuth();
  const queryClient = useQueryClient();

  const [setupData, setSetupData] = useState<{
    provisioning_uri: string;
    backup_codes: string[];
  } | null>(null);
  const [verifyCode, setVerifyCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const {
    data: mfaStatus,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["mfa-status"],
    queryFn: getMFAStatus,
    enabled: !!user,
  });

  const setupMutation = useMutation({
    mutationFn: setupMFA,
    onSuccess: (data) => {
      setSetupData({
        provisioning_uri: data.provisioning_uri,
        backup_codes: data.backup_codes,
      });
    },
  });

  const verifyMutation = useMutation({
    mutationFn: (code: string) => verifyMFA(code),
    onSuccess: () => {
      setSetupData(null);
      setVerifyCode("");
      setStatusMsg("MFA enabled successfully.");
      queryClient.invalidateQueries({ queryKey: ["mfa-status"] });
    },
    onError: () => setStatusMsg("Verification failed. Please try again."),
  });

  const disableMutation = useMutation({
    mutationFn: (code: string) => disableMFA(code),
    onSuccess: () => {
      setDisableCode("");
      setStatusMsg("MFA disabled.");
      queryClient.invalidateQueries({ queryKey: ["mfa-status"] });
    },
    onError: () => setStatusMsg("Disable failed. Please check your code."),
  });

  if (loading || isLoading) return <PageSkeleton />;
  if (error) return <ErrorCard message={(error as Error).message} />;

  const enabled = mfaStatus?.mfa_enabled ?? false;

  return (
    <div className="max-w-lg mx-auto space-y-6 p-6">
      <h1 className="text-2xl font-bold">Multi-Factor Authentication</h1>

      <div className="card space-y-2">
        <p className="font-semibold">
          {enabled ? "MFA is enabled" : "MFA is disabled"}
        </p>

        {!enabled && !setupData && (
          <button
            className="btn-primary"
            onClick={() => setupMutation.mutate()}
            disabled={setupMutation.isPending}
          >
            Enable MFA
          </button>
        )}

        {!enabled && setupData && (
          <div className="space-y-3">
            <p className="text-sm text-[var(--muted)]">
              Scan the QR code in your authenticator app, then enter the code
              below.
            </p>
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?data=${encodeURIComponent(setupData.provisioning_uri)}&size=200x200`}
              alt="MFA QR code"
              width={200}
              height={200}
            />
            <details>
              <summary className="cursor-pointer text-sm">
                Show backup codes
              </summary>
              <ul className="text-sm font-mono mt-2 space-y-1">
                {setupData.backup_codes.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </details>
            <input
              type="text"
              inputMode="numeric"
              placeholder="6-digit code"
              value={verifyCode}
              onChange={(e) => setVerifyCode(e.target.value)}
              className="input w-full"
              maxLength={6}
            />
            <button
              className="btn-primary w-full"
              onClick={() => verifyMutation.mutate(verifyCode)}
              disabled={verifyMutation.isPending || verifyCode.length < 6}
            >
              Verify &amp; Activate
            </button>
          </div>
        )}

        {enabled && (
          <div className="space-y-3">
            <input
              type="text"
              inputMode="numeric"
              placeholder="Enter code to confirm"
              value={disableCode}
              onChange={(e) => setDisableCode(e.target.value)}
              className="input w-full"
              maxLength={6}
            />
            <button
              className="btn-danger w-full"
              onClick={() => disableMutation.mutate(disableCode)}
              disabled={disableMutation.isPending || disableCode.length < 6}
            >
              Disable MFA
            </button>
          </div>
        )}

        {statusMsg && (
          <p className="text-sm text-[var(--success)]">{statusMsg}</p>
        )}
      </div>
    </div>
  );
}
