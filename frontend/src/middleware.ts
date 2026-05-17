import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

const SECRET = new TextEncoder().encode(
  process.env.SECRET_KEY || "troque-esta-chave-em-producao"
);

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isAdminPath = pathname.startsWith("/admin");
  const isClientPath = pathname.startsWith("/client");

  if (!isAdminPath && !isClientPath) {
    return NextResponse.next();
  }

  const rawToken = request.cookies.get("auth-token")?.value;
  const token = rawToken ? decodeURIComponent(rawToken) : null;

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    const { payload } = await jwtVerify(token, SECRET, {
      algorithms: ["HS256"],
    });

    const role = payload.role as string;

    if (isAdminPath && role !== "super_admin") {
      return NextResponse.redirect(new URL("/client", request.url));
    }

    return NextResponse.next();
  } catch {
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete("auth-token");
    return response;
  }
}

export const config = {
  matcher: ["/admin/:path*", "/client/:path*"],
};
