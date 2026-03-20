import { describe, it, expect, vi, beforeEach } from "vitest";

describe("Auto token refresh (cookie-based)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
  });

  it("retries request after refreshing token on 401", async () => {
    let callCount = 0;
    const mockFetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/auth/refresh")) {
        // refresh endpoint — server sets httpOnly cookies in the response
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({}),
        });
      }
      callCount++;
      if (callCount === 1) {
        // First call: 401
        return Promise.resolve({
          ok: false,
          status: 401,
          statusText: "Unauthorized",
          json: () => Promise.resolve({ detail: "Token expired" }),
        });
      }
      // Retry call: success (cookies auto-sent by browser)
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: "123", email: "test@test.com" }),
      });
    });

    vi.stubGlobal("fetch", mockFetch);
    // localStorage still used for user display data (not tokens)
    vi.stubGlobal("localStorage", {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });

    const { getProfile } = await import("@/lib/api");
    const result = await getProfile();

    expect(result).toEqual({ id: "123", email: "test@test.com" });
    // Should have called: original request, refresh, retry
    expect(mockFetch).toHaveBeenCalledTimes(3);
    // Refresh now sends empty body (cookies used for auth)
    const [, refreshInit] = mockFetch.mock.calls[1];
    expect(refreshInit.body).toBe(JSON.stringify({}));
  });

  it("clears user state when refresh also fails with 401", async () => {
    const dispatchSpy = vi.fn();
    vi.stubGlobal("dispatchEvent", dispatchSpy);

    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: () => Promise.resolve({ detail: "Session expired" }),
    });

    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("localStorage", {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });

    const { getProfile } = await import("@/lib/api");
    await expect(getProfile()).rejects.toThrow("Session expired");
    // Only user display data is cleared from localStorage (tokens are in httpOnly cookies)
    expect(localStorage.removeItem).toHaveBeenCalledWith("user");
  });

  it("attempts refresh on 401 even without localStorage tokens", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: () => Promise.resolve({ detail: "Not authenticated" }),
    });

    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("localStorage", {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });

    const { getProfile } = await import("@/lib/api");
    await expect(getProfile()).rejects.toThrow("Session expired");
    // With cookie-based auth, refresh is always attempted on 401:
    // 1. original request → 401, 2. refresh attempt → 401 (fails)
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});
