import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Workspace } from "@/components/workspace";
import { plausibleToken } from "@/lib/api";

export const metadata: Metadata = { title: "Your plan · Networth", referrer: "no-referrer" };

/** `?q=/brief` loads the brief straight away, from a "Get my brief now" link. */
export default async function UserPage({ params, searchParams }: PageProps<"/u/[token]">) {
  const [{ token }, { q }] = await Promise.all([params, searchParams]);
  if (!plausibleToken(token)) notFound();
  return <Workspace scope={{ kind: "user", token }} ask={typeof q === "string" ? q.trim() || null : null} />;
}
