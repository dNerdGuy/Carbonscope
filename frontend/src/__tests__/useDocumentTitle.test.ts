import { describe, it, expect, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

describe("useDocumentTitle", () => {
  const originalTitle = document.title;

  afterEach(() => {
    document.title = originalTitle;
  });

  it("sets document title with suffix", () => {
    renderHook(() => useDocumentTitle("Dashboard"));
    expect(document.title).toBe("Dashboard | CarbonScope");
  });

  it("sets fallback title when empty string is provided", () => {
    renderHook(() => useDocumentTitle(""));
    expect(document.title).toBe("CarbonScope");
  });

  it("restores previous title on unmount", () => {
    document.title = "Original Title";
    const { unmount } = renderHook(() => useDocumentTitle("Reports"));
    expect(document.title).toBe("Reports | CarbonScope");
    unmount();
    expect(document.title).toBe("Original Title");
  });

  it("updates title when prop changes", () => {
    const { rerender } = renderHook(({ title }) => useDocumentTitle(title), {
      initialProps: { title: "Settings" },
    });
    expect(document.title).toBe("Settings | CarbonScope");
    rerender({ title: "Profile" });
    expect(document.title).toBe("Profile | CarbonScope");
  });
});
