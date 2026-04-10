import PowerConsumptionForm from './PowerConsumptionForm';
import DailyCoalSteamForm from './DailyCoalSteamForm';
import HODDashboard from './HODDashboard';
import React, { useState } from 'react';
import BoilerLogForm from './BoilerLogForm';

function App() {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('token')
  );
  const [userRole, setUserRole] = useState<string | null>(
    localStorage.getItem('role')
  );

  const handleLogin = (newToken: string, role: string) => {
    localStorage.setItem('token', newToken);
    localStorage.setItem('role', role);
    setToken(newToken);
    setUserRole(role);
  };

  const handleLogout = () => {
    localStorage.clear();
    setToken(null);
    setUserRole(null);
  };

  if (!token) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return <Dashboard role={userRole!} token={token!} onLogout={handleLogout} />;
}

// ─── LOGIN PAGE ───────────────────────────────────────────
function LoginPage({ onLogin }: { onLogin: (token: string, role: string) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch('https://shalimar-ops.onrender.com/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (res.ok) {
        onLogin(data.access_token, data.role);
      } else {
        setError(data.detail || 'Login failed');
      }
    } catch {
      setError('Cannot connect to server. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.loginBg}>
      <div style={styles.loginCard}>

        {/* Logo area */}
        <div style={styles.logoArea}>
          <div style={styles.logoCircle}>🏭</div>
          <h1 style={styles.logoTitle}>Shalimar Plant Ops</h1>
          <p style={styles.logoSub}>Sonkhamb · Katol · Nagpur</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Username</label>
            <input
              style={styles.input}
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
              autoFocus
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Password</label>
            <input
              style={styles.input}
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          {error && <div style={styles.errorBox}>{error}</div>}

          <button
            type="submit"
            style={loading ? styles.btnDisabled : styles.btn}
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p style={styles.footer}>
          Shalimar Nutrients Pvt. Ltd. · Internal System
        </p>
      </div>
    </div>
  );
}

// ─── DASHBOARD (placeholder) ─────────────────────────────
function Dashboard({ role, token, onLogout }: { 
  role: string; 
  token: string;
  onLogout: () => void 
}) {
  const [page, setPage] = useState<'home' | 'boiler-log' | 'hod-dashboard' | 'coal-steam' | 'power'>('home');

  if (page === 'boiler-log') {
    return <BoilerLogForm token={token} onBack={() => setPage('home')} />;
  }
  if (page === 'hod-dashboard') {
  return <HODDashboard token={token} onBack={() => setPage('home')} />;
}
if (page === 'coal-steam') {
  return <DailyCoalSteamForm token={token} onBack={() => setPage('home')} />;
}
if (page === 'power') {
  return <PowerConsumptionForm token={token} onBack={() => setPage('home')} />;
}

  return (
    <div style={styles.dashBg}>
      <div style={styles.dashHeader}>
        <div>
          <h2 style={styles.dashTitle}>Shalimar Plant Ops</h2>
          <p style={styles.dashSub}>Logged in as: <strong>{role.toUpperCase()}</strong></p>
        </div>
        <button onClick={onLogout} style={styles.logoutBtn}>Logout</button>
      </div>

            <div style={{ maxWidth: 600, margin: '40px auto', padding: '0 16px' }}>
        {/* Boiler Log Card */}
        <div onClick={() => setPage('boiler-log')} style={styles.menuCard}>
          <div style={{ fontSize: 36, marginBottom: 10 }}>🔥</div>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Boiler Log Entry</div>
          <div style={{ fontSize: 12, color: '#666' }}>Submit shift readings · Boiler No. 15936</div>
        </div>

        {/* HOD Dashboard Card */}
        {role === 'hod' && (
          <div
            onClick={() => setPage('hod-dashboard')}
            style={{ ...styles.menuCard, marginTop: 20 }}
          >
            <div style={{ fontSize: 36, marginBottom: 10 }}>👔</div>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>HOD Dashboard</div>
            <div style={{ fontSize: 12, color: '#666' }}>Review & approve pending entries</div>
          </div>
        )}
          <div onClick={() => setPage('coal-steam')}
            style={{ ...styles.menuCard, marginTop: 20 }}>
            <div style={{ fontSize: 36, marginBottom: 10 }}>🪨</div>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Daily Coal & Steam</div>
            <div style={{ fontSize: 12, color: '#666' }}>Auto C/S ratio · Replaces daily Excel</div>
           </div>
           <div onClick={() => setPage('power')}
            style={{ ...styles.menuCard, marginTop: 20 }}>
            <div style={{ fontSize: 36, marginBottom: 10 }}>⚡</div>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Power Consumption</div>
            <div style={{ fontSize: 12, color: '#666' }}>Daily units · Solar tracking · DG log</div>
          </div>
      </div>
    </div>
  );
}

// ─── STYLES ──────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  loginBg: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  loginCard: {
    background: '#fff',
    borderRadius: 16,
    padding: '40px 36px',
    width: '100%',
    maxWidth: 400,
    boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
  },
  logoArea: {
    textAlign: 'center',
    marginBottom: 32,
  },
  logoCircle: {
    fontSize: 48,
    marginBottom: 12,
  },
  logoTitle: {
    fontSize: 22,
    fontWeight: 700,
    color: '#1a1a2e',
    margin: '0 0 4px',
  },
  logoSub: {
    fontSize: 12,
    color: '#888',
    margin: 0,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: 600,
    color: '#444',
  },
  input: {
    padding: '12px 14px',
    border: '1.5px solid #ddd',
    borderRadius: 8,
    fontSize: 15,
    outline: 'none',
    transition: 'border 0.2s',
  },
  btn: {
    padding: '13px',
    background: '#0f3460',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 8,
  },
  btnDisabled: {
    padding: '13px',
    background: '#999',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: 'not-allowed',
    marginTop: 8,
  },
  errorBox: {
    background: '#fff0f0',
    border: '1px solid #ffcccc',
    color: '#cc0000',
    padding: '10px 14px',
    borderRadius: 8,
    fontSize: 13,
  },
  footer: {
    textAlign: 'center',
    fontSize: 11,
    color: '#aaa',
    marginTop: 24,
    marginBottom: 0,
  },
  dashBg: {
    minHeight: '100vh',
    background: '#f5f7fa',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  dashHeader: {
    background: '#0f3460',
    color: '#fff',
    padding: '16px 24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dashTitle: {
    margin: 0,
    fontSize: 18,
    fontWeight: 700,
  },
  dashSub: {
    margin: '4px 0 0',
    fontSize: 12,
    opacity: 0.8,
  },
  logoutBtn: {
    background: 'rgba(255,255,255,0.15)',
    color: '#fff',
    border: '1px solid rgba(255,255,255,0.3)',
    borderRadius: 6,
    padding: '8px 16px',
    cursor: 'pointer',
    fontSize: 13,
  },
  dashContent: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 'calc(100vh - 70px)',
  },
  welcomeCard: {
    background: '#fff',
    borderRadius: 16,
    padding: '48px 40px',
    textAlign: 'center',
    boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
    maxWidth: 360,
  },
  menuCard: {
  background: '#fff',
  borderRadius: 16,
  padding: '32px 28px',
  boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
  cursor: 'pointer',
  textAlign: 'center' as const,
  border: '2px solid transparent',
  transition: 'all 0.2s',
},
};

export default App;