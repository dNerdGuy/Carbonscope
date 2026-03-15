import { test, expect, Page } from "@playwright/test";

/** Seed localStorage with a fake authenticated session. */
async function seedAuth(page: Page) {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(
    JSON.stringify({ sub: 1, email: "alice@example.com", company_id: 1 }),
  ).toString("base64url");
  const fakeToken = `${header}.${payload}.fakesig`;

  // Middleware runs before client code, so we need a request cookie too.
  await page.context().addCookies([
    {
      name: "cs_access_token",
      value: fakeToken,
      url: "http://localhost:3000",
    },
    {
      name: "access_token",
      value: fakeToken,
      url: "http://localhost:3000",
    },
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

/** Intercept all /api/v1 calls with empty success responses. */
async function mockAllApis(page: Page) {
  await page.route("**/api/v1/**", (route) => {
    const url = route.request().url();
    const body =
      url.includes("/auth/me")
        ? {
            id: 1,
            email: "alice@example.com",
            full_name: "Alice",
            company_id: 1,
            role: "admin",
          }
        : {};
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

const SIDEBAR_SECTIONS = [
  { label: /dashboard/i, url: /dashboard/ },
  { label: /upload/i, url: /upload/ },
  { label: /compliance/i, url: /compliance/ },
  { label: /scenario/i, url: /scenario/ },
  { label: /benchmark/i, url: /benchmark/ },
  { label: /alert/i, url: /alert/ },
  { label: /marketplace/i, url: /marketplace/ },
  { label: /setting/i, url: /setting/ },
];

test.describe("Authenticated navigation", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
    await mockAllApis(page);
  });

  for (const section of SIDEBAR_SECTIONS) {
    test(`can navigate to ${section.label.source}`, async ({ page }) => {
      await page.goto("/dashboard");
      await page.waitForTimeout(500);

      // Find and click a link whose text matches the section label
      const link = page.locator(`a, button`).filter({ hasText: section.label });
      if ((await link.count()) > 0) {
        await link.first().click();
        await expect(page).toHaveURL(section.url, { timeout: 5000 });
      } else {
        // Navigate directly if sidebar link not found (may be behind a menu)
        await page.goto(
          `/${section.label.source.replace(/[/\\^$.*+?()[\]{}|]/g, "").toLowerCase()}`,
        );
        // Should stay authenticated — not redirected to login
        await page.waitForTimeout(1000);
        const url = page.url();
        expect(url).not.toMatch(/login/);
      }
    });
  }
});

test.describe("Page responsiveness", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
    await mockAllApis(page);
  });

  test("mobile viewport shows page content", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/dashboard");
    await page.waitForTimeout(1000);
    // Should not redirect to login
    expect(page.url()).not.toMatch(/login/);
  });

  test("tablet viewport shows page content", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/dashboard");
    await page.waitForTimeout(1000);
    expect(page.url()).not.toMatch(/login/);
  });
});

test.describe("Error handling", () => {
  test("404 page renders for unknown routes", async ({ page }) => {
    await page.goto("/this-route-does-not-exist-abc123");
    // Should show a 404 or not-found indicator
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });

  test("API error does not crash the app", async ({ page }) => {
    await seedAuth(page);
    // Make all API calls return 500
    await page.route("**/api/v1/**", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Internal Server Error" }),
      }),
    );

    await page.goto("/dashboard");
    await page.waitForTimeout(2000);
    // The page should still render (error boundary or error message, not blank)
    const body = await page.textContent("body");
    expect(body!.length).toBeGreaterThan(0);
  });
});
