import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable, type Column } from "@/components/DataTable";

interface TestRow {
  id: string;
  name: string;
  value: number;
  [key: string]: unknown;
}

const columns: Column<TestRow>[] = [
  { key: "name", header: "Name" },
  { key: "value", header: "Value" },
];

const sampleData: TestRow[] = [
  { id: "1", name: "Alpha", value: 10 },
  { id: "2", name: "Beta", value: 20 },
  { id: "3", name: "Gamma", value: 30 },
];

describe("DataTable", () => {
  it("renders column headers in desktop table", () => {
    render(<DataTable columns={columns} data={[]} />);
    const ths = document.querySelectorAll("th");
    const headers = Array.from(ths).map((th) => th.textContent);
    expect(headers).toContain("Name");
    expect(headers).toContain("Value");
  });

  it("renders empty message when no data", () => {
    render(
      <DataTable columns={columns} data={[]} emptyMessage="Nothing here" />,
    );
    const matches = screen.getAllByText("Nothing here");
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it("renders default empty message", () => {
    render(<DataTable columns={columns} data={[]} />);
    const matches = screen.getAllByText("No data found.");
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it("renders data rows", () => {
    render(<DataTable columns={columns} data={sampleData} />);
    // Both desktop table and mobile cards render data
    expect(screen.getAllByText("Alpha").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("20").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Gamma").length).toBeGreaterThanOrEqual(1);
  });

  it("renders mobile card layout with field labels", () => {
    render(<DataTable columns={columns} data={sampleData} />);
    // Mobile cards render column headers as labels per row
    const nameLabels = screen.getAllByText("Name");
    // 1 in <th> + 3 in cards = 4
    expect(nameLabels.length).toBe(4);
  });

  it("shows loading state", () => {
    render(<DataTable columns={columns} data={[]} loading />);
    const rows = document.querySelectorAll("[role='status']");
    expect(rows.length).toBeGreaterThan(0);
  });

  it("renders custom column renderer", () => {
    const cols: Column<TestRow>[] = [
      { key: "name", header: "Name" },
      {
        key: "value",
        header: "Value",
        render: (row) => <strong>{row.value * 2}</strong>,
      },
    ];
    render(<DataTable columns={cols} data={sampleData} />);
    expect(screen.getAllByText("20").length).toBeGreaterThanOrEqual(1); // 10 * 2
    expect(screen.getAllByText("60").length).toBeGreaterThanOrEqual(1); // 30 * 2
  });

  it("renders pagination controls", () => {
    render(
      <DataTable
        columns={columns}
        data={sampleData.slice(0, 2)}
        total={3}
        limit={2}
        offset={0}
        onPageChange={() => {}}
      />,
    );
    expect(screen.getByText("Page 1 of 2 (3 items)")).toBeInTheDocument();
    const prevButtons = screen.getAllByRole("button", { name: "Previous" });
    const nextButtons = screen.getAllByRole("button", { name: "Next" });
    expect(prevButtons[0]).toBeDisabled();
    expect(nextButtons[0]).toBeEnabled();
  });

  it("calls onPageChange when clicking Next", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={sampleData.slice(0, 2)}
        total={3}
        limit={2}
        offset={0}
        onPageChange={onPageChange}
      />,
    );
    await user.click(screen.getAllByRole("button", { name: "Next" })[0]);
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("disables Next on last page", () => {
    render(
      <DataTable
        columns={columns}
        data={sampleData.slice(2)}
        total={3}
        limit={2}
        offset={2}
        onPageChange={() => {}}
      />,
    );
    expect(screen.getAllByRole("button", { name: "Next" })[0]).toBeDisabled();
    expect(
      screen.getAllByRole("button", { name: "Previous" })[0],
    ).toBeEnabled();
  });

  it("does not render pagination when total fits in one page", () => {
    render(
      <DataTable
        columns={columns}
        data={sampleData}
        total={3}
        limit={10}
        offset={0}
        onPageChange={() => {}}
      />,
    );
    expect(screen.queryByText("Previous")).not.toBeInTheDocument();
  });
});
