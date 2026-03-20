import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockLogin = vi.fn();
const mockRegister = vi.fn();
const mockLogoutApi = vi.fn();

vi.mock("@/lib/api", () => ({
  login: (...a: unknown[]) => mockLogin(...a),
  register: (...a: unknown[]) => mockRegister(...a),
  logoutApi: (...a: unknown[]) => mockLogoutApi(...a),
}));

vi.mock("@/components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { AuthProvider, useAuth } from "@/lib/auth-context";

function TestConsumer() {
  const { user, loading, login, logout, register } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? JSON.stringify(user) : "null"}</span>
      <button onClick={() => login("a@b.com", "pw")}>Login</button>
      <button onClick={logout}>Logout</button>
      <button
        onClick={() =>
          register({
            email: "a@b.com",
            password: "pw",
            full_name: "Test",
            company_name: "Co",
            industry: "tech",
          })
        }
      >
        Register
      </button>
    </div>
  );
}

// Create a valid JWT-like token: header.payload.signature
function makeToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256" }));
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `${header}.${body}.fakesig`;
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("starts with loading then resolves", async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    // After useEffect, loading should become false
    expect(await screen.findByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("user")).toHaveTextContent("null");
  });

  it("restores user from localStorage", async () => {
    const savedUser = {
      id: "u1",
      email: "saved@test.com",
      full_name: "Saved",
      company_id: "c1",
      role: "admin",
    };
    localStorage.setItem("user", JSON.stringify(savedUser));

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(await screen.findByTestId("user")).toHaveTextContent(
      "saved@test.com",
    );
  });

  it("login stores token and navigates to dashboard", async () => {
    const token = makeToken({ sub: "user-1", company_id: "comp-1" });
    mockLogin.mockResolvedValue({
      access_token: token,
      refresh_token: "refresh-1",
      token_type: "bearer",
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await screen.findByTestId("loading");
    await act(async () => {
      screen.getByText("Login").click();
    });

    expect(mockLogin).toHaveBeenCalledWith("a@b.com", "pw");
    // Tokens are now stored in httpOnly cookies by the server, not localStorage
    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("user")).not.toBeNull();
    expect(mockPush).toHaveBeenCalledWith("/dashboard");
  });

  it("logout clears state and navigates to login", async () => {
    localStorage.setItem(
      "user",
      JSON.stringify({ id: "u1", email: "a@b.com" }),
    );
    mockLogoutApi.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await screen.findByTestId("loading");
    await act(async () => {
      screen.getByText("Logout").click();
    });

    expect(localStorage.getItem("user")).toBeNull();
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("logout succeeds even if API call fails", async () => {
    localStorage.setItem("user", JSON.stringify({ id: "u1" }));
    mockLogoutApi.mockRejectedValue(new Error("Server down"));

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await screen.findByTestId("loading");
    await act(async () => {
      screen.getByText("Logout").click();
    });

    expect(localStorage.getItem("user")).toBeNull();
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("register auto-logs in", async () => {
    const user = {
      id: "u2",
      email: "a@b.com",
      full_name: "Test",
      company_id: "c1",
      role: "user",
    };
    const token = makeToken({ sub: "u2", company_id: "c1" });
    mockRegister.mockResolvedValue(user);
    mockLogin.mockResolvedValue({
      access_token: token,
      refresh_token: "refresh-2",
      token_type: "bearer",
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await screen.findByTestId("loading");
    await act(async () => {
      screen.getByText("Register").click();
    });

    expect(mockRegister).toHaveBeenCalled();
    expect(mockLogin).toHaveBeenCalledWith("a@b.com", "pw");
    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("user")).not.toBeNull();
    expect(mockPush).toHaveBeenCalledWith("/dashboard");
  });
});

describe("useAuth", () => {
  it("throws outside AuthProvider", () => {
    // Suppress React error boundary console noise
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow(
      "useAuth must be inside AuthProvider",
    );
    spy.mockRestore();
  });
});
