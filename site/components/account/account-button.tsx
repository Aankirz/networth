import { signInWithGoogle } from "@/app/account-actions";
import { AccountMenu } from "@/components/account/account-menu";
import { signedIn } from "@/lib/session";

/** "Sign in" for a visitor, or their avatar and menu once they are signed in with Google. */
export async function AccountButton() {
  const visitor = await signedIn();
  if (visitor) return <AccountMenu name={visitor.name} />;
  return (
    <form action={signInWithGoogle}>
      <button type="submit" className="btn">Sign in</button>
    </form>
  );
}
