import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api";

describe("ApiError", () => {
  it("has status and message", () => {
    const err = new ApiError(404, "Not Found");
    expect(err.status).toBe(404);
    expect(err.message).toBe("Not Found");
    expect(err).toBeInstanceOf(Error);
  });

  it("is instanceof Error", () => {
    const err = new ApiError(500, "Server Error");
    expect(err instanceof Error).toBe(true);
    expect(err instanceof ApiError).toBe(true);
  });
});

describe("API Client request function", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends request with credentials (cookies) instead of Bearer token", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "1", email: "test@test.com" }),
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("localStorage", {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });

    // Dynamically import to pick up mocked globals
    const { getProfile } = await import("@/lib/api");
    await getProfile();

    expect(mockFetch).toHaveBeenCalledOnce();
    const [, init] = mockFetch.mock.calls[0];
    // Should NOT have Authorization header (cookies are used instead)
    expect(init.headers["Authorization"]).toBeUndefined();
    // Should include credentials for cookie-based auth
    expect(init.credentials).toBe("include");
  });

  it("throws ApiError on non-ok response", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: () => Promise.resolve({ detail: "Invalid token" }),
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("localStorage", {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });

    const { getProfile } = await import("@/lib/api");
    // With auto-refresh: 401 triggers refresh attempt which also gets 401 → "Session expired"
    await expect(getProfile()).rejects.toThrow("Session expired");
  });

  it("retries transient 503 and then succeeds", async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        headers: new Headers(),
        json: () => Promise.resolve({ detail: "temporarily unavailable" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: () => Promise.resolve({ id: "1", email: "test@test.com" }),
      });

    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("localStorage", {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });

    const { getProfile } = await import("@/lib/api");
    const profile = await getProfile();

    expect(profile.email).toBe("test@test.com");
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});
