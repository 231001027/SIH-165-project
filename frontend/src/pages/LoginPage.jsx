import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button, Input, Label } from "../components/ui";
import { IconCheckShield, IconFlame, IconEval } from "../components/icons";

const DEMO_ACCOUNTS = [
  { role: "Admin", email: "admin@sifguard-oil.com", password: "Admin@12345" },
  { role: "HSE Analyst", email: "analyst@sifguard-oil.com", password: "Analyst@12345" },
  { role: "Viewer", email: "viewer@sifguard-oil.com", password: "Viewer@12345" },
];

const PILLARS = [
  { icon: IconFlame, title: "Detect", body: "Finds the small minority of reports carrying genuine fatal potential." },
  { icon: IconCheckShield, title: "Explain", body: "Every classification traces to evidence in the text -- never a bare score." },
  { icon: IconEval, title: "Abstain", body: "Weak or conflicting evidence routes to human review, never a forced guess." },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("analyst@sifguard-oil.com");
  const [password, setPassword] = useState("Analyst@12345");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) {
      navigate("/dashboard");
    } else {
      setError(result.error);
    }
  }

  return (
    <div className="flex min-h-screen bg-ink-950">
      <div className="bg-grain relative hidden w-[46%] flex-col justify-between overflow-hidden bg-gradient-to-br from-ink-900 via-ink-950 to-black p-12 text-white lg:flex">
        <div className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-accent-500/20 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-96 w-96 translate-x-1/3 translate-y-1/4 rounded-full bg-teal-500/10 blur-3xl" />

        <div className="relative">
          <div className="mb-1 flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 text-sm font-extrabold text-ink-950 shadow-glow">
              SG
            </span>
            <p className="text-[15px] font-extrabold tracking-tight">SIFGuard-OIL</p>
          </div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent-400">
            SIH26165 &middot; Oil India Limited
          </p>
        </div>

        <div className="relative">
          <h1 className="max-w-md text-[32px] font-extrabold leading-[1.15] tracking-tight">
            "No injury occurred" does not mean low risk.
          </h1>
          <p className="mt-4 max-w-sm text-[14px] leading-relaxed text-white/60">
            An explainable SIF-precursor intelligence layer that reads free-text safety reports, maps them
            to IOGP Life-Saving Rules, and surfaces the safety barrier that actually failed -- with the
            honesty to say "I'm not sure" when the evidence is thin.
          </p>

          <div className="mt-9 grid grid-cols-3 gap-4">
            {PILLARS.map((p) => (
              <div key={p.title} className="rounded-xl border border-white/10 bg-white/[0.03] p-3.5">
                <p.icon className="h-4 w-4 text-accent-400" />
                <p className="mt-2 text-[12.5px] font-bold text-white">{p.title}</p>
                <p className="mt-0.5 text-[11px] leading-snug text-white/50">{p.body}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-[11px] text-white/30">
          Synthetic demo data throughout &middot; no real OIL production data is used
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center bg-surface px-6 py-12">
        <div className="w-full max-w-[400px] animate-fade-in-up">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 text-sm font-extrabold text-ink-950">
                SG
              </span>
              <p className="text-[16px] font-extrabold text-ink_text-primary">SIFGuard-OIL</p>
            </div>
          </div>

          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-accent-600">Welcome back</p>
          <h2 className="mt-1 text-[24px] font-extrabold tracking-tight text-ink_text-primary">Sign in to the console</h2>
          <p className="mt-1.5 text-[13px] text-ink_text-secondary">Access the HSE precursor-intelligence dashboard.</p>

          <form onSubmit={handleSubmit} className="mt-7 space-y-4">
            <div>
              <Label>Email</Label>
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <Label>Password</Label>
              <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && (
              <p className="rounded-lg border border-risk-high/20 bg-risk-high/5 px-3 py-2 text-[13px] font-medium text-risk-high">
                {error}
              </p>
            )}
            <Button type="submit" variant="accent" size="lg" disabled={loading} className="w-full">
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>

          <div className="mt-7 border-t border-line pt-5">
            <p className="mb-2 text-[10.5px] font-bold uppercase tracking-wide text-ink_text-muted">Demo accounts</p>
            <div className="space-y-1.5">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.email}
                  onClick={() => {
                    setEmail(acc.email);
                    setPassword(acc.password);
                  }}
                  className="flex w-full items-center justify-between rounded-lg border border-line px-3 py-2 text-left text-[12.5px] transition hover:border-accent-300 hover:bg-accent-50/40"
                >
                  <span className="font-bold text-ink_text-primary">{acc.role}</span>
                  <span className="text-ink_text-muted">{acc.email}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
