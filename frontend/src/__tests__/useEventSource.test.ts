import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useEventSource } from "@/hooks/useEventSource";

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, fn: (e: MessageEvent) => void) {
    (this.listeners[type] ??= []).push(fn);
  }

  close() {
    this.closed = true;
  }

  // Test helper: simulate a server-sent event
  emit(type: string, data: unknown) {
    for (const fn of this.listeners[type] ?? []) {
      fn({ data: JSON.stringify(data) } as MessageEvent);
    }
  }
}

vi.stubGlobal("EventSource", MockEventSource);

describe("useEventSource", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("opens an EventSource when enabled", () => {
    const handler = vi.fn();
    renderHook(() => useEventSource({ report_ready: handler }));

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].closed).toBe(false);
  });

  it("does not open when disabled", () => {
    renderHook(() => useEventSource({ report_ready: vi.fn() }, false));
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("dispatches parsed JSON to the correct handler", () => {
    const handler = vi.fn();
    renderHook(() => useEventSource({ report_ready: handler }));

    const es = MockEventSource.instances[0];
    act(() => es.emit("report_ready", { id: "42" }));

    expect(handler).toHaveBeenCalledWith({ id: "42" });
  });

  it("ignores malformed payloads without throwing", () => {
    const handler = vi.fn();
    renderHook(() => useEventSource({ report_ready: handler }));

    const es = MockEventSource.instances[0];
    // Send invalid JSON
    for (const fn of es.listeners["report_ready"] ?? []) {
      fn({ data: "not-json{" } as MessageEvent);
    }

    expect(handler).not.toHaveBeenCalled();
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = renderHook(() =>
      useEventSource({ report_ready: vi.fn() }),
    );

    const es = MockEventSource.instances[0];
    expect(es.closed).toBe(false);

    unmount();
    expect(es.closed).toBe(true);
  });

  it("reconnects after error with 5s delay", () => {
    renderHook(() => useEventSource({ report_ready: vi.fn() }));

    expect(MockEventSource.instances).toHaveLength(1);
    const es = MockEventSource.instances[0];

    // Trigger error → should schedule reconnect
    act(() => es.onerror?.());
    expect(es.closed).toBe(true);

    // Advance 5 seconds
    act(() => vi.advanceTimersByTime(5000));
    expect(MockEventSource.instances).toHaveLength(2);
    expect(MockEventSource.instances[1].closed).toBe(false);
  });

  it("does not reconnect after unmount", () => {
    const { unmount } = renderHook(() =>
      useEventSource({ report_ready: vi.fn() }),
    );

    const es = MockEventSource.instances[0];

    // Trigger error, then unmount before timer fires
    act(() => es.onerror?.());
    unmount();

    act(() => vi.advanceTimersByTime(5000));
    // Should still be just the one instance (no reconnect)
    expect(MockEventSource.instances).toHaveLength(1);
  });
});
