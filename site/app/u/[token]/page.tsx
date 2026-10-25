import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Workspace } from "@/components/workspace";
import { plausibleToken } from "@/lib/api";

export const metadata: Metadata = { title: "Your plan · Networth", referrer: "no-referrer" };

export default async function UserPage({ params }: PageProps<"/u/[token]">) {
  const { token } = await params;
  if (!plausibleToken(token)) notFound();
  return <Workspace scope={{ kind: "user", token }} />;
}
