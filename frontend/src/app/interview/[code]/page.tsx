"use client";

import React, { use, useEffect, useState } from "react";
import CandidateInterviewPage from "../page";
import SebGate from "@/components/interview/SebGate";
import { isSEB } from "@/lib/seb";

export default function CandidateDirectCodePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const resolvedParams = use(params);
  const code = resolvedParams?.code || "";

  // isSEB() reads navigator.userAgent — only available client-side.
  // Start as null (unknown) to avoid a flash on either branch.
  const [sebDetected, setSebDetected] = useState<boolean | null>(null);

  useEffect(() => {
    // isSEB() logs navigator.userAgent to the console automatically.
    setSebDetected(isSEB());
  }, []);

  // While hydrating, render nothing visible to avoid layout shift.
  if (sebDetected === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#050505]" />
    );
  }

  // Not running inside SEB → show the branded gate page.
  if (!sebDetected) {
    return <SebGate code={code} />;
  }

  // Running inside SEB → proceed to the normal interview flow.
  return <CandidateInterviewPage initialCode={code} />;
}
