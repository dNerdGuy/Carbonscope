import { Outlet, createRootRoute } from "@tanstack/react-router";
import { Suspense } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { QueryProvider } from "@/lib/query-provider";
import { ThemeProvider } from "@/lib/theme-context";
import { ToastProvider } from "@/components/Toast";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import RouteError from "@/components/RouteError";
import NotFoundPage from "@/components/NotFound";

export const Route = createRootRoute({
  errorComponent: RouteError,
  notFoundComponent: NotFoundPage,
  component: RootLayout,
});

function RootLayout() {
  return (
    <ThemeProvider>
      <QueryProvider>
        <ToastProvider>
          <Suspense>
            <AuthProvider>
              <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-[var(--primary)] focus:text-black focus:px-4 focus:py-2 focus:rounded-lg"
              >
                Skip to main content
              </a>
              <Navbar />
              <Sidebar />
              <main id="main-content" className="sidebar-main" role="main">
                <Outlet />
              </main>
            </AuthProvider>
          </Suspense>
        </ToastProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}
