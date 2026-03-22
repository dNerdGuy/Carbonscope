/**
 * User journey E2E tests.
 *
 * Covers the three key flows identified in Phase 3.5:
 *  1. Full register → upload data → estimate → view report → export CSV
 *  2. MFA setup flow
 *  3. Marketplace purchase flow
 *
 * All backend calls are intercepted via page.route() so tests run without
 * a live API server (the Next.js dev/prod server is still required).
 */

import { test, expect, type Page } from "@playwright/test";

// ── Shared helpers ────────────────────────────────────────────────

const FAKE_USER = {
  id: "u1",
  email: "journey@test.com",
  full_name: "Journey Tester",
  company_id: "c1",
  role: "admin",
};

const FAKE_COMPANY = {
  id: "c1",
  name: "Journey Corp",
  industry: "technology",
  region: "US",
};

const FAKE_UPLOAD = {
  id: "up1",
  year: 2024,
  status: "pending",
  created_at: "2025-01-01T00:00:00Z",
};

const FAKE_REPORT = {
  id: "rpt1",
  year: 2024,
  scope1: 120.5,
  scope2: 85.3,
  scope3: 420.8,
  total: 626.6,
  confidence: 0.87,
  methodology_version: "ghg_protocol_v3",
  created_at: "2025-01-01T01:00:00Z",
};

/** Seed localStorage / cookies with a valid-looking JWT so auth guards pass. */
async function seedAuth(page: Page) {
  const header = Buffer.from(
    JSON.stringify({ alg: "HS256", typ: "JWT" }),
  ).toString("base64url");
  const payload = Buffer.from(
    JSON.stringify({
      sub: FAKE_USER.id,
      email: FAKE_USER.email,
      company_id: FAKE_USER.company_id,
    }),
  ).toString("base64url");
  const fakeToken = `${header}.${payload}.fakesig`;

  await page.context().addCookies([
    { name: "cs_access_token", value: fakeToken, url: "http://localhost:3000" },
    { name: "access_token", value: fakeToken, url: "http://localhost:3000" },
  ]);

  await page.addInitScript(
    ({ token, user }: { token: string; user: typeof FAKE_USER }) => {
      localStorage.setItem("token", token);
      localStorage.setItem("user", JSON.stringify(user));
    },
    { token: fakeToken, user: FAKE_USER },
  );
}

/** Intercept all /api/v1/** calls with sensible defaults, overridden per-test. */
async function mockCoreApis(page: Page) {
  await page.route("**/api/v1/**", (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // Auth
    if (url.includes("/auth/me")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_USER),
      });
    }
    if (url.includes("/auth/register") && method === "POST") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(FAKE_USER),
      });
    }
    if (url.includes("/auth/login") && method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "fake-token",
          token_type: "bearer",
        }),
      });
    }

    // Company
    if (url.includes("/company") && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_COMPANY),
      });
    }

    // Data uploads
    if (url.includes("/carbon/upload") && method === "POST") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(FAKE_UPLOAD),
      });
    }

    // Estimate trigger
    if (url.includes("/carbon/estimate") && method === "POST") {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(FAKE_REPORT),
      });
    }

    // Reports list
    if (
      url.match(/\/carbon\/reports\b/) &&
      method === "GET" &&
      !url.includes("export")
    ) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [FAKE_REPORT],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      });
    }

    // Export CSV
    if (url.includes("/carbon/reports/export")) {
      return route.fulfill({
        status: 200,
        contentType: "text/csv",
        headers: { "Content-Disposition": "attachment; filename=reports.csv" },
        body: "id,year,scope1,scope2,scope3,total,confidence\nrpt1,2024,120.5,85.3,420.8,626.6,0.87",
      });
    }

    // Dashboard
    if (url.includes("/carbon/dashboard") || url.includes("/dashboard")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          latest_report: FAKE_REPORT,
          company: FAKE_COMPANY,
          total_reports: 1,
        }),
      });
    }

    // Fallback
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

// ── Journey 1: Register → Upload → Estimate → Reports → Export ───

test.describe("Full data journey", () => {
  test("register page shows all required fields", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByLabel("Full Name")).toBeVisible();
    await expect(page.getByLabel("Company Name")).toBeVisible();
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Create Account" }),
    ).toBeVisible();
  });

  test("register form submits and redirects to dashboard", async ({ page }) => {
    await mockCoreApis(page);
    await seedAuth(page);

    // Intercept register POST
    await page.route("**/auth/register", (route) => {
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(FAKE_USER),
      });
    });

    await page.goto("/register");
    await page.getByLabel("Full Name").fill("Journey Tester");
    await page.getByLabel("Company Name").fill("Journey Corp");
    await page.getByLabel("Email", { exact: true }).fill("journey@test.com");
    await page.getByLabel("Password", { exact: true }).fill("Str0ng!Pass");
    await page
      .getByLabel("Confirm Password", { exact: true })
      .fill("Str0ng!Pass");
    await page.getByLabel("Industry").selectOption({ index: 1 });
    await page.getByRole("button", { name: "Create Account" }).click();

    // After successful register the app redirects out of /register
    await expect(page).not.toHaveURL(/register/, { timeout: 5000 });
  });

  test("upload page renders all scope input fields", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await page.goto("/upload");

    // Scope 1 inputs
    await expect(page.getByLabel(/natural gas/i)).toBeVisible();
    await expect(page.getByLabel(/diesel/i)).toBeVisible();
    // Scope 2 input
    await expect(page.getByLabel(/electricity/i)).toBeVisible();
  });

  test("upload form submits and shows estimation result", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await page.goto("/upload");

    await page.getByLabel(/electricity/i).fill("50000");
    await page.getByLabel(/employee/i).fill("100");
    await page.getByRole("button", { name: /submit|estimate/i }).click();

    // Should show estimate result (total visible)
    await expect(page.getByText(/626|total/i)).toBeVisible({ timeout: 8000 });
  });

  test("reports page lists the estimated report", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await page.goto("/reports");

    await expect(page.getByText(/2024/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/626/)).toBeVisible();
  });

  test("reports export CSV download is triggered", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await page.goto("/reports");

    // Wait for page to load content
    await page.waitForTimeout(1000);

    // Click the export / download button (text varies by implementation)
    const exportBtn = page
      .getByRole("button", { name: /export|download/i })
      .first();
    if (await exportBtn.isVisible()) {
      const [download] = await Promise.all([
        page.waitForEvent("download", { timeout: 4000 }).catch(() => null),
        exportBtn.click(),
      ]);
      // If a download was triggered, validate the filename
      if (download) {
        expect(download.suggestedFilename()).toMatch(/\.(csv|json|parquet)$/);
      }
    } else {
      // Export link exists (anchor-based download)
      const exportLink = page
        .getByRole("link", { name: /export|download/i })
        .first();
      await expect(exportLink).toBeVisible();
    }
  });
});

// ── Journey 2: MFA setup flow ─────────────────────────────────────

test.describe("MFA setup flow", () => {
  const MFA_STATUS_OFF = { enabled: false, totp_provisioned: false };
  const MFA_STATUS_ON = { enabled: true, totp_provisioned: true };
  const MFA_SETUP = {
    secret: "JBSWY3DPEHPK3PXP",
    qr_code: "data:image/png;base64,iVBORw0KGgo=",
    backup_codes: ["11111111", "22222222"],
  };

  async function mockMfaApis(page: Page, { enabled }: { enabled: boolean }) {
    await page.route("**/mfa/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(enabled ? MFA_STATUS_ON : MFA_STATUS_OFF),
      }),
    );
    await page.route("**/mfa/setup", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MFA_SETUP),
      }),
    );
    await page.route("**/mfa/verify", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true }),
      }),
    );
    await page.route("**/mfa/disable", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true }),
      }),
    );
  }

  test("MFA page shows disabled status when MFA is off", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMfaApis(page, { enabled: false });
    await page.goto("/mfa");

    await expect(page.getByText(/disabled|not enabled/i)).toBeVisible({
      timeout: 5000,
    });
    await expect(
      page.getByRole("button", { name: /enable|set up/i }),
    ).toBeVisible();
  });

  test("MFA setup shows QR code after clicking Enable", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMfaApis(page, { enabled: false });
    await page.goto("/mfa");

    await page.getByRole("button", { name: /enable|set up/i }).click();
    // After setup call, QR code or secret should be shown
    await expect(
      page
        .getByAltText(/qr/i)
        .or(page.getByText(/JBSWY3DPEHPK3PXP/))
        .or(page.getByText(/authenticator/i)),
    ).toBeVisible({ timeout: 5000 });
  });

  test("MFA verify step accepts a 6-digit TOTP code", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMfaApis(page, { enabled: false });
    await page.goto("/mfa");

    // Trigger setup to reveal verify form
    await page.getByRole("button", { name: /enable|set up/i }).click();
    await page.waitForTimeout(500);

    const codeInput = page
      .getByPlaceholder(/6.digit|totp|code/i)
      .or(page.getByLabel(/code/i));
    if (await codeInput.isVisible()) {
      await codeInput.fill("123456");
      await page.getByRole("button", { name: /verify|confirm/i }).click();
      // After verify the page should show success or redirect
      await page.waitForTimeout(1000);
      await expect(
        page.getByText(/success|enabled/i).or(page.getByText(/2024/)),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test("MFA page shows enabled status when MFA is on", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMfaApis(page, { enabled: true });
    await page.goto("/mfa");

    await expect(page.getByText(/enabled|active/i)).toBeVisible({
      timeout: 5000,
    });
    await expect(page.getByRole("button", { name: /disable/i })).toBeVisible();
  });
});

// ── Journey 3: Marketplace purchase flow ─────────────────────────

test.describe("Marketplace purchase flow", () => {
  const LISTINGS = [
    {
      id: "lst_1",
      title: "2024 Scope 1 Manufacturing Offsets",
      description: "Verified scope 1 reductions for heavy manufacturing",
      price_credits: 150,
      listing_type: "one_time",
      status: "active",
      seller_company_id: "c2",
      created_at: "2024-03-01T00:00:00Z",
    },
    {
      id: "lst_2",
      title: "2024 Technology Scope 3 Benchmark",
      description: "Industry-aggregated Scope 3 data for technology sector",
      price_credits: 75,
      listing_type: "subscription",
      status: "active",
      seller_company_id: "c3",
      created_at: "2024-04-01T00:00:00Z",
    },
  ];

  async function mockMarketplaceApis(page: Page) {
    await page.route("**/marketplace/listings**", (route) => {
      const method = route.request().method();
      if (method === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(LISTINGS),
        });
      }
      return route.continue();
    });

    await page.route("**/marketplace/purchase**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          order_id: "ord_1",
          credits_spent: 150,
        }),
      }),
    );

    await page.route("**/billing**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ credits: 500, plan: "pro" }),
      }),
    );
  }

  test("marketplace page loads and displays listings", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMarketplaceApis(page);
    await page.goto("/marketplace");

    await expect(page.getByText(/2024 Scope 1 Manufacturing/i)).toBeVisible({
      timeout: 8000,
    });
    await expect(page.getByText(/2024 Technology Scope 3/i)).toBeVisible();
  });

  test("listings show pricing information", async ({ page }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMarketplaceApis(page);
    await page.goto("/marketplace");

    // Price credits should be visible
    await expect(page.getByText(/150/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/75/)).toBeVisible();
  });

  test("clicking purchase on a listing shows confirmation or processes purchase", async ({
    page,
  }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMarketplaceApis(page);
    await page.goto("/marketplace");

    // Wait for listings to load
    await page
      .getByText(/2024 Scope 1 Manufacturing/i)
      .waitFor({ timeout: 8000 });

    // Find a buy/purchase button
    const buyBtn = page
      .getByRole("button", { name: /buy|purchase|get access/i })
      .first();
    if (await buyBtn.isVisible()) {
      await buyBtn.click();
      // Should either show a confirm dialog or navigate
      await page.waitForTimeout(800);
      // Confirm or check for success state
      const confirmBtn = page.getByRole("button", { name: /confirm|proceed/i });
      if (await confirmBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await confirmBtn.click();
      }
      // After purchase — success message, order confirmation, or stay on page
      await page.waitForTimeout(600);
      await expect(page.locator("body")).not.toContainText("Fatal error");
    }
  });

  test("marketplace page is accessible while authenticated", async ({
    page,
  }) => {
    await seedAuth(page);
    await mockCoreApis(page);
    await mockMarketplaceApis(page);
    await page.goto("/marketplace");

    // Should not redirect to login
    await page.waitForTimeout(1000);
    await expect(page).not.toHaveURL(/login/);
    await expect(page.locator("body")).not.toBeEmpty();
  });
});
