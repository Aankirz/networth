import type { Metadata, Viewport } from "next";
import { Newsreader, Public_Sans } from "next/font/google";
import { cookies } from "next/headers";
import "./globals.css";

const display = Newsreader({ variable: "--font-display", subsets: ["latin"], style: ["normal"] });
const text = Public_Sans({ variable: "--font-text", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Networth",
  description: "What happened, what history counted, and what your plan could become. Research, not advice.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "oklch(96.1% 0.006 135)" },
    { media: "(prefers-color-scheme: dark)", color: "oklch(20.6% 0.016 235)" },
  ],
};

export const THEME_COOKIE = "nw-theme";

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const picked = (await cookies()).get(THEME_COOKIE)?.value;
  const theme = picked === "light" || picked === "dark" ? picked : undefined;
  return (
    <html lang="en" data-theme={theme} className={`${display.variable} ${text.variable}`}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
