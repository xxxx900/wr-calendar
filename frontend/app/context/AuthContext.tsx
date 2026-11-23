"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getAuthRedirectUrl, getSupabaseClient } from "../lib/supabase";
import { fetchUserRoleFromSupabase, isUserAdmin } from "../lib/auth";
import { LOCAL_DEV, localDevSession } from "../lib/localDev";

type AuthContextType = {
  session: Session | null;
  user: User | null;
  isAdmin: boolean;
  authLoading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType>({
  session: null,
  user: null,
  isAdmin: false,
  authLoading: true,
  signIn: async () => {},
  signOut: async () => {},
  refreshAuth: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [dbRole, setDbRole] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  async function checkDbRole(currentSession: Session | null) {
    if (!currentSession?.user?.email) {
      setDbRole(null);
      return;
    }
    const supabase = getSupabaseClient();
    if (!supabase) return;
    const role = await fetchUserRoleFromSupabase(supabase, currentSession.user.email);
    setDbRole(role);
  }

  async function syncSession(currentSession: Session | null) {
    setSession(currentSession);
    await checkDbRole(currentSession);
    setAuthLoading(false);
  }

  useEffect(() => {
    if (LOCAL_DEV) {
      setSession(localDevSession());
      setDbRole("admin");
      setAuthLoading(false);
      return;
    }

    const supabase = getSupabaseClient();
    if (!supabase) {
      setAuthLoading(false);
      return;
    }

    void supabase.auth.getSession().then(({ data }) => {
      void syncSession(data.session);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      void syncSession(nextSession);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  async function signIn() {
    if (LOCAL_DEV) return;
    const supabase = getSupabaseClient();
    if (!supabase) return;
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: getAuthRedirectUrl() },
    });
  }

  async function signOut() {
    if (LOCAL_DEV) return;
    const supabase = getSupabaseClient();
    await supabase?.auth.signOut();
    setSession(null);
    setDbRole(null);
  }

  async function refreshAuth() {
    const supabase = getSupabaseClient();
    if (!supabase) return;
    const { data } = await supabase.auth.getSession();
    await syncSession(data.session);
  }

  const isAdmin = isUserAdmin(session, dbRole);

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        isAdmin,
        authLoading,
        signIn,
        signOut,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
