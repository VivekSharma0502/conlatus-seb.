"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Key,
  User,
  Envelope,
  Buildings,
  Clock,
  Sparkle,
  ArrowRight,
  CircleNotch,
  WarningCircle,
  CheckCircle,
  Timer,
  ProhibitInset,
} from "@phosphor-icons/react";
import SpecularContainer from "@/components/SpecularContainer";
import InterviewRoom from "@/components/interview/InterviewRoom";
import brand from "@/lib/brand";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

interface InterviewDetails {
  interview_id: string;
  role_title: string;
  company_name: string;
  duration_minutes: number;
  is_valid: boolean;
}

interface ActiveSession {
  interviewId: string;
  candidateName: string;
  candidateEmail: string;
  roleTitle: string;
  companyName: string;
  durationMinutes: number;
  token: string;
}

/** Classify a backend error string into a user-friendly message + severity. */
function classifyCodeError(detail: string): {
  message: string;
  kind: "invalid" | "expired" | "used" | "generic";
} {
  const d = detail.toLowerCase();
  if (d.includes("expir")) {
    return {
      message:
        "This interview link has expired. Please contact your recruiter for a new link.",
      kind: "expired",
    };
  }
  if (
    d.includes("already") ||
    d.includes("complet") ||
    d.includes("used") ||
    d.includes("started")
  ) {
    return {
      message:
        "This interview has already been completed. Each link is single-use.",
      kind: "used",
    };
  }
  if (
    d.includes("not found") ||
    d.includes("invalid") ||
    d.includes("no interview")
  ) {
    return {
      message: "Invalid access code. Please check the link you were sent.",
      kind: "invalid",
    };
  }
  return { message: detail, kind: "generic" };
}

// ─── Error badge icons ────────────────────────────────────────────────────────

function CodeErrorIcon({ kind }: { kind: "invalid" | "expired" | "used" | "generic" }) {
  if (kind === "expired") return <Timer size={12} weight="fill" />;
  if (kind === "used") return <ProhibitInset size={12} weight="fill" />;
  return <WarningCircle size={12} weight="fill" />;
}

// ─── Root export ─────────────────────────────────────────────────────────────

export default function CandidateInterviewPage({
  initialCode: propCode,
}: { initialCode?: string } = {}) {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center text-white bg-[#050505]">
          <CircleNotch size={24} className="animate-spin text-violet-400" />
        </div>
      }
    >
      <CandidatePortalContent propCode={propCode} />
    </Suspense>
  );
}

// ─── Main content ─────────────────────────────────────────────────────────────

function CandidatePortalContent({ propCode }: { propCode?: string }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialCode =
    propCode ||
    searchParams.get("code") ||
    searchParams.get("id") ||
    "";

  const [code, setCode] = useState(initialCode);
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");

  const [details, setDetails] = useState<InterviewDetails | null>(null);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);
  const [codeError, setCodeError] = useState<{
    message: string;
    kind: "invalid" | "expired" | "used" | "generic";
  } | null>(null);

  const [isJoining, setIsJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null);

  // ── Auto-verify code with debounce ──────────────────────────────────────────
  useEffect(() => {
    if (!code || code.trim().length < 3) {
      setDetails(null);
      setCodeError(null);
      return;
    }

    const timer = setTimeout(async () => {
      setIsVerifyingCode(true);
      setCodeError(null);
      try {
        const res = await fetch(
          `${API_BASE_URL}/interview/details/${encodeURIComponent(code.trim())}`,
          {
            referrerPolicy: "unsafe-url",
          }
        );
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          const detail: string =
            err.detail || "Interview access code is invalid or expired.";
          throw new Error(detail);
        }
        const data = await res.json();
        setDetails(data);
      } catch (err: any) {
        setDetails(null);
        setCodeError(classifyCodeError(err.message || "Invalid interview code"));
      } finally {
        setIsVerifyingCode(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [code]);

  // ── Join handler ─────────────────────────────────────────────────────────────
  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || !candidateName.trim() || !candidateEmail.trim()) {
      setJoinError("Please fill out all required fields.");
      return;
    }

    setIsJoining(true);
    setJoinError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/interview/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        referrerPolicy: "unsafe-url",
        body: JSON.stringify({
          interview_code: code.trim(),
          candidate_name: candidateName.trim(),
          candidate_email: candidateEmail.trim(),
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          err.detail || "Failed to join interview. Please check your credentials."
        );
      }

      const data = await res.json();
      localStorage.setItem("interview_token", data.access_token);
      localStorage.setItem("interview_code", code.trim());

      setActiveSession({
        interviewId: data.interview_id,
        candidateName: data.candidate_name,
        candidateEmail: data.candidate_email,
        roleTitle: data.role_title,
        companyName: data.company_name,
        durationMinutes: data.duration_minutes,
        token: data.access_token,
      });
    } catch (err: any) {
      setJoinError(err.message || "Unable to join session. Please try again.");
    } finally {
      setIsJoining(false);
    }
  };

  // ── Active session → full interview room ──────────────────────────────────
  if (activeSession) {
    return (
      <InterviewRoom
        interviewId={activeSession.interviewId}
        candidateName={activeSession.candidateName}
        candidateEmail={activeSession.candidateEmail}
        initialRoleTitle={activeSession.roleTitle}
        initialCompanyName={activeSession.companyName}
        durationMinutes={activeSession.durationMinutes}
        token={activeSession.token}
        onExit={() => setActiveSession(null)}
      />
    );
  }

  // ── Portal form ───────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen w-full bg-[#050505] text-white flex items-center justify-center p-4 sm:p-6 relative overflow-hidden">
      {/* Background glows */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-violet-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-xl relative z-10 flex flex-col gap-6">
        <SpecularContainer
          radius={28}
          tintOpacity={0.03}
          className="w-full border border-white/10 glass-panel shadow-2xl"
          contentClassName="p-8 sm:p-10 flex flex-col"
        >
          {/* ── Brand header ── */}
          <div className="flex items-center gap-3 mb-6">
            <div className="w-11 h-11 rounded-2xl glass-panel flex items-center justify-center border border-white/10 bg-white/5 p-2 shrink-0">
              <img
                src={brand.logoSrc}
                alt={brand.name}
                className="w-full h-full object-contain"
              />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">
                Candidate Interview Portal
              </h1>
              <p className="text-xs text-white/45">
                {brand.name} · Enter your access code to begin.
              </p>
            </div>
          </div>

          {/* ── Form ── */}
          <form onSubmit={handleJoin} className="flex flex-col gap-5">
            {/* Access code */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-white/70 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Key size={14} className="text-violet-400" />
                  Interview Access Code
                </span>
                {isVerifyingCode && (
                  <span className="text-[10px] text-white/40 flex items-center gap-1">
                    <CircleNotch size={10} className="animate-spin" />
                    Verifying…
                  </span>
                )}
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="e.g. 9a78f23c-83b6-4ac4 or DEMO"
                  className={`w-full bg-black/40 border rounded-xl px-4 py-3 text-sm text-white font-mono placeholder:font-sans placeholder-white/30 focus:outline-none transition-all ${
                    details
                      ? "border-violet-500/50 ring-1 ring-violet-500/30"
                      : codeError
                      ? "border-red-500/50"
                      : "border-white/10 focus:border-white/30"
                  }`}
                  required
                />
                {details && (
                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2 text-violet-400">
                    <CheckCircle size={18} weight="fill" />
                  </div>
                )}
              </div>

              {/* Classified error message */}
              <AnimatePresence>
                {codeError && (
                  <motion.p
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="text-[11px] text-red-400 flex items-start gap-1 mt-0.5"
                  >
                    <span className="mt-[1px] shrink-0">
                      <CodeErrorIcon kind={codeError.kind} />
                    </span>
                    {codeError.message}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>

            {/* Validated details banner */}
            <AnimatePresence>
              {details && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="bg-violet-500/10 border border-violet-500/25 rounded-xl p-4 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-violet-300 font-semibold text-sm">
                      <Buildings size={16} />
                      <span>{details.company_name}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-white/60 bg-black/40 px-2.5 py-1 rounded-lg border border-white/5">
                      <Clock size={14} className="text-violet-400" />
                      <span>{details.duration_minutes} mins</span>
                    </div>
                  </div>
                  <p className="text-xs text-white/80">
                    Position:{" "}
                    <strong className="text-white font-medium">
                      {details.role_title}
                    </strong>
                  </p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Candidate name */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-white/70 flex items-center gap-1.5">
                <User size={14} className="text-white/40" />
                Full Name
              </label>
              <input
                type="text"
                value={candidateName}
                onChange={(e) => setCandidateName(e.target.value)}
                placeholder="e.g. Jane Doe"
                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 transition-all"
                required
              />
            </div>

            {/* Candidate email */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-white/70 flex items-center gap-1.5">
                <Envelope size={14} className="text-white/40" />
                Email Address
              </label>
              <input
                type="email"
                value={candidateEmail}
                onChange={(e) => setCandidateEmail(e.target.value)}
                placeholder="e.g. jane@example.com"
                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 transition-all"
                required
              />
            </div>

            {/* Join error */}
            {joinError && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center gap-2">
                <WarningCircle size={16} weight="fill" className="shrink-0" />
                <span>{joinError}</span>
              </div>
            )}

            {/* Pre-flight tip */}
            <div className="p-3.5 rounded-xl bg-white/5 border border-white/10 text-xs text-white/60 flex items-start gap-2.5">
              <Sparkle size={16} className="text-violet-400 shrink-0 mt-0.5" />
              <span>
                Please ensure you are in a quiet room with your camera and
                microphone ready. The interview uses real-time voice speech
                analysis.
              </span>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isJoining || !!codeError || !details}
              className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-sm font-semibold text-white transition-all shadow-lg shadow-violet-600/25 active:scale-[0.98] flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {isJoining ? (
                <span className="flex items-center gap-2">
                  <CircleNotch size={16} className="animate-spin" />
                  Verifying &amp; Connecting…
                </span>
              ) : (
                <span className="flex items-center gap-2 font-semibold">
                  Start Technical Interview <ArrowRight size={16} />
                </span>
              )}
            </button>
          </form>
        </SpecularContainer>

        {/* Footer */}
        <p className="text-center text-[11px] text-white/20">
          {brand.name} · Secure AI Interview Platform
        </p>
      </div>
    </div>
  );
}
