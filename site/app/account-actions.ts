"use server";

import { redirect } from "next/navigation";

import { signIn, signOut } from "@/auth";
import { forgetAccount, linkAccount } from "@/lib/api";
import { signedIn } from "@/lib/session";

const MAX_CODE = 32;
const CANT_CHECK = "Networth can't check codes right now. Try again in a minute.";
const SIGNED_OUT = "Your sign-in has run out. Sign in again to go on.";

export async function signInWithGoogle(): Promise<void> {
  await signIn("google", { redirectTo: "/dashboard" });
}

export async function signOutNow(): Promise<void> {
  await signOut({ redirectTo: "/" });
}

/** "Forget me on the web": the Google link goes on the server first, then the session here. */
export async function forgetMe(): Promise<void> {
  const visitor = await signedIn();
  if (visitor) {
    const result = await forgetAccount(visitor);
    if (!result.ok && result.status !== 401) redirect("/dashboard?forget=failed");
  }
  await signOut({ redirectTo: "/?forgotten=1" });
}

export interface LinkState {
  error: string | null;
}

/** The code from /weblink. The server says whether it worked; its words are shown as they come. */
export async function linkWithCode(_previous: LinkState, form: FormData): Promise<LinkState> {
  const visitor = await signedIn();
  if (!visitor) return { error: SIGNED_OUT };
  const code = String(form.get("code") ?? "").replace(/\s/g, "").slice(0, MAX_CODE);
  const result = await linkAccount(visitor, code);
  if (result.ok) redirect("/dashboard");
  const words = result.error?.message.body.map((b) => ("text" in b ? b.text : b.label)).join(" ");
  return { error: words || CANT_CHECK };
}
