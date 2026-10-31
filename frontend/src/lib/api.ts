export interface CandidateListItem {
  id: string;
  candidate_name: string;
  candidate_email: string;
  role_title: string;
  company_name: string;
  status: "completed" | "in-progress" | "pending";
  overall_score: number | null;
  recommendation: string | null;
  human_decision: "hired" | "rejected" | "next_round" | "under_review" | null;
  token: string;
  created_at: string;
  completed_at: string | null;
}

export interface CriterionBreakdown {
  score: number;
  weight: number;
  weighted_score: number;
  evidence_count: number;
  description?: string;
}

export interface TranscriptTurn {
  id: string;
  speaker: "interviewer" | "candidate";
  message: string;
  timestamp: string;
  audio_url?: string | null;
}

export interface CandidateDetailResponse {
  id: string;
  candidate_name: string;
  candidate_email: string;
  role_title: string;
  company_name: string;
  status: "completed" | "in-progress" | "pending";
  token: string;
  created_at: string;
  completed_at: string | null;

  report_id?: string | null;
  overall_score: number | null;
  recommendation: string | null;
  summary: string | null;
  rubric_breakdown: Record<string, CriterionBreakdown> | null;
  synthesis_details: {
    strengths?: string[];
    growth_areas?: string[];
    communication?: string;
    flags?: string[];
  } | null;
  human_decision: string | null;
  human_notes: string | null;

  transcripts: TranscriptTurn[];
}

export interface DashboardAlert {
  id: string;
  type: "warning" | "info" | "success" | "alert";
  title: string;
  message: string;
  timestamp: string;
}

export interface AdminOverviewResponse {
  total_interviews: number;
  completed_interviews: number;
  in_progress_interviews: number;
  pending_interviews: number;
  average_score: number;
  pass_rate: number;
  recent_candidates: CandidateListItem[];
  alerts: DashboardAlert[];
}

export interface AdminSettingsPayload {
  model_provider: string;
  model_name: string;
  default_duration: number;
  rubric_threshold: number;
  company_name: string;
  company_logo?: string | null;
  recruiter_email?: string | null;
  email_notifications: boolean;
  alert_on_finish: boolean;
  groq_api_key_configured: boolean;
  anthropic_api_key_configured: boolean;
  openai_api_key_configured: boolean;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(): HeadersInit {
  let token: string | null = null;
  if (typeof window !== "undefined") {
    token =
      localStorage.getItem("access_token") ||
      localStorage.getItem("admin_token");
    if (!token) {
      const match = document.cookie.match(new RegExp("(^| )auth_token=([^;]+)"));
      if (match) token = match[2];
    }
  }

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function handleAuthError(res: Response) {
  if (res.status === 401 && typeof window !== "undefined") {
    // Clear invalid or stale admin credentials
    localStorage.removeItem("access_token");
    localStorage.removeItem("admin_token");
    document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    
    // Redirect to login if currently on an admin page
    if (window.location.pathname.startsWith("/admin") && !window.location.pathname.startsWith("/admin/login")) {
      const redirectUrl = `/admin/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      window.location.href = redirectUrl;
    }
  }
}

export async function fetchAdminOverview(): Promise<AdminOverviewResponse> {
  const res = await fetch(`${API_BASE_URL}/admin/overview`, {
    headers: getAuthHeaders(),
    referrerPolicy: "unsafe-url",
  });
  if (!res.ok) {
    handleAuthError(res);
    throw new Error(`Failed to load admin overview: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchCandidates(
  search?: string,
  status?: string
): Promise<CandidateListItem[]> {
  const params = new URLSearchParams();
  if (search && search.trim()) params.set("search", search.trim());
  if (status && status !== "all") params.set("status", status);

  const url = `${API_BASE_URL}/admin/candidates?${params.toString()}`;
  const res = await fetch(url, {
    headers: getAuthHeaders(),
    referrerPolicy: "unsafe-url",
  });
  if (!res.ok) {
    handleAuthError(res);
    throw new Error(`Failed to fetch candidates: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchCandidateDetail(
  id: string
): Promise<CandidateDetailResponse> {
  const res = await fetch(`${API_BASE_URL}/admin/candidates/${id}`, {
    headers: getAuthHeaders(),
    referrerPolicy: "unsafe-url",
  });
  if (!res.ok) {
    handleAuthError(res);
    throw new Error(`Failed to fetch candidate details: ${res.statusText}`);
  }
  return res.json();
}

export async function submitCandidateDecision(
  id: string,
  decision: string,
  notes?: string
): Promise<{ status: string; human_decision: string; human_notes: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/candidates/${id}/decision`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ decision, notes }),
    referrerPolicy: "unsafe-url",
  });
  if (!res.ok) {
    handleAuthError(res);
    throw new Error(`Failed to submit recruiter decision: ${res.statusText}`);
  }
  return res.json();
}

export async function retriggerCandidateReport(
  id: string
): Promise<{ status: string; report_id?: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/candidates/${id}/retrigger`, {
    method: "POST",
    headers: getAuthHeaders(),
    referrerPolicy: "unsafe-url",
  });
  if (!res.ok) {
    handleAuthError(res);
    throw new Error(`Failed to re-trigger candidate report: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAdminSettings(): Promise<AdminSettingsPayload> {
  const res = await fetch(`${API_BASE_URL}/admin/settings`, {
    headers: getAuthHeaders(),
    referrerPolicy: "unsafe-url",
  });
  if (!res.ok) {
    handleAuthError(res);
    throw new Error(`Failed to load admin settings: ${res.statusText}`);
  }
  return res.json();
}

export async function updateAdminSettings(
  payload: AdminSettingsPayload
): Promise<AdminSettingsPayload> {
  const res = await fetch(`${API_BASE_URL}/admin/settings`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
    referrerPolicy: "unsafe-url",
  });
  if (!res.ok) {
    throw new Error(`Failed to update settings: ${res.statusText}`);
  }
  return res.json();
}
