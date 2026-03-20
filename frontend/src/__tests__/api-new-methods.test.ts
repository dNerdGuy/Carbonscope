import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally before importing api
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);
vi.stubGlobal("localStorage", {
  getItem: vi.fn().mockReturnValue(null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
});

describe("New API methods", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getCreditLedger calls correct endpoint", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          items: [
            {
              id: "1",
              amount: -1,
              reason: "estimate",
              balance_after: 99,
              created_at: "2025-01-01T00:00:00Z",
            },
          ],
          total: 1,
        }),
    });

    const { getCreditLedger } = await import("@/lib/api");
    const result = await getCreditLedger({ limit: 10, offset: 0 });

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("/billing/credits/ledger");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=0");
    expect(result.items).toHaveLength(1);
    expect(result.items[0].amount).toBe(-1);
  });

  it("getCreditLedger works without params", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0 }),
    });

    const { getCreditLedger } = await import("@/lib/api");
    await getCreditLedger();

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("/billing/credits/ledger");
    expect(url).not.toContain("?");
  });

  it("deleteAccount calls DELETE /auth/me", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.resolve(null),
    });

    const { deleteAccount } = await import("@/lib/api");
    await deleteAccount();

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain("/auth/me");
    expect(init.method).toBe("DELETE");
  });

  it("getSupplyChainLink calls correct endpoint", async () => {
    const mockLink = {
      id: "abc-123",
      buyer_company_id: "buyer-1",
      supplier_company_id: "supplier-1",
      spend_usd: 1000,
      category: "raw_materials",
      status: "pending",
      notes: null,
      created_at: "2025-01-01T00:00:00Z",
    };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockLink),
    });

    const { getSupplyChainLink } = await import("@/lib/api");
    const result = await getSupplyChainLink("abc-123");

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("/supply-chain/links/abc-123");
    expect(result.id).toBe("abc-123");
  });

  it("getListing calls correct endpoint", async () => {
    const mockListing = {
      id: "lst-1",
      title: "Test Data",
      description: "desc",
      category: "energy",
      price_credits: 5,
      seller_company_id: "comp-1",
      is_active: true,
      created_at: "2025-01-01T00:00:00Z",
    };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockListing),
    });

    const { getListing } = await import("@/lib/api");
    const result = await getListing("lst-1");

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("/marketplace/listings/lst-1");
    expect(result.id).toBe("lst-1");
  });

  it("listWebhooks passes pagination params", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0 }),
    });

    const { listWebhooks } = await import("@/lib/api");
    await listWebhooks({ limit: 20, offset: 10 });

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("limit=20");
    expect(url).toContain("offset=10");
  });

  it("listAuditLogs passes filter params", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0 }),
    });

    const { listAuditLogs } = await import("@/lib/api");
    await listAuditLogs({
      action: "create",
      resource_type: "report",
      user_id: "user-1",
    });

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("action=create");
    expect(url).toContain("resource_type=report");
    expect(url).toContain("user_id=user-1");
  });
});
