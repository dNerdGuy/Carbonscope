import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const mockListWebhooks = vi.fn();
const mockCreateWebhook = vi.fn();
const mockDeleteWebhook = vi.fn();
const mockToggleWebhook = vi.fn();
const mockListDeliveries = vi.fn();
const mockRetryDelivery = vi.fn();

vi.mock("@/lib/api", () => ({
  listWebhooks: (...a: unknown[]) => mockListWebhooks(...a),
  createWebhook: (...a: unknown[]) => mockCreateWebhook(...a),
  deleteWebhook: (...a: unknown[]) => mockDeleteWebhook(...a),
  toggleWebhook: (...a: unknown[]) => mockToggleWebhook(...a),
  listDeliveries: (...a: unknown[]) => mockListDeliveries(...a),
  retryDelivery: (...a: unknown[]) => mockRetryDelivery(...a),
}));

vi.mock("@/components/ConfirmDialog", () => ({
  default: ({
    open,
    onConfirm,
    onCancel,
    title,
  }: {
    open: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    title: string;
  }) =>
    open ? (
      <div>
        <span>{title}</span>
        <button onClick={onConfirm}>Confirm</button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    ) : null,
}));

vi.mock("@/components/StatusMessage", () => ({
  StatusMessage: ({ message }: { message: string }) => <div>{message}</div>,
}));

import WebhookSection from "@/components/WebhookSection";

const WEBHOOKS = {
  items: [
    {
      id: "wh-1",
      url: "https://example.com/hook",
      event_types: ["report.created"],
      active: true,
      created_at: "2024-01-01T00:00:00Z",
    },
  ],
};

describe("WebhookSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListWebhooks.mockResolvedValue(WEBHOOKS);
  });

  it("renders heading", async () => {
    render(<WebhookSection />);
    expect(await screen.findByText("Webhooks")).toBeInTheDocument();
  });

  it("displays existing webhook URL", async () => {
    render(<WebhookSection />);
    expect(
      await screen.findByText("https://example.com/hook"),
    ).toBeInTheDocument();
  });

  it("shows error message when listWebhooks fails", async () => {
    mockListWebhooks.mockRejectedValue(new Error("network error"));
    render(<WebhookSection />);
    expect(
      await screen.findByText("Failed to load webhooks"),
    ).toBeInTheDocument();
  });

  it("disables add button when URL is empty", async () => {
    render(<WebhookSection />);
    await screen.findByText("Webhooks");
    const addBtn = screen.getByRole("button", { name: /add webhook/i });
    expect(addBtn).toBeDisabled();
  });

  it("enables add button when URL is entered", async () => {
    render(<WebhookSection />);
    await screen.findByText("Webhooks");
    const input = screen.getByPlaceholderText(
      /https:\/\/example\.com\/webhook/,
    );
    fireEvent.change(input, { target: { value: "https://my.site/hook" } });
    const addBtn = screen.getByRole("button", { name: /add webhook/i });
    expect(addBtn).not.toBeDisabled();
  });

  it("calls createWebhook when add button is clicked", async () => {
    mockCreateWebhook.mockResolvedValue({
      id: "wh-2",
      url: "https://my.site/hook",
      event_types: ["report.created"],
      active: true,
      created_at: "2024-01-02T00:00:00Z",
    });
    render(<WebhookSection />);
    await screen.findByText("Webhooks");
    const input = screen.getByPlaceholderText(
      /https:\/\/example\.com\/webhook/,
    );
    fireEvent.change(input, { target: { value: "https://my.site/hook" } });
    fireEvent.click(screen.getByRole("button", { name: /add webhook/i }));
    await waitFor(() =>
      expect(mockCreateWebhook).toHaveBeenCalledWith(
        expect.objectContaining({ url: "https://my.site/hook" }),
      ),
    );
  });

  it("shows delete confirm dialog when delete button clicked", async () => {
    render(<WebhookSection />);
    await screen.findByText("https://example.com/hook");
    const deleteBtn = screen.getAllByRole("button", { name: /delete/i })[0];
    fireEvent.click(deleteBtn);
    expect(await screen.findByText(/delete webhook/i)).toBeInTheDocument();
  });

  it("calls deleteWebhook after confirmation", async () => {
    mockDeleteWebhook.mockResolvedValue(undefined);
    render(<WebhookSection />);
    await screen.findByText("https://example.com/hook");
    const deleteBtn = screen.getAllByRole("button", { name: /delete/i })[0];
    fireEvent.click(deleteBtn);
    const confirmBtn = await screen.findByRole("button", { name: "Confirm" });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(mockDeleteWebhook).toHaveBeenCalledWith("wh-1"));
  });
});
