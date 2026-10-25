import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { cookies } from "next/headers";
import "./globals.css";

const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
// Mono only sets figures, none of them above the fold, so it loads without a preload.
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"], preload: false });

export const metadata: Metadata = {
  title: "Networth",
  description: "Know what the news means for your money. Research, not advice.",
};

export const viewport: Viewport = {
  themeColor: "oklch(14.5% 0.004 255)",
};

export const THEME_COOKIE = "nw-theme";

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const light = (await cookies()).get(THEME_COOKIE)?.value === "light";
  return (
    <html lang="en" data-theme={light ? "light" : "dark"} className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
