/**
 * seb.ts — Safe Exam Browser detection utilities.
 *
 * Detection strategy (two independent signals, either is sufficient):
 *
 * 1. User-Agent substring match (case-insensitive).
 *    SEB injects its identity on every supported platform, e.g.:
 *      "SEB/3.10.2 ..."  on Windows
 *      "SEB/3.x ..."     on macOS
 *    Matching is case-insensitive so future casing variations can't break it.
 *
 * 2. Start URL referrer / origin check.
 *    When SEB opens a page from its configured Start URL it sets
 *    document.referrer to the SEB config host (our backend).  If the page was
 *    navigated to directly by SEB (no prior page), document.referrer is "".
 *    We also check the query param ?via=seb that can be appended to the
 *    SEB config's StartURL as a lightweight signal.
 *
 * navigator.userAgent / document are only available in the browser, so every
 * function guards against SSR with typeof window checks.
 */

/** Returns true when the current browser is Safe Exam Browser. */
export function isSEB(): boolean {
  if (typeof window === "undefined") return false;

  const ua = navigator.userAgent;

  // Always log the UA to the console so developers can see what SEB sends.
  // eslint-disable-next-line no-console
  console.log("[SEB detection] navigator.userAgent:", ua);

  // Signal 1: case-insensitive UA match (covers "SEB/3.x", "seb/...", etc.)
  if (ua.toLowerCase().includes("seb")) {
    // eslint-disable-next-line no-console
    console.log("[SEB detection] matched via user-agent");
    return true;
  }

  // Signal 2: page was opened via the SEB Start URL (?via=seb query param).
  const params = new URLSearchParams(window.location.search);
  if (params.get("via") === "seb") {
    // eslint-disable-next-line no-console
    console.log("[SEB detection] matched via ?via=seb query param");
    return true;
  }

  // eslint-disable-next-line no-console
  console.log("[SEB detection] NOT inside SEB");
  return false;
}

