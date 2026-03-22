import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

const mockReplace = vi.fn();

let mockUser: { email: string } | null = null;
let mockLoading = false;

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading }),
}));

import { useRequireAuth } from "@/hooks/useRequireAuth";

describe("useRequireAuth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = null;
    mockLoading = false;
  });

  it("returns user and loading from auth context", () => {
    mockUser = { email: "u@test.com" };
    const { result } = renderHook(() => useRequireAuth());
    expect(result.current.user).toEqual({ email: "u@test.com" });
    expect(result.current.loading).toBe(false);
  });

  it("redirects to /login when not loading and user is null", () => {
    mockUser = null;
    mockLoading = false;
    renderHook(() => useRequireAuth());
    expect(mockReplace).toHaveBeenCalledWith("/login");
  });

  it("does NOT redirect while still loading", () => {
    mockUser = null;
    mockLoading = true;
    renderHook(() => useRequireAuth());
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("does NOT redirect when user is logged in", () => {
    mockUser = { email: "admin@test.com" };
    mockLoading = false;
    renderHook(() => useRequireAuth());
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
