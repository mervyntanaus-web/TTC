import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export default function Login() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("staff@ttc.demo");
  const [password, setPassword] = useState("demo-password-123");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/cases" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="card login-card">
        <h2>TTC Digital Evidence Management</h2>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          Sign in to browse cases, review footage, and manage redactions.
        </p>
        {error && <div className="error-banner">{error}</div>}
        <form onSubmit={onSubmit}>
          <div className="field">
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </div>
          <div className="field">
            <label>Password</label>
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
          </div>
          <button type="submit" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 12 }}>
          Demo accounts (seeded by <code>seed/seed_data.py</code>): staff@ttc.demo, legal@ttc.demo,
          investigator@ttc.demo, admin@ttc.demo — password <code>demo-password-123</code>.
        </p>
      </div>
    </div>
  );
}
