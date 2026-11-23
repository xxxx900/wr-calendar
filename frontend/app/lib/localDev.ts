import type { Session } from "@supabase/supabase-js";

export const LOCAL_DEV = process.env.NEXT_PUBLIC_LOCAL_DEV === "true";

// Matches the admin entry in scripts/dev_token.py.
export function localDevSession(): Session {
  return {
    access_token: process.env.NEXT_PUBLIC_LOCAL_DEV_TOKEN ?? "",
    refresh_token: "",
    expires_in: 31536000,
    token_type: "bearer",
    user: {
      id: "11111111-1111-1111-1111-111111111111",
      email: "admin@example.test",
      aud: "authenticated",
      app_metadata: { role: "admin" },
      user_metadata: { full_name: "Local Admin" },
      created_at: new Date(0).toISOString(),
    },
  };
}
