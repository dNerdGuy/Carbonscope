import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockReplace = vi.fn();
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  usePathname: () => "/questionnaires",
  useSearchParams: () => new URLSearchParams(),
}));

const mockListQuestionnaires = vi.fn();
const mockListTemplates = vi.fn();
const mockUploadQuestionnaire = vi.fn();
const mockApplyTemplate = vi.fn();
const mockDeleteQuestionnaire = vi.fn();
const mockExtractQuestions = vi.fn();

vi.mock("@/lib/api", () => ({
  listQuestionnaires: (...a: unknown[]) => mockListQuestionnaires(...a),
  listTemplates: (...a: unknown[]) => mockListTemplates(...a),
  uploadQuestionnaire: (...a: unknown[]) => mockUploadQuestionnaire(...a),
  applyTemplate: (...a: unknown[]) => mockApplyTemplate(...a),
  deleteQuestionnaire: (...a: unknown[]) => mockDeleteQuestionnaire(...a),
  extractQuestions: (...a: unknown[]) => mockExtractQuestions(...a),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "u@test.com" }, loading: false }),
}));

vi.mock("@/components/Skeleton", () => ({
  PageSkeleton: () => <div>Loading...</div>,
}));

type ConfirmDialogProps = {
  open: boolean;
  onConfirm: () => void;
  title: string;
};

vi.mock("@/components/ConfirmDialog", () => ({
  default: ({ open, onConfirm, title }: ConfirmDialogProps) =>
    open ? (
      <div data-testid="confirm-dialog">
        <span>{title}</span>
        <button onClick={onConfirm}>Confirm</button>
      </div>
    ) : null,
}));

import QuestionnairesPage from "@/app/questionnaires/page";

const QUESTIONNAIRES = {
  items: [
    {
      id: "q1",
      title: "CDP Report 2024",
      status: "extracted",
      original_filename: "cdp.csv",
      file_type: "csv",
      file_size: 1024,
      created_at: "2024-01-01T00:00:00Z",
    },
  ],
  total: 1,
};

const TEMPLATES = [
  {
    id: "cdp_climate",
    title: "CDP Climate Change Questionnaire",
    description: "Core CDP questions",
    framework: "CDP",
    question_count: 10,
  },
  {
    id: "tcfd_disclosure",
    title: "TCFD Recommended Disclosures",
    description: "TCFD core questions",
    framework: "TCFD",
    question_count: 9,
  },
];

describe("QuestionnairesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListQuestionnaires.mockResolvedValue(QUESTIONNAIRES);
    mockListTemplates.mockResolvedValue(TEMPLATES);
  });

  it("renders heading", async () => {
    render(<QuestionnairesPage />);
    expect(
      await screen.findByText("Sustainability Questionnaires"),
    ).toBeInTheDocument();
  });

  it("shows tabs", async () => {
    render(<QuestionnairesPage />);
    expect(await screen.findByText("My Questionnaires")).toBeInTheDocument();
    expect(screen.getByText("Upload Document")).toBeInTheDocument();
    expect(screen.getByText("Template Library")).toBeInTheDocument();
  });

  it("lists questionnaires", async () => {
    render(<QuestionnairesPage />);
    expect(await screen.findByText("CDP Report 2024")).toBeInTheDocument();
  });

  it("shows templates tab", async () => {
    render(<QuestionnairesPage />);
    fireEvent.click(await screen.findByText("Template Library"));
    expect(
      await screen.findByText("CDP Climate Change Questionnaire"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("TCFD Recommended Disclosures"),
    ).toBeInTheDocument();
  });

  it("shows error on load failure", async () => {
    mockListQuestionnaires.mockRejectedValue(new Error("Network error"));
    mockListTemplates.mockRejectedValue(new Error("Network error"));
    render(<QuestionnairesPage />);
    expect(await screen.findByText("Failed to load data")).toBeInTheDocument();
  });

  it("applies template", async () => {
    mockApplyTemplate.mockResolvedValue({ id: "q2" });
    render(<QuestionnairesPage />);
    fireEvent.click(await screen.findByText("Template Library"));
    const useButtons = await screen.findAllByText("Use Template");
    fireEvent.click(useButtons[0]);
    await waitFor(() => {
      expect(mockApplyTemplate).toHaveBeenCalledWith("cdp_climate");
    });
  });
});
