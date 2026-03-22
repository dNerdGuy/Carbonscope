import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import { DataTable, type Column } from "@/components/DataTable";
import ConfirmDialog from "@/components/ConfirmDialog";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useToast } from "@/components/Toast";
import {
  listTeamMembers,
  listInvitations,
  inviteTeamMember,
  updateMemberRole,
  removeMember,
  type TeamMember,
  type TeamInvite,
  type PaginatedResponse,
} from "@/lib/api";

const ROLES = ["admin", "editor", "viewer"];

const ROLE_BADGES: Record<string, string> = {
  admin: "bg-purple-500/20 text-purple-400",
  editor: "bg-blue-500/20 text-blue-400",
  viewer: "bg-gray-500/20 text-gray-400",
};

export const Route = createFileRoute("/team")({ component: TeamPage });

function TeamPage() {
  useDocumentTitle("Team");
  const { user, loading } = useRequireAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [inviting, setInviting] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<string | null>(null);
  const [roleEditId, setRoleEditId] = useState<string | null>(null);
  const [roleEditValue, setRoleEditValue] = useState("viewer");

  const membersQuery = useQuery<PaginatedResponse<TeamMember>>({
    queryKey: ["team-members", user?.company_id],
    queryFn: () => listTeamMembers({ limit: 100 }),
    enabled: !!user && !loading,
  });

  const invitesQuery = useQuery<PaginatedResponse<TeamInvite>>({
    queryKey: ["team-invitations", user?.company_id],
    queryFn: () => listInvitations({ limit: 50 }),
    enabled: !!user && !loading,
  });

  const members = membersQuery.data?.items ?? [];
  const invites = invitesQuery.data?.items ?? [];
  const pendingInvites = invites.filter((inv) => !inv.accepted_at);

  useEffect(() => {
    const err = membersQuery.error || invitesQuery.error;
    if (err) {
      setError(err instanceof Error ? err.message : "Failed to load team data");
    }
  }, [membersQuery.error, invitesQuery.error]);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setError("");
    try {
      await inviteTeamMember({ email: inviteEmail.trim(), role: inviteRole });
      toast("Invitation sent!", "success");
      setInviteEmail("");
      setInviteRole("viewer");
      setShowInvite(false);
      await queryClient.invalidateQueries({ queryKey: ["team-invitations"] });
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to send invitation",
      );
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(memberId: string) {
    setError("");
    try {
      await updateMemberRole(memberId, roleEditValue);
      toast("Role updated", "success");
      setRoleEditId(null);
      await queryClient.invalidateQueries({ queryKey: ["team-members"] });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update role");
    }
  }

  async function handleRemove() {
    if (!removeTarget) return;
    setError("");
    try {
      await removeMember(removeTarget);
      toast("Member removed", "success");
      setRemoveTarget(null);
      await queryClient.invalidateQueries({ queryKey: ["team-members"] });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to remove member");
    }
  }

  const memberColumns: Column<TeamMember>[] = [
    {
      key: "full_name",
      header: "Name",
      render: (m) => (
        <div>
          <span className="font-medium">{m.full_name}</span>
          <span className="block text-xs text-[var(--muted)]">{m.email}</span>
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      render: (m) =>
        roleEditId === m.id ? (
          <div className="flex items-center gap-2">
            <select
              className="input text-xs py-1 w-24"
              value={roleEditValue}
              onChange={(e) => setRoleEditValue(e.target.value)}
              aria-label="Select role"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <button
              onClick={() => handleRoleChange(m.id)}
              className="text-xs text-[var(--primary)] hover:underline"
            >
              Save
            </button>
            <button
              onClick={() => setRoleEditId(null)}
              className="text-xs text-[var(--muted)] hover:underline"
            >
              Cancel
            </button>
          </div>
        ) : (
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_BADGES[m.role] ?? ROLE_BADGES.viewer}`}
          >
            {m.role}
          </span>
        ),
    },
    {
      key: "is_active",
      header: "Status",
      render: (m) => (
        <span
          className={`inline-flex items-center gap-1.5 text-xs ${m.is_active ? "text-green-400" : "text-[var(--muted)]"}`}
        >
          <span
            className={`h-2 w-2 rounded-full ${m.is_active ? "bg-green-400" : "bg-[var(--muted)]"}`}
          />
          {m.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "last_login",
      header: "Last Login",
      render: (m) => (
        <span className="text-[var(--muted)] text-xs">
          {m.last_login ? new Date(m.last_login).toLocaleDateString() : "Never"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (m) =>
        m.id === user?.id ? (
          <span className="text-xs text-[var(--muted)]">You</span>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setRoleEditId(m.id);
                setRoleEditValue(m.role);
              }}
              className="text-xs text-[var(--primary)] hover:underline"
            >
              Edit Role
            </button>
            <button
              onClick={() => setRemoveTarget(m.id)}
              className="text-xs text-[var(--danger)] hover:underline"
            >
              Remove
            </button>
          </div>
        ),
    },
  ];

  const inviteColumns: Column<TeamInvite>[] = [
    { key: "email", header: "Email" },
    {
      key: "role",
      header: "Role",
      render: (inv) => (
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_BADGES[inv.role] ?? ROLE_BADGES.viewer}`}
        >
          {inv.role}
        </span>
      ),
    },
    {
      key: "expires_at",
      header: "Expires",
      render: (inv) => (
        <span className="text-[var(--muted)] text-xs">
          {new Date(inv.expires_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Sent",
      render: (inv) => (
        <span className="text-[var(--muted)] text-xs">
          {new Date(inv.created_at).toLocaleDateString()}
        </span>
      ),
    },
  ];

  if (loading || membersQuery.isLoading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">
      <Breadcrumbs
        items={[{ label: "Dashboard", href: "/dashboard" }, { label: "Team" }]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Team Management</h1>
          <p className="text-[var(--muted)] text-sm">
            {members.length} member{members.length !== 1 ? "s" : ""}
            {pendingInvites.length > 0 &&
              ` · ${pendingInvites.length} pending invite${pendingInvites.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className="btn-primary text-sm"
        >
          + Invite Member
        </button>
      </div>

      {error && <StatusMessage message={error} variant="error" />}

      {/* Invite form */}
      {showInvite && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Invite Team Member</h2>
          <form
            onSubmit={handleInvite}
            className="flex flex-wrap gap-3 items-end"
          >
            <div className="flex-1 min-w-[200px]">
              <label htmlFor="invite-email" className="label">
                Email Address
              </label>
              <input
                id="invite-email"
                type="email"
                className="input"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.com"
                required
              />
            </div>
            <div>
              <label htmlFor="invite-role" className="label">
                Role
              </label>
              <select
                id="invite-role"
                className="input"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <button type="submit" className="btn-primary" disabled={inviting}>
                {inviting ? "Sending..." : "Send Invite"}
              </button>
              <button
                type="button"
                onClick={() => setShowInvite(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Members table */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Members</h2>
        <DataTable<TeamMember>
          columns={memberColumns}
          data={members}
          loading={membersQuery.isLoading}
          emptyMessage="No team members found."
          caption="Team members"
        />
      </div>

      {/* Pending invitations */}
      {pendingInvites.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Pending Invitations</h2>
          <DataTable<TeamInvite>
            columns={inviteColumns}
            data={pendingInvites}
            emptyMessage="No pending invitations."
            caption="Pending invitations"
          />
        </div>
      )}

      <ConfirmDialog
        open={!!removeTarget}
        title="Remove Member"
        message="Are you sure you want to remove this member? They will lose access to the company."
        confirmLabel="Remove"
        onConfirm={handleRemove}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  );
}
