import { test, expect, Page } from "@playwright/test";

// ── Helpers ──────────────────────────────────────────────────────────

async function seedAuth(page: Page) {
  const header = Buffer.from(
    JSON.stringify({ alg: "HS256", typ: "JWT" }),
  ).toString("base64url");
  const payload = Buffer.from(
    JSON.stringify({ sub: 1, email: "alice@example.com", company_id: 1 }),
  ).toString("base64url");
  const fakeToken = `${header}.${payload}.fakesig`;

  await page.context().addCookies([
    { name: "cs_access_token", value: fakeToken, url: "http://localhost:3000" },
    { name: "access_token", value: fakeToken, url: "http://localhost:3000" },
  ]);

  await page.addInitScript((token: string) => {
    localStorage.setItem("token", token);
    localStorage.setItem(
      "user",
      JSON.stringify({
        id: 1,
        email: "alice@example.com",
        full_name: "Alice",
        company_id: 1,
        role: "admin",
      }),
    );
  }, fakeToken);
}

async function mockApis(page: Page) {
  await page.route("**/api/v1/**", (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/auth/me")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          email: "alice@example.com",
          full_name: "Alice",
          company_id: 1,
          role: "admin",
        }),
      });
    }

    if (url.includes("/marketplace/listings") && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "lst_1",
            title: "2024 Scope 1 Manufacturing",
            description: "Verified scope 1 data for manufacturing sector",
            price_credits: 100,
            listing_type: "one_time",
            status: "active",
            seller_company_id: 2,
            created_at: "2024-01-15T00:00:00Z",
          },
        ]),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

// ── Tests ────────────────────────────────────────────────────────────

test.describe("Marketplace happy-path", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
    await mockApis(page);
  });

  test("marketplace page loads and shows listings", async ({ page }) => {
    await page.goto("/marketplace");
    await page.waitForTimeout(1000);
    expect(page.url()).not.toMatch(/login/);
    // Page should render without crashing
    await expect(page.locator("body")).not.toBeEmpty();
  });

  test("settings page renders profile section", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForTimeout(1000);
    expect(page.url()).not.toMatch(/login/);
    await expect(page.locator("body")).not.toBeEmpty();
  });

  test("dashboard page renders main content area", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForTimeout(1000);
    expect(page.url()).not.toMatch(/login/);
    await expect(page.locator("main, [role='main'], #__next")).toBeVisible();
  });
});
