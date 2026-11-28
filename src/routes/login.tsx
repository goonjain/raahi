import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Eye, EyeOff, KeyRound, Lock, Mail, ShieldCheck, User, UserPlus } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

type SearchParams = {
  mode?: "login" | "signup";
  redirect?: string;
};

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    mode: search.mode === "signup" ? "signup" : "login",
    redirect: typeof search.redirect === "string" ? search.redirect : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Sign In — Raahi Jaipur" },
      { name: "description", content: "Sign in or create a Raahi traveller account for Jaipur." },
    ],
  }),
  component: LoginRouteComponent,
});

function LoginRouteComponent() {
  const search = Route.useSearch();
  return <LoginPage initialMode={search.mode} redirectTo={search.redirect} />;
}

function getPasswordStrength(pw: string): { valid: boolean; label: string; color: string } {
  if (!pw) return { valid: false, label: "", color: "" };
  const hasLen = pw.length >= 8;
  const hasLetter = /[a-zA-Z]/.test(pw);
  const hasNumber = /\d/.test(pw);
  if (hasLen && hasLetter && hasNumber) {
    return {
      valid: true,
      label: pw.length >= 12 ? "Strong password" : "Good password",
      color: "text-emerald-700",
    };
  }
  return {
    valid: false,
    label: "Use 8+ characters with at least one letter and one number",
    color: "text-amber-700",
  };
}

export function LoginPage({
  initialMode = "login",
  redirectTo,
}: {
  initialMode?: "login" | "signup";
  redirectTo?: string;
} = {}) {
  const navigate = useNavigate();
  const { user, loading: authLoading, login, signup } = useAuth();

  const [mode, setMode] = useState<"login" | "signup">(initialMode === "signup" ? "signup" : "login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user) {
      const target =
        redirectTo && redirectTo.startsWith("/")
          ? redirectTo
          : user.role === "admin"
            ? "/admin"
            : "/";
      void navigate({ to: target as any });
    }
  }, [authLoading, user, navigate, redirectTo]);

  const strength = getPasswordStrength(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === "signup") {
      if (name.trim().length < 2) {
        setError("Please enter your full name (at least 2 characters).");
        return;
      }
      if (!strength.valid) {
        setError("Password must be at least 8 characters and include a letter and a number.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
      setSubmitting(true);
      const res = await signup(name.trim(), email.trim(), password);
      setSubmitting(false);
      if (!res.ok) {
        setError(res.error || "Unable to create account.");
        return;
      }
      const target = redirectTo && redirectTo.startsWith("/") ? redirectTo : "/";
      void navigate({ to: target as any });
      return;
    }

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setSubmitting(true);
    const res = await login(email.trim(), password);
    setSubmitting(false);
    if (!res.ok || !res.user) {
      setError(res.error || "Invalid email or password.");
      return;
    }
    const target =
      redirectTo && redirectTo.startsWith("/")
        ? redirectTo
        : res.user.role === "admin"
          ? "/admin"
          : "/";
    void navigate({ to: target as any });
  };

  return (
    <div className="min-h-screen bg-background jaali flex flex-col">
      <header className="border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-baseline gap-2">
            <span className="font-display text-2xl text-primary font-bold">राही</span>
            <span className="text-base font-semibold text-foreground">Raahi</span>
            <span className="text-xs text-muted-foreground hidden sm:inline">| जयपुर</span>
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-primary transition"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Jaipur Guide
          </Link>
        </div>
        <div className="border-bandhani" />
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-border bg-card shadow-lg overflow-hidden">
          <div className="bg-gradient-to-r from-primary via-primary/95 to-saffron/90 px-6 py-6 text-primary-foreground">
            <p className="font-display text-sm text-gold">पधारो म्हारे देस · Welcome to Raahi</p>
            <h1 className="mt-1 font-serif text-2xl font-bold">
              {mode === "login" ? "Sign in to Raahi" : "Create your Raahi account"}
            </h1>
            <p className="mt-1 text-xs text-primary-foreground/85">
              {mode === "login"
                ? "Tourists & Rajasthan DoT administrators sign in here."
                : "Join Jaipur's crowd-aware travel community and earn rewards."}
            </p>
          </div>

          <div className="p-6 space-y-5">
            <div className="grid grid-cols-2 rounded-xl bg-muted p-1 border border-border">
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
                className={`flex items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-semibold transition ${
                  mode === "login"
                    ? "bg-card text-primary shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <KeyRound className="w-4 h-4" />
                Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("signup");
                  setError(null);
                }}
                className={`flex items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-semibold transition ${
                  mode === "signup"
                    ? "bg-card text-primary shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <UserPlus className="w-4 h-4" />
                Sign Up
              </button>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-lg border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-xs font-medium text-destructive"
              >
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === "signup" && (
                <div className="space-y-1.5">
                  <label htmlFor="auth-name" className="block text-xs font-semibold text-foreground">
                    Full Name
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      id="auth-name"
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Aarav Sharma"
                      className="w-full rounded-lg border border-input bg-background pl-9 pr-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="auth-email" className="block text-xs font-semibold text-foreground">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="auth-email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-lg border border-input bg-background pl-9 pr-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="auth-password" className="block text-xs font-semibold text-foreground">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="auth-password"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === "signup" ? "At least 8 chars, letter + number" : "Enter your password"}
                    className="w-full rounded-lg border border-input bg-background pl-9 pr-10 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {mode === "signup" && strength.label && (
                  <p className={`text-[11px] font-medium ${strength.color}`}>{strength.label}</p>
                )}
              </div>

              {mode === "signup" && (
                <div className="space-y-1.5">
                  <label htmlFor="auth-confirm" className="block text-xs font-semibold text-foreground">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      id="auth-confirm"
                      type={showConfirm ? "text" : "password"}
                      required
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter your password"
                      className="w-full rounded-lg border border-input bg-background pl-9 pr-10 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((s) => !s)}
                      aria-label={showConfirm ? "Hide confirm password" : "Show confirm password"}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1"
                    >
                      {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 transition disabled:opacity-60"
              >
                {submitting
                  ? mode === "login"
                    ? "Signing in..."
                    : "Creating account..."
                  : mode === "login"
                    ? "Sign In"
                    : "Create Tourist Account"}
              </button>
            </form>

            <div className="pt-2 border-t border-border flex items-center gap-2 text-[11px] text-muted-foreground">
              <ShieldCheck className="w-4 h-4 text-primary shrink-0" />
              <span>
                Secured with Argon2id password hashing and server-validated HttpOnly session cookies.
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

