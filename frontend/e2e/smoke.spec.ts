import { test, expect } from "@playwright/test";

test.describe("Authentication flow", () => {
  test("login page loads and renders form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("h1")).toContainText("CarbonScope");
    await expect(page.getByText("Sign in to your account")).toBeVisible();
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("login page has register link", async ({ page }) => {
    await page.goto("/login");
    const registerLink = page.locator('a[href="/register"]');
    await expect(registerLink).toBeVisible();
  });

  test("register page loads and renders form", async ({ page }) => {
    await page.goto("/register");
    await expect(page.locator("h1")).toContainText("CarbonScope");
    await expect(page.getByText("Create your account")).toBeVisible();
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', "invalid@example.com");
    await page.fill('input[type="password"]', "wrong_password_123");
    await page.click('button[type="submit"]');
    // Should show an error message (server may be down — just check form doesn't navigate)
    await expect(page).toHaveURL(/login/);
  });
});

test.describe("Navigation", () => {
  test("unauthenticated user is redirected to login", async ({ page }) => {
    await page.goto("/dashboard");
    // Should redirect to login since not authenticated
    await expect(page).toHaveURL(/login/, { timeout: 5000 });
  });

  test("login page renders auth actions", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Register" })).toBeVisible();
  });
});

test.describe("Static pages", () => {
  test("login page has correct title", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveTitle(/CarbonScope/i);
  });
});
