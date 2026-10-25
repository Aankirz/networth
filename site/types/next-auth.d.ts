import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    /** The Google subject id. Read on the server only, to sign the token the API trusts. */
    subject: string | null;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    google?: string;
  }
}
