import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Skeleton,
  CardSkeleton,
  TableSkeleton,
  PageSkeleton,
} from "@/components/Skeleton";

describe("Skeleton", () => {
  it("renders with aria-hidden", () => {
    const { container } = render(<Skeleton className="h-4 w-full" />);
    const el = container.firstChild as HTMLElement;
    expect(el).toHaveAttribute("aria-hidden", "true");
  });

  it("applies custom className", () => {
    const { container } = render(<Skeleton className="h-8 w-1/2" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("h-8");
    expect(el.className).toContain("w-1/2");
  });

  it("has pulse animation class", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("animate-pulse");
  });
});

describe("CardSkeleton", () => {
  it("renders skeleton lines", () => {
    const { container } = render(<CardSkeleton />);
    const skeletons = container.querySelectorAll("[aria-hidden='true']");
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
  });
});

describe("TableSkeleton", () => {
  it("renders correct number of rows", () => {
    const { container } = render(<TableSkeleton rows={3} />);
    // 1 header + 3 rows = 4 skeleton elements
    const skeletons = container.querySelectorAll("[aria-hidden='true']");
    expect(skeletons.length).toBe(4);
  });

  it("defaults to 5 rows", () => {
    const { container } = render(<TableSkeleton />);
    const skeletons = container.querySelectorAll("[aria-hidden='true']");
    expect(skeletons.length).toBe(6); // 1 header + 5
  });
});

describe("PageSkeleton", () => {
  it("renders header and card skeletons", () => {
    const { container } = render(<PageSkeleton />);
    const skeletons = container.querySelectorAll("[aria-hidden='true']");
    expect(skeletons.length).toBeGreaterThan(5);
  });
});
