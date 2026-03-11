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

export async function listDataUploads(): Promise<DataUpload[]> {
  return request<DataUpload[]>("/data");
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

export async function listReports(year?: number): Promise<EmissionReport[]> {
  const q = year ? `?year=${year}` : "";
  return request<EmissionReport[]>(`/reports${q}`);
}

export async function getReport(id: string): Promise<EmissionReport> {
  return request<EmissionReport>(`/reports/${encodeURIComponent(id)}`);
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

export async function listSuppliers(): Promise<
  Array<{
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
  }>
> {
  return request("/supply-chain/suppliers");
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
  secret: string;
  active: boolean;
  created_at: string;
}

export async function createWebhook(data: {
  url: string;
  event_types: string[];
}): Promise<WebhookConfig> {
  return request<WebhookConfig>("/webhooks/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listWebhooks(): Promise<WebhookConfig[]> {
  return request<WebhookConfig[]>("/webhooks/");
}

export async function deleteWebhook(id: string): Promise<void> {
  return request(`/webhooks/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
