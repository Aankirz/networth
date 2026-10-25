import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Google only. AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET and AUTH_SECRET come from the environment.
// The session cookie keeps three things: the Google subject id, the display name and nothing
// else. Google's tokens and the email are dropped as soon as the sign-in completes.
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  pages: { signIn: "/dashboard", error: "/dashboard" },
  callbacks: {
    jwt({ token, account }) {
      // Without a database, Auth.js gives each sign-in a random `sub`; Google's own subject id
      // is the account's providerAccountId, and that is what a link is keyed on.
      if (account?.provider === "google") {
        return { sub: token.sub, name: token.name ?? "", google: account.providerAccountId };
      }
      return token;
    },
    session({ session, token }) {
      return { expires: session.expires, user: { name: token.name ?? "" }, subject: token.google ?? null };
    },
  },
});
