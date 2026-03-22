import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Routes that don't require authentication */
const PUBLIC_ROUTES = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
];

/**
 * Decode the JWT payload and check if the token has expired.
 * Does NOT verify signature (edge middleware has no access to secret);
 * the backend validates signatures on every API call.
 */
function isTokenExpired(jwt: string): boolean {
  try {
    const parts = jwt.split(".");
    if (parts.length !== 3) return true;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(
      base64.length + ((4 - (base64.length % 4)) % 4),
      "=",
    );
    const payload = JSON.parse(atob(padded));
    if (typeof payload.exp !== "number") return true;
    // Allow 30s clock skew
    return payload.exp * 1000 < Date.now() - 30_000;
  } catch {
    return true;
  }
}

/**
 * Next.js Edge Middleware — redirects unauthenticated users to /login
 * and authenticated users away from auth pages.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip API routes and static assets
  if (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  const accessToken = request.cookies.get("access_token")?.value;

  // Token is valid if the httpOnly access_token exists and isn't expired.
  // The backend validates signatures on every API call; middleware only handles routing.
  const isAuthenticated = accessToken ? !isTokenExpired(accessToken) : false;

  const isPublicRoute = PUBLIC_ROUTES.some((r) => pathname.startsWith(r));

  // Unauthenticated user trying to access protected route → redirect to login
  if (!isAuthenticated && !isPublicRoute && pathname !== "/") {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  // Authenticated user trying to access auth pages → redirect to dashboard
  if (isAuthenticated && isPublicRoute) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
