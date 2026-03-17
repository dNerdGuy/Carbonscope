/** Typed API client for the CarbonScope backend. */

const BASE = "/api/v1";
const RETRY_MAX_ATTEMPTS = 3;
const RETRY_BASE_DELAY_MS =
  typeof process !== "undefined" && process.env.NODE_ENV === "test" ? 1 : 200;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseRetryAfterMs(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return seconds * 1000;
  const dateMs = Date.parse(value);
  if (!Number.isNaN(dateMs)) {
    const delta = dateMs - Date.now();
    return delta > 0 ? delta : 0;
  }
  return null;
}

function isRetryableStatus(status: number): boolean {
  return status === 429 || status === 502 || status === 503 || status === 504;
}

async function fetchWithRetry(
  input: string,
  init: RequestInit,
): Promise<Response> {
  for (let attempt = 1; attempt <= RETRY_MAX_ATTEMPTS; attempt++) {
    try {
      const res = await fetch(input, init);
      if (!isRetryableStatus(res.status) || attempt === RETRY_MAX_ATTEMPTS) {
        return res;
      }

      const retryAfterMs = parseRetryAfterMs(res.headers.get("Retry-After"));
      const backoff = RETRY_BASE_DELAY_MS * 2 ** (attempt - 1);
      await sleep(retryAfterMs ?? backoff);
      continue;
    } catch (err) {
      if (attempt === RETRY_MAX_ATTEMPTS) {
        throw err;
      }
      const backoff = RETRY_BASE_DELAY_MS * 2 ** (attempt - 1);
      await sleep(backoff);
    }
  }

  // Unreachable, but keeps TS control flow explicit.
  throw new Error("Request retry loop exhausted");
}

function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

/** Prevent multiple concurrent refresh attempts. */
let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) {
    throw new ApiError(401, "Session expired");
  }

  const res = await fetchWithRetry(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError(res.status, "Session expired");
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  if (typeof data.refresh_token === "string" && data.refresh_token.length > 0) {
    localStorage.setItem("refresh_token", data.refresh_token);
  }
  return data.access_token;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Attach CSRF token for mutating requests when using cookie auth
  const csrf = getCsrfToken();
  if (csrf && !token) {
    headers["X-CSRF-Token"] = csrf;
  }

  const res = await fetchWithRetry(`${BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  // Auto-refresh: on 401, try refreshing the token once and retry
  if (res.status === 401 && token && path !== "/auth/refresh") {
    try {
      if (!refreshPromise) refreshPromise = doRefresh();
      const newToken = await refreshPromise;
      refreshPromise = null;
      headers["Authorization"] = `Bearer ${newToken}`;
      const retry = await fetchWithRetry(`${BASE}${path}`, {
        ...init,
        headers,
        credentials: "include",
      });
      if (!retry.ok) {
        const body = await retry.json().catch(() => ({}));
        throw new ApiError(retry.status, body.detail ?? retry.statusText);
      }
      if (retry.status === 204) return undefined as T;
      return retry.json();
    } catch (err) {
      refreshPromise = null;
      // If refresh also failed, clear auth state and notify React
      if (err instanceof ApiError && err.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("user");
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("auth:session-expired"));
        }
      }
      throw err;
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

/**
 * Like `request()` but returns the raw Response for non-JSON bodies (blobs,
 * file uploads). Uses `fetchWithRetry`, attaches auth & CSRF headers.
 */
async function rawRequest(path: string, init?: RequestInit): Promise<Response> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const csrf = getCsrfToken();
  if (csrf && !token) {
    headers["X-CSRF-Token"] = csrf;
  }

  const res = await fetchWithRetry(`${BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  // Auto-refresh: on 401, try refreshing the token once and retry
  if (res.status === 401 && token && path !== "/auth/refresh") {
    try {
      if (!refreshPromise) refreshPromise = doRefresh();
      const newToken = await refreshPromise;
      refreshPromise = null;
      headers["Authorization"] = `Bearer ${newToken}`;
      const retry = await fetchWithRetry(`${BASE}${path}`, {
        ...init,
        headers,
        credentials: "include",
      });
      if (!retry.ok) {
        const body = await retry.json().catch(() => ({}));
        throw new ApiError(retry.status, body.detail ?? retry.statusText);
      }
      return retry;
    } catch (err) {
      refreshPromise = null;
      if (err instanceof ApiError && err.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("user");
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("auth:session-expired"));
        }
      }
      throw err;
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res;
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
  refresh_token?: string;
  csrf_token?: string | null;
  mfa_required?: boolean;
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

export async function logoutApi(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
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

export async function forgotPassword(email: string): Promise<void> {
  return request<void>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<void> {
  return request<void>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

// ── Audit Logs ──────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  company_id: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: string | null;
  created_at: string;
}

export async function listAuditLogs(params?: {
  limit?: number;
  offset?: number;
  action?: string;
  resource_type?: string;
  user_id?: string;
}): Promise<PaginatedResponse<AuditLogEntry>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  if (params?.action) q.set("action", params.action);
  if (params?.resource_type) q.set("resource_type", params.resource_type);
  if (params?.user_id) q.set("user_id", params.user_id);
  const qs = q.toString();
  return request(`/audit-logs/${qs ? `?${qs}` : ""}`);
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
  const q = new URLSearchParams({ format });
  if (year != null) q.set("year", String(year));
  const res = await rawRequest(`/reports/export?${q}`);
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

export async function listWebhooks(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<WebhookConfig>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/webhooks/${qs ? `?${qs}` : ""}`);
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
  const formData = new FormData();
  formData.append("file", file);
  const res = await rawRequest("/questionnaires/upload", {
    method: "POST",
    body: formData,
  });
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
  const res = await rawRequest(
    `/questionnaires/${encodeURIComponent(id)}/export/pdf`,
  );
  return res.blob();
}

export async function exportReportPdf(id: string): Promise<Blob> {
  const res = await rawRequest(`/reports/${encodeURIComponent(id)}/export/pdf`);
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
  status?: string;
}): Promise<PaginatedResponse<ScenarioOut>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  if (params?.status) q.set("status", params.status);
  const qs = q.toString();
  return request(`/scenarios/${qs ? `?${qs}` : ""}`);
}

export async function getScenario(id: string): Promise<ScenarioOut> {
  return request<ScenarioOut>(`/scenarios/${encodeURIComponent(id)}`);
}

export async function computeScenario(id: string): Promise<ScenarioOut> {
  return request<ScenarioOut>(`/scenarios/${encodeURIComponent(id)}/compute`, {
    method: "POST",
  });
}

export async function deleteScenario(id: string): Promise<void> {
  return request<void>(`/scenarios/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ── Billing & Subscriptions ─────────────────────────────────────────

export interface SubscriptionOut {
  id: string;
  company_id: string;
  plan: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
}

export interface CreditBalanceOut {
  company_id: string;
  balance: number;
  plan: string;
}

export interface PlanLimits {
  monthly_credits: number;
  max_reports_per_month: number;
  max_scenarios: number;
  max_questionnaires: number;
  pdf_export: boolean;
  supply_chain: boolean;
  webhooks: boolean;
  marketplace: boolean;
  price_usd: number;
}

export async function getSubscription(): Promise<SubscriptionOut> {
  return request<SubscriptionOut>("/billing/subscription");
}

export async function changePlan(plan: string): Promise<SubscriptionOut> {
  return request<SubscriptionOut>("/billing/subscription", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export async function getCredits(): Promise<CreditBalanceOut> {
  return request<CreditBalanceOut>("/billing/credits");
}

export interface CreditLedgerEntry {
  id: string;
  amount: number;
  reason: string;
  balance_after: number;
  created_at: string;
}

export async function getCreditLedger(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<CreditLedgerEntry>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/billing/credits/ledger${qs ? `?${qs}` : ""}`);
}

export async function listPlans(): Promise<Record<string, PlanLimits>> {
  return request<Record<string, PlanLimits>>("/billing/plans");
}

// ── Alerts ──────────────────────────────────────────────────────────

export interface AlertOut {
  id: string;
  company_id: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  is_read: boolean;
  acknowledged_at: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export async function listAlerts(params?: {
  unread_only?: boolean;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<AlertOut>> {
  const q = new URLSearchParams();
  if (params?.unread_only != null)
    q.set("unread_only", String(params.unread_only));
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/alerts${qs ? `?${qs}` : ""}`);
}

export async function acknowledgeAlert(id: string): Promise<AlertOut> {
  return request<AlertOut>(`/alerts/${encodeURIComponent(id)}/acknowledge`, {
    method: "POST",
  });
}

export async function triggerAlertCheck(): Promise<AlertOut[]> {
  return request<AlertOut[]>("/alerts/check", { method: "POST" });
}

// ── Marketplace ─────────────────────────────────────────────────────

export interface DataListingOut {
  id: string;
  seller_company_id: string;
  title: string;
  description: string | null;
  data_type: string;
  industry: string;
  region: string;
  year: number;
  price_credits: number;
  anonymized_data: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface DataPurchaseOut {
  id: string;
  listing_id: string;
  buyer_company_id: string;
  price_credits: number;
  listing: DataListingOut;
  created_at: string;
}

export async function createListing(data: {
  title: string;
  description?: string;
  data_type: string;
  report_id: string;
  price_credits: number;
}): Promise<DataListingOut> {
  return request<DataListingOut>("/marketplace/listings", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function browseListings(params?: {
  industry?: string;
  region?: string;
  data_type?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<DataListingOut>> {
  const q = new URLSearchParams();
  if (params?.industry) q.set("industry", params.industry);
  if (params?.region) q.set("region", params.region);
  if (params?.data_type) q.set("data_type", params.data_type);
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/marketplace/listings${qs ? `?${qs}` : ""}`);
}

export async function getListing(id: string): Promise<DataListingOut> {
  return request<DataListingOut>(
    `/marketplace/listings/${encodeURIComponent(id)}`,
  );
}

export async function purchaseListing(id: string): Promise<DataPurchaseOut> {
  return request<DataPurchaseOut>(
    `/marketplace/listings/${encodeURIComponent(id)}/purchase`,
    { method: "POST" },
  );
}

// ── Marketplace Seller ──────────────────────────────────────────────

export async function getMyMarketplaceSales(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<DataPurchaseOut>> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request(`/marketplace/my-sales${qs ? `?${qs}` : ""}`);
}

export interface SellerRevenue {
  total_revenue_credits: number;
  total_sales: number;
  active_listings: number;
}

export async function getMyMarketplaceRevenue(): Promise<SellerRevenue> {
  return request<SellerRevenue>("/marketplace/my-revenue");
}

export async function deleteAccount(): Promise<void> {
  return request("/auth/me", { method: "DELETE" });
}

export async function getSupplyChainLink(
  linkId: string,
): Promise<SupplyChainLink> {
  return request<SupplyChainLink>(
    `/supply-chain/links/${encodeURIComponent(linkId)}`,
  );
}

// ── PCAF (Financed Emissions) ────────────────────────────────────

export interface FinancedPortfolio {
  id: string;
  company_id: string;
  name: string;
  year: number;
  created_at: string;
}

export interface FinancedAsset {
  id: string;
  portfolio_id: string;
  asset_name: string;
  asset_class: string;
  outstanding_amount: number;
  total_equity_debt: number;
  investee_emissions_tco2e: number;
  attribution_factor: number;
  financed_emissions_tco2e: number;
  data_quality_score: number;
  industry: string | null;
  region: string | null;
  notes: string | null;
  created_at: string;
}

export interface PortfolioSummary {
  portfolio: FinancedPortfolio;
  total_financed_emissions: number;
  weighted_data_quality: number;
  asset_count: number;
  by_asset_class: Record<string, number>;
}

export async function listPortfolios(params?: {
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request<{ items: FinancedPortfolio[]; total: number }>(
    `/pcaf/portfolios${qs ? `?${qs}` : ""}`,
  );
}

export async function createPortfolio(data: { name: string; year: number }) {
  return request<FinancedPortfolio>("/pcaf/portfolios", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getPortfolioSummary(portfolioId: string) {
  return request<PortfolioSummary>(
    `/pcaf/portfolios/${encodeURIComponent(portfolioId)}/summary`,
  );
}

export async function listPortfolioAssets(
  portfolioId: string,
  params?: { limit?: number; offset?: number },
) {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request<{ items: FinancedAsset[]; total: number }>(
    `/pcaf/portfolios/${encodeURIComponent(portfolioId)}/assets${qs ? `?${qs}` : ""}`,
  );
}

export async function addPortfolioAsset(
  portfolioId: string,
  data: {
    asset_name: string;
    asset_class: string;
    outstanding_amount: number;
    total_equity_debt: number;
    investee_emissions_tco2e: number;
    data_quality_score: number;
    industry?: string;
    region?: string;
    notes?: string;
  },
) {
  return request<FinancedAsset>(
    `/pcaf/portfolios/${encodeURIComponent(portfolioId)}/assets`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

export async function deletePortfolioAsset(
  portfolioId: string,
  assetId: string,
) {
  return request<void>(
    `/pcaf/portfolios/${encodeURIComponent(portfolioId)}/assets/${encodeURIComponent(assetId)}`,
    {
      method: "DELETE",
    },
  );
}

// ── Data Reviews ─────────────────────────────────────────────────

export interface DataReview {
  id: string;
  report_id: string;
  company_id: string;
  status: string;
  reviewer_id: string | null;
  reviewer_notes: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export async function listReviews(params?: {
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return request<{ items: DataReview[]; total: number }>(
    `/reviews${qs ? `?${qs}` : ""}`,
  );
}

export async function createReview(reportId: string) {
  return request<DataReview>("/reviews", {
    method: "POST",
    body: JSON.stringify({ report_id: reportId }),
  });
}

export async function getReview(reviewId: string) {
  return request<DataReview>(`/reviews/${encodeURIComponent(reviewId)}`);
}

export async function reviewAction(
  reviewId: string,
  action: string,
  notes?: string,
) {
  return request<DataReview>(
    `/reviews/${encodeURIComponent(reviewId)}/action`,
    {
      method: "POST",
      body: JSON.stringify({ action, notes }),
    },
  );
}

// ── MFA ──────────────────────────────────────────────────────────

export interface MFAStatus {
  mfa_enabled: boolean;
}

export interface MFASetup {
  secret: string;
  provisioning_uri: string;
  backup_codes: string[];
}

export async function getMFAStatus() {
  return request<MFAStatus>("/auth/mfa/status");
}

export async function setupMFA() {
  return request<MFASetup>("/auth/mfa/setup", { method: "POST" });
}

export async function verifyMFA(totpCode: string) {
  return request<MFAStatus>("/auth/mfa/verify", {
    method: "POST",
    body: JSON.stringify({ totp_code: totpCode }),
  });
}

export async function validateMFA(totpCode: string) {
  return request<MFAStatus>("/auth/mfa/validate", {
    method: "POST",
    body: JSON.stringify({ totp_code: totpCode }),
  });
}

export async function disableMFA(totpCode: string) {
  return request<void>("/auth/mfa/disable", {
    method: "DELETE",
    body: JSON.stringify({ totp_code: totpCode }),
  });
}

// ── Benchmarks ───────────────────────────────────────────────────

export interface IndustryBenchmark {
  industry: string;
  avg_scope1: number;
  avg_scope2: number;
  avg_scope3: number;
  avg_total: number;
  company_count: number;
  your_total: number | null;
  percentile: number | null;
}

export interface PeerComparison {
  rank: number;
  total_companies: number;
  percentile: number;
  you: { total: number; confidence: number };
  average: number;
  median: number;
  best: number;
}

export async function getIndustryBenchmarks(industry?: string) {
  const params = new URLSearchParams();
  if (industry) params.set("industry", industry);
  const qs = params.toString();
  return request<IndustryBenchmark>(
    `/benchmarks/industry${qs ? `?${qs}` : ""}`,
  );
}

export async function getPeerComparison() {
  return request<PeerComparison>("/benchmarks/peers");
}

/** SSE endpoint URL for real-time events. */
export const SSE_EVENTS_URL = `${BASE}/events/subscribe`;
