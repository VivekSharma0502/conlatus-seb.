/**
 * brand.ts — Single source of truth for Conlatus branding.
 *
 * Change name, logo, colors, and SEB config host here only.
 * All interview-facing pages import from this file.
 */

const brand = {
  /** Display name shown in headings, titles, and alt text. */
  name: "Conlatus",

  /** Short tagline shown under the logo on candidate-facing pages. */
  tagline: "AI Technical Interview Platform",

  /**
   * Logo path served from /public.
   * Replace /favicon.ico with a proper SVG/PNG when available.
   */
  logoSrc: "/favicon.ico",

  /**
   * Primary accent colour — violet-600 in Tailwind v4 terms.
   * Used for gradients, rings, and icon accents.
   * Keep in sync with --primary in globals.css if you change it.
   */
  primaryColor: "#7c3aed",

  /**
   * Secondary accent — indigo-600.
   * Used as the tail colour in gradient buttons.
   */
  secondaryColor: "#4f46e5",

  /**
   * Host (host:port) of the BACKEND server that serves /seb/config.seb.
   * Set NEXT_PUBLIC_SEB_CONFIG_HOST in frontend/.env.local.
   * Falls back to "localhost:8000" so local dev never silently uses the
   * frontend port.
   *
   * Scheme selection (seb:// vs sebs://) is handled at call-site in SebGate.
   */
  sebConfigHost:
    process.env.NEXT_PUBLIC_SEB_CONFIG_HOST || "localhost:8000",

  /** SEB download links. Update whenever Safe Exam Browser releases a new version. */
  seb: {
    windows: "https://safeexambrowser.org/download_en.html",
    macos: "https://safeexambrowser.org/download_en.html",
  },
} as const;

export default brand;

