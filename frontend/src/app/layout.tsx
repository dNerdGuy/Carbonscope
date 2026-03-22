import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { QueryProvider } from "@/lib/query-provider";
import { ThemeProvider } from "@/lib/theme-context";
import { ToastProvider } from "@/components/Toast";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import { validateEnv } from "@/lib/env";

// Validate environment variables at import time (server side)
validateEnv();

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://carbonscope.io";

export const metadata: Metadata = {
  title: {
    default: "CarbonScope",
    template: "%s | CarbonScope",
  },
  description:
    "Decentralized corporate carbon emission intelligence powered by Bittensor",
  metadataBase: new URL(SITE_URL),
  alternates: { canonical: "/" },
  openGraph: {
    title: "CarbonScope",
    description:
      "Decentralized corporate carbon emission intelligence powered by Bittensor",
    type: "website",
    url: SITE_URL,
    siteName: "CarbonScope",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "CarbonScope — Decentralized Carbon Intelligence",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "CarbonScope",
    description:
      "Decentralized corporate carbon emission intelligence powered by Bittensor",
    images: ["/og-image.png"],
  },
  icons: { icon: "/favicon.ico" },
};

/** JSON-LD structured data for search engines. */
const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "CarbonScope",
  description:
    "Decentralized corporate carbon emission estimation and reporting platform powered by Bittensor",
  url: SITE_URL,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body>
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
                    {children}
                  </main>
                </AuthProvider>
              </Suspense>
            </ToastProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
