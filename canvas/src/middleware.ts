import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  // Redirect /en, /zh, etc. locale prefixes back to root
  const pathname = request.nextUrl.pathname;
  if (/^\/[a-z]{2}(\/|$)/.test(pathname)) {
    return NextResponse.redirect(new URL("/", request.url));
  }
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
