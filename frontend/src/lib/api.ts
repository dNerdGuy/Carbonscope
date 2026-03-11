/** Typed API client for the CarbonScope backend. */

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// ── Shared types ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ── Auth ────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  company_id: string;
  role: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export async function register(data: {
  email: string;
  password: string;
  full_name: string;
  company_name: string;
  industry: string;
  region?: string;
}): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function login(email: string, password: string): Promise<Token> {
  return request<Token>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getProfile(): Promise<User> {
  return request<User>("/auth/me");
}

export async function updateProfile(data: {
  full_name?: string;
  email?: string;
}): Promise<User> {
  return request<User>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  return request<void>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export async function refreshToken(): Promise<Token> {
  return request<Token>("/auth/refresh", { method: "POST" });
}

// ── Company ─────────────────────────────────────────────────────────

export interface Company {
  id: string;
  name: string;
  industry: string;
  region: string;
  employee_count: number | null;
  revenue_usd: number | null;
  created_at: string;
}

export async function getCompany(): Promise<Company> {
  return request<Company>("/company");
}

export async function updateCompany(
  data: Partial<Omit<Company, "id" | "created_at">>,
): Promise<Company> {
  return request<Company>("/company", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ── Data uploads ────────────────────────────────────────────────────

export interface DataUpload {
  id: string;
  company_id: string;
  year: number;
  provided_data: Record<string, unknown>;
  notes: string | null;
  created_at: string;
}

export async function uploadData(data: {
  year: number;
  provided_data: Record<string, unknown>;
  notes?: string;
}): Promise<DataUpload> {
  return request<DataUpload>("/data", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listDataUploads(params?: {
  year?: number;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<DataUpload>> {
  const q = new URLSearchParams();
  if (params?.year != null) q.set("year", String(params.year));
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request<PaginatedResponse<DataUpload>>(`/data${qs ? `?${qs}` : ""}`);
}

export async function getUploadById(id: string): Promise<DataUpload> {
  return request<DataUpload>(`/data/${encodeURIComponent(id)}`);
}

export async function patchUpload(
  id: string,
  data: {
    year?: number;
    provided_data?: Record<string, unknown>;
    notes?: string;
  },
): Promise<DataUpload> {
  return request<DataUpload>(`/data/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteUpload(id: string): Promise<void> {
  return request<void>(`/data/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ── Estimation & Reports ────────────────────────────────────────────

export interface EmissionReport {
  id: string;
  company_id: string;
  year: number;
  scope1: number;
  scope2: number;
  scope3: number;
  total: number;
  breakdown: Record<string, unknown> | null;
  confidence: number;
  sources: string[] | null;
  assumptions: string[] | null;
  methodology_version: string;
  miner_scores: Record<string, unknown> | null;
  created_at: string;
}

export async function createEstimate(
  dataUploadId: string,
): Promise<EmissionReport> {
  return request<EmissionReport>("/estimate", {
    method: "POST",
    body: JSON.stringify({ data_upload_id: dataUploadId }),
  });
}

export async function listReports(params?: {
  year?: number;
  confidenceMin?: number;
  sortBy?: "created_at" | "year" | "total" | "confidence";
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<EmissionReport>> {
  const q = new URLSearchParams();
  if (params?.year != null) q.set("year", String(params.year));
  if (params?.confidenceMin != null)
    q.set("confidence_min", String(params.confidenceMin));
  if (params?.sortBy) q.set("sort_by", params.sortBy);
  if (params?.order) q.set("order", params.order);
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request<PaginatedResponse<EmissionReport>>(
    `/reports${qs ? `?${qs}` : ""}`,
  );
}

export async function getReport(id: string): Promise<EmissionReport> {
  return request<EmissionReport>(`/reports/${encodeURIComponent(id)}`);
}

export async function deleteReport(id: string): Promise<void> {
  return request<void>(`/reports/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function exportReports(
  format: "csv" | "json" = "csv",
  year?: number,
): Promise<Blob> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const q = new URLSearchParams({ format });
  if (year != null) q.set("year", String(year));
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}/reports/export?${q}`, { headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.blob();
}

// ── Dashboard ───────────────────────────────────────────────────────

export interface DashboardSummary {
  company: Company;
  latest_report: EmissionReport | null;
  reports_count: number;
  data_uploads_count: number;
  year_over_year: {
    year: number;
    scope1: number;
    scope2: number;
    scope3: number;
    total: number;
  }[];
}

export async function getDashboard(): Promise<DashboardSummary> {
  return request<DashboardSummary>("/dashboard");
}

// ── AI / Parsing ────────────────────────────────────────────────────

export async function parseText(
  text: string,
): Promise<{ extracted_data: Record<string, unknown> }> {
  return request("/ai/parse-text", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export interface Prediction {
  predictions: Record<string, number>;
  method: string;
  uncertainty: { low: number; mid: number; high: number };
  filled_categories: string[];
  confidence_adjustment: number;
}

export async function predict(
  knownData: Record<string, unknown>,
  industry?: string,
): Promise<Prediction> {
  return request<Prediction>("/ai/predict", {
    method: "POST",
    body: JSON.stringify({ known_data: knownData, industry }),
  });
}

export async function getAuditTrail(
  reportId: string,
): Promise<{ audit_trail: string }> {
  return request("/ai/audit-trail", {
    method: "POST",
    body: JSON.stringify({ report_id: reportId }),
  });
}

export interface Recommendation {
  id: string;
  scope: number;
  category: string;
  title: string;
  description: string;
  co2_reduction_tco2e: number;
  reduction_percentage: number;
  annual_cost_usd: { min: number; max: number };
  cost_tier: string;
  payback_years: number;
  difficulty: string;
  co_benefits: string[];
  priority_score: number;
}

export interface RecommendationSummary {
  recommendations: Recommendation[];
  summary: {
    total_reduction_tco2e: number;
    total_reduction_pct: number;
    annual_cost_range_usd: { min: number; max: number };
    recommendation_count: number;
    quick_wins: number;
  };
}

export async function getRecommendations(
  reportId: string,
): Promise<RecommendationSummary> {
  return request<RecommendationSummary>(
    `/ai/recommendations/${encodeURIComponent(reportId)}`,
  );
}

// ── Supply Chain ────────────────────────────────────────────────────

export interface SupplyChainLink {
  id: string;
  buyer_company_id: string;
  supplier_company_id: string;
  spend_usd: number | null;
  category: string;
  status: string;
  notes: string | null;
  created_at: string;
}

export async function addSupplier(data: {
  supplier_company_id: string;
  spend_usd?: number;
  category?: string;
  notes?: string;
}): Promise<SupplyChainLink> {
  return request<SupplyChainLink>("/supply-chain/links", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface SupplierEntry {
  link_id: string;
  company_id: string;
  company_name: string;
  industry: string;
  region: string;
  spend_usd: number | null;
  category: string;
  status: string;
  emissions: {
    scope1: number | null;
    scope2: number | null;
    total: number | null;
    confidence: number | null;
    year: number | null;
  } | null;
  created_at: string;
}

export async function listSuppliers(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<SupplierEntry>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/supply-chain/suppliers${qs ? `?${qs}` : ""}`);
}

export interface BuyerEntry {
  link_id: string;
  company_id: string;
  company_name: string;
  industry: string;
  spend_usd: number | null;
  category: string;
  status: string;
  created_at: string;
}

export async function listBuyers(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<BuyerEntry>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/supply-chain/buyers${qs ? `?${qs}` : ""}`);
}

export async function getScope3FromSuppliers(year?: number): Promise<{
  scope3_cat1_from_suppliers: number;
  supplier_count: number;
  verified_count: number;
  coverage_pct: number;
  details: Array<Record<string, unknown>>;
}> {
  const q = year ? `?year=${year}` : "";
  return request(`/supply-chain/scope3-from-suppliers${q}`);
}

export async function updateSupplyChainLink(
  linkId: string,
  status: string,
): Promise<SupplyChainLink> {
  return request<SupplyChainLink>(
    `/supply-chain/links/${encodeURIComponent(linkId)}`,
    { method: "PATCH", body: JSON.stringify({ status }) },
  );
}

export async function deleteSupplyChainLink(linkId: string): Promise<void> {
  return request(`/supply-chain/links/${encodeURIComponent(linkId)}`, {
    method: "DELETE",
  });
}

// ── Compliance ──────────────────────────────────────────────────────

export async function generateComplianceReport(
  reportId: string,
  framework: "ghg_protocol" | "cdp" | "tcfd" | "sbti",
): Promise<Record<string, unknown>> {
  return request("/compliance/report", {
    method: "POST",
    body: JSON.stringify({ report_id: reportId, framework }),
  });
}

// ── Webhooks ────────────────────────────────────────────────────────

export interface WebhookConfig {
  id: string;
  company_id: string;
  url: string;
  event_types: string[];
  active: boolean;
  created_at: string;
}

export interface WebhookCreateResponse extends WebhookConfig {
  secret: string;
}

export async function createWebhook(data: {
  url: string;
  event_types: string[];
}): Promise<WebhookCreateResponse> {
  return request<WebhookCreateResponse>("/webhooks/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listWebhooks(): Promise<WebhookConfig[]> {
  return request<WebhookConfig[]>("/webhooks/");
}

export async function toggleWebhook(
  id: string,
  active: boolean,
): Promise<WebhookConfig> {
  return request<WebhookConfig>(`/webhooks/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ active }),
  });
}

export async function deleteWebhook(id: string): Promise<void> {
  return request(`/webhooks/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ── Questionnaires ──────────────────────────────────────────────────

export interface QuestionnaireOut {
  id: string;
  company_id: string;
  title: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  status: string;
  created_at: string;
  updated_at: string | null;
}

export interface QuestionOut {
  id: string;
  questionnaire_id: string;
  question_number: number;
  question_text: string;
  category: string | null;
  ai_draft_answer: string | null;
  human_answer: string | null;
  status: string;
  confidence: number | null;
  created_at: string;
}

export interface QuestionnaireDetail {
  questionnaire: QuestionnaireOut;
  questions: QuestionOut[];
}

export async function uploadQuestionnaire(
  file: File,
): Promise<QuestionnaireOut> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const formData = new FormData();
  formData.append("file", file);
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}/questionnaires/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json();
}

export async function listQuestionnaires(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<QuestionnaireOut>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/questionnaires/${qs ? `?${qs}` : ""}`);
}

export async function getQuestionnaire(
  id: string,
): Promise<QuestionnaireDetail> {
  return request<QuestionnaireDetail>(
    `/questionnaires/${encodeURIComponent(id)}`,
  );
}

export async function extractQuestions(
  id: string,
): Promise<QuestionnaireDetail> {
  return request<QuestionnaireDetail>(
    `/questionnaires/${encodeURIComponent(id)}/extract`,
    { method: "POST" },
  );
}

export async function updateQuestion(
  questionnaireId: string,
  questionId: string,
  data: { human_answer?: string; status?: string },
): Promise<QuestionOut> {
  return request<QuestionOut>(
    `/questionnaires/${encodeURIComponent(questionnaireId)}/questions/${encodeURIComponent(questionId)}`,
    { method: "PATCH", body: JSON.stringify(data) },
  );
}

export async function deleteQuestionnaire(id: string): Promise<void> {
  return request<void>(`/questionnaires/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function exportQuestionnairePdf(id: string): Promise<Blob> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(
    `${BASE}/questionnaires/${encodeURIComponent(id)}/export/pdf`,
    { headers },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.blob();
}

export async function exportReportPdf(id: string): Promise<Blob> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(
    `${BASE}/reports/${encodeURIComponent(id)}/export/pdf`,
    { headers },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.blob();
}

export interface TemplateSummary {
  id: string;
  title: string;
  description: string;
  framework: string;
  question_count: number;
}

export async function listTemplates(): Promise<TemplateSummary[]> {
  return request<TemplateSummary[]>("/questionnaires/templates/");
}

export async function applyTemplate(
  templateId: string,
): Promise<QuestionnaireDetail> {
  return request<QuestionnaireDetail>(
    `/questionnaires/templates/${encodeURIComponent(templateId)}/apply`,
    { method: "POST" },
  );
}

// ── What-if Scenarios ───────────────────────────────────────────────

export interface ScenarioOut {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  base_report_id: string;
  parameters: Record<string, unknown>;
  results: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string | null;
}

export async function createScenario(data: {
  name: string;
  description?: string;
  base_report_id: string;
  parameters: Record<string, unknown>;
}): Promise<ScenarioOut> {
  return request<ScenarioOut>("/scenarios/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listScenarios(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<ScenarioOut>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/scenarios/${qs ? `?${qs}` : ""}`);
}

export async function getScenario(id: string): Promise<ScenarioOut> {
  return request<ScenarioOut>(`/scenarios/${encodeURIComponent(id)}`);
}

export async function computeScenario(id: string): Promise<ScenarioOut> {
  return request<ScenarioOut>(
    `/scenarios/${encodeURIComponent(id)}/compute`,
    { method: "POST" },
  );
}

export async function deleteScenario(id: string): Promise<void> {
  return request<void>(`/scenarios/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
