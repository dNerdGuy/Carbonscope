import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

const mockListMembers = vi.fn();
const mockListInvitations = vi.fn();
const mockInviteTeamMember = vi.fn();
const mockUpdateMemberRole = vi.fn();
const mockRemoveMember = vi.fn();

vi.mock("@/lib/api", () => ({
  listTeamMembers: (...a: unknown[]) => mockListMembers(...a),
  listInvitations: (...a: unknown[]) => mockListInvitations(...a),
  inviteTeamMember: (...a: unknown[]) => mockInviteTeamMember(...a),
  updateMemberRole: (...a: unknown[]) => mockUpdateMemberRole(...a),
  removeMember: (...a: unknown[]) => mockRemoveMember(...a),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "admin@test.com", company_id: "c1" },
    loading: false,
  }),
}));

vi.mock("@/components/Breadcrumbs", () => ({
  default: () => <nav data-testid="breadcrumbs" />,
}));

const mockToast = vi.fn();
vi.mock("@/components/Toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

import { Route as _Route_TeamPage } from "@/app/team";
const TeamPage = _Route_TeamPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const MOCK_MEMBERS = {
  items: [
    {
      id: "u1",
      email: "admin@test.com",
      full_name: "Admin User",
      role: "admin",
      is_active: true,
      last_login: "2024-06-01T10:00:00Z",
      created_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "u2",
      email: "editor@test.com",
      full_name: "Editor User",
      role: "editor",
      is_active: true,
      last_login: null,
      created_at: "2024-02-01T00:00:00Z",
    },
  ],
  total: 2,
};

const MOCK_INVITATIONS = {
  items: [
    {
      id: "inv1",
      email: "pending@test.com",
      role: "viewer",
      invited_by: "u1",
      expires_at: "2025-01-01T00:00:00Z",
      accepted_at: null,
      created_at: "2024-06-15T00:00:00Z",
    },
  ],
  total: 1,
};

describe("TeamPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListMembers.mockResolvedValue(MOCK_MEMBERS);
    mockListInvitations.mockResolvedValue(MOCK_INVITATIONS);
  });

  it("renders team heading and member count", async () => {
    renderWithQueryClient(<TeamPage />);
    expect(await screen.findByText("Team Management")).toBeInTheDocument();
    expect(screen.getByText(/2 members/)).toBeInTheDocument();
  });

  it("shows members in the table", async () => {
    renderWithQueryClient(<TeamPage />);
    expect((await screen.findAllByText("Admin User")).length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText("Editor User").length).toBeGreaterThan(0);
    expect(screen.getAllByText("admin@test.com").length).toBeGreaterThan(0);
    expect(screen.getAllByText("editor@test.com").length).toBeGreaterThan(0);
  });

  it("shows pending invitation count", async () => {
    renderWithQueryClient(<TeamPage />);
    expect(await screen.findByText(/1 pending invite/)).toBeInTheDocument();
  });

  it("shows pending invitations table", async () => {
    renderWithQueryClient(<TeamPage />);
    expect(
      (await screen.findAllByText("pending@test.com")).length,
    ).toBeGreaterThan(0);
  });

  it("labels current user row as 'You'", async () => {
    renderWithQueryClient(<TeamPage />);
    expect((await screen.findAllByText("You")).length).toBeGreaterThan(0);
  });

  it("shows Edit Role and Remove buttons for other members", async () => {
    renderWithQueryClient(<TeamPage />);
    expect((await screen.findAllByText("Edit Role")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Remove").length).toBeGreaterThan(0);
  });

  it("opens invite form when button clicked", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<TeamPage />);
    await screen.findByText("Team Management");

    await user.click(screen.getByText("+ Invite Member"));
    expect(screen.getByText("Invite Team Member")).toBeInTheDocument();
    expect(screen.getByLabelText("Email Address")).toBeInTheDocument();
    expect(screen.getByLabelText("Role")).toBeInTheDocument();
  });

  it("sends invite on form submit", async () => {
    mockInviteTeamMember.mockResolvedValue({
      id: "inv2",
      email: "new@test.com",
      role: "viewer",
    });
    const user = userEvent.setup();
    renderWithQueryClient(<TeamPage />);
    await screen.findByText("Team Management");

    await user.click(screen.getByText("+ Invite Member"));
    await user.type(screen.getByLabelText("Email Address"), "new@test.com");
    await user.click(screen.getByText("Send Invite"));

    expect(mockInviteTeamMember).toHaveBeenCalledWith({
      email: "new@test.com",
      role: "viewer",
    });
  });

  it("shows role editor on Edit Role click", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<TeamPage />);
    await screen.findAllByText("Editor User");

    await user.click(screen.getAllByText("Edit Role")[0]);
    expect(screen.getAllByLabelText("Select role").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Save").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cancel").length).toBeGreaterThan(0);
  });

  it("calls updateMemberRole on Save", async () => {
    mockUpdateMemberRole.mockResolvedValue({
      ...MOCK_MEMBERS.items[1],
      role: "admin",
    });
    const user = userEvent.setup();
    renderWithQueryClient(<TeamPage />);
    await screen.findAllByText("Editor User");

    await user.click(screen.getAllByText("Edit Role")[0]);
    await user.selectOptions(
      screen.getAllByLabelText("Select role")[0],
      "admin",
    );
    await user.click(screen.getAllByText("Save")[0]);

    expect(mockUpdateMemberRole).toHaveBeenCalledWith("u2", "admin");
  });

  it("opens confirm dialog on Remove click", async () => {
    // Mock showModal/close since jsdom doesn't support <dialog> natively
    HTMLDialogElement.prototype.showModal =
      HTMLDialogElement.prototype.showModal || vi.fn();
    HTMLDialogElement.prototype.close =
      HTMLDialogElement.prototype.close || vi.fn();
    const user = userEvent.setup();
    renderWithQueryClient(<TeamPage />);
    await screen.findAllByText("Editor User");

    await user.click(screen.getAllByText("Remove")[0]);
    expect(
      screen.getByText(/Are you sure you want to remove this member/),
    ).toBeInTheDocument();
  });

  it("shows empty invitations gracefully", async () => {
    mockListInvitations.mockResolvedValue({ items: [], total: 0 });
    renderWithQueryClient(<TeamPage />);
    await screen.findByText("Team Management");
    // No pending invites text shown
    expect(screen.queryByText(/pending invite/)).not.toBeInTheDocument();
  });

  it("handles API error on members load", async () => {
    mockListMembers.mockRejectedValue(new Error("Network error"));
    renderWithQueryClient(<TeamPage />);
    expect(await screen.findByText(/Network error/)).toBeInTheDocument();
  });
});
