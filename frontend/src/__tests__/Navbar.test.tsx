import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mockPathname = vi.fn(() => "/reports");

// Mock auth context
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { email: "test@example.com" },
    logout: vi.fn(),
  }),
}));

// Mock theme context
vi.mock("@/lib/theme-context", () => ({
  useTheme: () => ({
    theme: "dark",
    toggleTheme: vi.fn(),
  }),
}));

import Sidebar from "@/components/Sidebar";

describe("Sidebar", () => {
  it("highlights exact route match", () => {
    mockPathname.mockReturnValue("/reports");
    render(<Sidebar />);
    const reportLinks = screen.getAllByText(/^Reports$/);
    const link = reportLinks[0].closest("a");
    expect(link?.className).toContain("sidebar-link-active");
  });

  it("highlights parent nav item on deep route", () => {
    mockPathname.mockReturnValue("/reports/abc123");
    render(<Sidebar />);
    const reportLinks = screen.getAllByText(/^Reports$/);
    const link = reportLinks[0].closest("a");
    expect(link?.className).toContain("sidebar-link-active");
  });

  it("does not highlight non-matching routes", () => {
    mockPathname.mockReturnValue("/reports/abc123");
    render(<Sidebar />);
    const settingsLinks = screen.getAllByText(/^Settings$/);
    const link = settingsLinks[0].closest("a");
    expect(link?.className).not.toContain("sidebar-link-active");
  });

  it("does not highlight dashboard for non-dashboard deep routes", () => {
    mockPathname.mockReturnValue("/reports/abc123");
    render(<Sidebar />);
    const dashboardLinks = screen.getAllByText(/^Dashboard$/);
    const link = dashboardLinks[0].closest("a");
    expect(link?.className).not.toContain("sidebar-link-active");
  });

  it("renders all navigation sections", () => {
    mockPathname.mockReturnValue("/dashboard");
    render(<Sidebar />);
    expect(screen.getAllByText("Main").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Analysis").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Operations").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Platform").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Account").length).toBeGreaterThan(0);
  });

  it("renders new nav items that were previously missing", () => {
    mockPathname.mockReturnValue("/dashboard");
    render(<Sidebar />);
    expect(screen.getAllByText("Benchmarks").length).toBeGreaterThan(0);
    expect(screen.getAllByText("PCAF").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Reviews").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Recommendations").length).toBeGreaterThan(0);
  });

  it("shows user email", () => {
    mockPathname.mockReturnValue("/dashboard");
    render(<Sidebar />);
    expect(screen.getAllByText("test@example.com").length).toBeGreaterThan(0);
  });

  it("shows logout button", () => {
    mockPathname.mockReturnValue("/dashboard");
    render(<Sidebar />);
    expect(screen.getAllByText("Logout").length).toBeGreaterThan(0);
  });
});
