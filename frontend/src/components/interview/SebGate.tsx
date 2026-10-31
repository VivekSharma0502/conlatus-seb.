"use client";

/**
 * SebGate.tsx
 *
 * Shown when the candidate visits /interview/[code] outside of Safe Exam Browser.
 * Renders:
 *  - Branded header
 *  - "Open in SEB" deep-link button  (seb:// for local, sebs:// for production)
 *  - Download links for Windows and macOS
 *  - Pre-flight checklist card
 */

import React from "react";
import { motion } from "framer-motion";
import {
  ShieldWarning,
  ArrowSquareOut,
  DownloadSimple,
  CheckCircle,
  Desktop,
  AppleLogo,
  WifiHigh,
  Camera,
  Microphone,
  X,
} from "@phosphor-icons/react";
import brand from "@/lib/brand";

const checklist = [
  {
    icon: X,
    label: "Close all other applications and browser tabs before starting.",
  },
  {
    icon: WifiHigh,
    label: "Connect to a stable, uninterrupted internet connection.",
  },
  {
    icon: Camera,
    label: "Ensure your camera is plugged in and functional.",
  },
  {
    icon: Microphone,
    label: "Ensure your microphone is plugged in and your audio is working.",
  },
];

interface SebGateProps {
  /** The interview code embedded in the URL — kept for display/future use. */
  code: string;
}

export default function SebGate({ code }: SebGateProps) {
  // Build the SEB deep-link.
  // - Use seb:// (plain HTTP) for localhost / 127.0.0.1 development.
  // - Use sebs:// (HTTPS) for every other host (staging, production).
  // The config URL points at the BACKEND (/seb/config.seb), not the frontend.
  // The ?code= query is omitted — the interview code is embedded in the SEB
  // config file's StartURL, not the config download URL.
  const sebHost = brand.sebConfigHost;
  const isLocal =
    sebHost.startsWith("localhost") || sebHost.startsWith("127.0.0.1");
  const scheme = isLocal ? "seb" : "sebs";
  const sebDeepLink = `${scheme}://${sebHost}/seb/config.seb`;

  return (
    <div className="min-h-screen w-full bg-[#050505] text-white flex items-center justify-center p-4 sm:p-6 relative overflow-hidden">
      {/* Background glows */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-violet-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-lg relative z-10 flex flex-col gap-5"
      >
        {/* Brand header */}
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl glass-panel flex items-center justify-center border border-white/10 bg-white/5 p-2 shrink-0">
            <img
              src={brand.logoSrc}
              alt={brand.name}
              className="w-full h-full object-contain"
            />
          </div>
          <div>
            <p className="text-xs font-semibold tracking-widest uppercase text-violet-400">
              {brand.name}
            </p>
            <p className="text-[11px] text-white/40">{brand.tagline}</p>
          </div>
        </div>

        {/* Main warning card */}
        <div className="w-full border border-white/10 glass-panel shadow-2xl rounded-3xl p-8 sm:p-10 flex flex-col gap-6">
          {/* Icon + heading */}
          <div className="flex flex-col items-center text-center gap-3">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
              <ShieldWarning size={32} weight="duotone" className="text-amber-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">
                Safe Exam Browser Required
              </h1>
              <p className="text-sm text-white/50 mt-1 max-w-xs mx-auto">
                Your interview must be taken inside{" "}
                <span className="text-white/70 font-medium">
                  Safe Exam Browser (SEB)
                </span>
                . Please open the link below or install SEB first.
              </p>
            </div>
          </div>

          {/* Open in SEB button */}
          <a
            href={sebDeepLink}
            className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-sm font-semibold text-white transition-all shadow-lg shadow-violet-600/25 active:scale-[0.98] flex items-center justify-center gap-2"
          >
            <ArrowSquareOut size={18} weight="bold" />
            Open in Safe Exam Browser
          </a>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-white/8" />
            <span className="text-[11px] text-white/30 font-medium uppercase tracking-widest">
              Don't have SEB?
            </span>
            <div className="flex-1 h-px bg-white/8" />
          </div>

          {/* Download links */}
          <div className="grid grid-cols-2 gap-3">
            <a
              href={brand.seb.windows}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/8 hover:border-white/20 transition-all text-sm font-medium text-white/80"
            >
              <Desktop size={16} className="text-blue-400" />
              Windows
              <DownloadSimple size={13} className="text-white/30 ml-auto" />
            </a>
            <a
              href={brand.seb.macos}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/8 hover:border-white/20 transition-all text-sm font-medium text-white/80"
            >
              <AppleLogo size={16} className="text-white/60" />
              macOS
              <DownloadSimple size={13} className="text-white/30 ml-auto" />
            </a>
          </div>
        </div>

        {/* Pre-flight checklist card */}
        <div className="w-full border border-white/8 rounded-2xl p-5 flex flex-col gap-3 bg-white/3">
          <p className="text-xs font-semibold uppercase tracking-widest text-white/40">
            Before you start — checklist
          </p>
          <ul className="flex flex-col gap-2.5">
            {checklist.map(({ icon: Icon, label }, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <CheckCircle
                  size={16}
                  weight="duotone"
                  className="text-violet-400 shrink-0 mt-0.5"
                />
                <span className="text-xs text-white/60 leading-relaxed">
                  {label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </motion.div>
    </div>
  );
}

