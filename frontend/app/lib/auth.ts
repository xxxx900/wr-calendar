import type { Session, SupabaseClient } from "@supabase/supabase-js";

export async function fetchUserRoleFromSupabase(supabase: SupabaseClient, email: string): Promise<string | null> {
  try {
    const { data, error } = await supabase
      .from("users")
      .select("role")
      .ilike("email", email.trim())
      .single();
    if (error || !data) return null;
    return (data.role as string) || null;
  } catch {
    return null;
  }
}

export function isUserAdmin(session: Session | null, dbRole?: string | null): boolean {
  if (!session?.user) return false;
  if (dbRole === "admin" || dbRole === "calendar_admin" || dbRole === "event_admin") return true;
  const role = session.user.app_metadata?.role;
  if (role === "admin" || role === "calendar_admin" || role === "event_admin") return true;
  return false;
}

export type AdminVerificationResult = {
  is_admin: boolean;
  email: string;
  name?: string | null;
  picture?: string | null;
};

export async function verifyAdminWithBackend(apiUrl: string, providerToken: string): Promise<AdminVerificationResult | null> {
  try {
    const response = await fetch(`${apiUrl}/api/v1/chat/auth/verify-admin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_token: providerToken }),
    });
    if (!response.ok) return null;
    return (await response.json()) as AdminVerificationResult;
  } catch {
    return null;
  }
}
