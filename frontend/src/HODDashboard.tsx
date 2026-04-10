import React, { useState, useEffect } from 'react';

interface LogEntry {
  id: number;
  shift: string;
  log_date: string;
  log_time: string;
  steam_pressure: number | null;
  steam_flow_sep: number | null;
  steam_flow_refl: number | null;
  drum_water_level: number | null;
  bed1_top_temp: number | null;
  bed2_top_temp: number | null;
  flue_gas_temp: number | null;
  feed_water_temp: number | null;
  breakdown_problem: string | null;
  remarks: string | null;
  status: string;
  created_at: string;
}

export default function HODDashboard({ token, onBack }: {
  token: string;
  onBack: () => void;
}) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'pending' | 'today'>('pending');
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [message, setMessage] = useState('');

  const fetchEntries = async () => {
  setLoading(true);
  const authToken = token || localStorage.getItem('token') || '';
  console.log('Token being used:', authToken?.slice(0, 30));
  
  try {
    const endpoint = tab === 'pending'
      ? 'http://127.0.0.1:8000/boiler-log/pending'
      : 'http://127.0.0.1:8000/boiler-log/today';

    const res = await fetch(endpoint, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    const data = await res.json();
    setEntries(Array.isArray(data) ? data : []);
  } catch {
    setEntries([]);
  } finally {
    setLoading(false);
  }
};

  useEffect(() => { fetchEntries(); }, [tab]);

  const handleAction = async (id: number, action: 'approve' | 'reject') => {
  setActionLoading(id);
  const authToken = token || localStorage.getItem('token') || '';
  try {
    const res = await fetch(`http://127.0.0.1:8000/boiler-log/${id}/${action}`, {
      method: 'PUT',
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    if (res.ok) {
      setMessage(`Entry #${id} ${action}d successfully`);
      setTimeout(() => setMessage(''), 3000);
      fetchEntries();
    }
  } finally {
    setActionLoading(null);
  }
};
  const downloadExcel = async (date: string) => {
  const res = await fetch(
    `http://127.0.0.1:8000/export/daily-boiler/${date}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Boiler_Report_${date}.xlsx`;
  a.click();
  window.URL.revokeObjectURL(url);
};

  const statusColor = (s: string) => ({
    pending: '#f59e0b',
    approved: '#10b981',
    rejected: '#ef4444'
  }[s] || '#888');

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <button onClick={onBack} style={s.backBtn}>← Back</button>
        <div>
          <div style={s.headerTitle}>HOD Dashboard</div>
          <div style={s.headerSub}>Review & approve boiler log entries</div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
  <button onClick={fetchEntries} style={s.refreshBtn}>🔄 Refresh</button>
  <button
    onClick={() => downloadExcel(new Date().toISOString().split('T')[0])}
    style={{
      background: '#10b981', color: '#fff', border: 'none',
      borderRadius: 6, padding: '6px 12px', cursor: 'pointer',
      fontSize: 13, fontWeight: 600
    }}
  >
     📥 Download Today's Excel
   </button>
  </div>
</div>

      {/* Tabs */}
      <div style={s.tabs}>
        <button
          style={tab === 'pending' ? s.tabActive : s.tab}
          onClick={() => setTab('pending')}
        >
          ⏳ Pending Approval
        </button>
        <button
          style={tab === 'today' ? s.tabActive : s.tab}
          onClick={() => setTab('today')}
        >
          📅 Today's Entries
        </button>
      </div>

      {message && <div style={s.msgBox}>{message}</div>}

      {/* Content */}
      <div style={s.content}>
        {loading ? (
          <div style={s.empty}>Loading...</div>
        ) : entries.length === 0 ? (
          <div style={s.empty}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>
              {tab === 'pending' ? '✅' : '📋'}
            </div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>
              {tab === 'pending' ? 'No pending entries' : 'No entries today'}
            </div>
            <div style={{ fontSize: 13, color: '#888', marginTop: 6 }}>
              {tab === 'pending'
                ? 'All entries have been reviewed'
                : 'Operators have not submitted yet'}
            </div>
          </div>
        ) : (
          entries.map(entry => (
            <div key={entry.id} style={s.card}>
              {/* Card header */}
              <div style={s.cardHeader}>
                <div style={s.cardLeft}>
                  <span style={s.entryId}>Entry #{entry.id}</span>
                  <span style={{
                    ...s.statusBadge,
                    background: statusColor(entry.status) + '20',
                    color: statusColor(entry.status),
                    border: `1px solid ${statusColor(entry.status)}40`
                  }}>
                    {entry.status.toUpperCase()}
                  </span>
                </div>
                <div style={s.cardRight}>
                  <span style={s.shiftBadge}>Shift {entry.shift}</span>
                  <span style={s.dateText}>
                    {entry.log_date} · {String(entry.log_time).slice(0, 5)}
                  </span>
                </div>
              </div>

              {/* Parameters grid */}
              <div style={s.paramGrid}>
                <Param label="Steam Pressure" value={entry.steam_pressure} unit="KG/CM"
                  warn={entry.steam_pressure !== null && (entry.steam_pressure < 6 || entry.steam_pressure > 12)} />
                <Param label="Steam Flow SEP" value={entry.steam_flow_sep} unit="KG" />
                <Param label="Steam Flow REFL" value={entry.steam_flow_refl} unit="KG" />
                <Param label="Drum Water Level" value={entry.drum_water_level} unit="%"
                  warn={entry.drum_water_level !== null && (entry.drum_water_level < 60 || entry.drum_water_level > 90)} />
                <Param label="Bed 1 Top Temp" value={entry.bed1_top_temp} unit="°C" />
                <Param label="Bed 2 Top Temp" value={entry.bed2_top_temp} unit="°C" />
                <Param label="Flue Gas Temp" value={entry.flue_gas_temp} unit="°C"
                  warn={entry.flue_gas_temp !== null && entry.flue_gas_temp > 200} />
                <Param label="Feed Water Temp" value={entry.feed_water_temp} unit="°C" />
              </div>

              {/* Breakdown alert */}
              {entry.breakdown_problem && (
                <div style={s.breakdownAlert}>
                  🚨 <strong>Breakdown:</strong> {entry.breakdown_problem}
                </div>
              )}

              {/* Remarks */}
              {entry.remarks && (
                <div style={s.remarksBox}>
                  💬 {entry.remarks}
                </div>
              )}

              {/* Action buttons — only for pending */}
              {entry.status === 'pending' && (
                <div style={s.actions}>
                  <button
                    style={actionLoading === entry.id ? s.btnDisabled : s.btnApprove}
                    disabled={actionLoading === entry.id}
                    onClick={() => handleAction(entry.id, 'approve')}
                  >
                    {actionLoading === entry.id ? '...' : '✓ Approve'}
                  </button>
                  <button
                    style={actionLoading === entry.id ? s.btnDisabled : s.btnReject}
                    disabled={actionLoading === entry.id}
                    onClick={() => handleAction(entry.id, 'reject')}
                  >
                    {actionLoading === entry.id ? '...' : '✗ Reject'}
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function Param({ label, value, unit, warn }: {
  label: string; value: number | null;
  unit: string; warn?: boolean;
}) {
  return (
    <div style={{ ...s.param, ...(warn ? s.paramWarn : {}) }}>
      <div style={s.paramLabel}>{label}</div>
      <div style={{ ...s.paramValue, color: warn ? '#ef4444' : '#111' }}>
        {value !== null && value !== undefined ? `${value} ${unit}` : '—'}
        {warn && ' ⚠️'}
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: '#f0f2f5', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' },
  header: { background: '#0f3460', color: '#fff', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16, position: 'sticky', top: 0, zIndex: 10 },
  headerTitle: { fontSize: 16, fontWeight: 700 },
  headerSub: { fontSize: 11, opacity: 0.75, marginTop: 2 },
  backBtn: { background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13 },
  refreshBtn: { marginLeft: 'auto', background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13 },
  tabs: { display: 'flex', background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '0 20px' },
  tab: { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, color: '#666', borderBottom: '2px solid transparent' },
  tabActive: { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, color: '#0f3460', fontWeight: 700, borderBottom: '2px solid #0f3460' },
  content: { maxWidth: 760, margin: '0 auto', padding: '20px 16px' },
  empty: { textAlign: 'center', padding: '60px 20px', color: '#888' },
  msgBox: { background: '#f0fff4', border: '1px solid #86efac', color: '#166534', padding: '10px 20px', fontSize: 13, textAlign: 'center' },
  card: { background: '#fff', borderRadius: 12, padding: '16px 18px', marginBottom: 14, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' },
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, paddingBottom: 10, borderBottom: '1px solid #f0f0f0' },
  cardLeft: { display: 'flex', alignItems: 'center', gap: 10 },
  cardRight: { display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' as const },
  entryId: { fontSize: 14, fontWeight: 700, color: '#111' },
  statusBadge: { fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 99, letterSpacing: '0.05em' },
  shiftBadge: { background: '#eff6ff', color: '#1d4ed8', fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 99 },
  dateText: { fontSize: 12, color: '#666' },
  paramGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 12 },
  param: { background: '#f8f9fa', borderRadius: 8, padding: '8px 10px' },
  paramWarn: { background: '#fff8f0', border: '1px solid #fed7aa' },
  paramLabel: { fontSize: 10, color: '#888', marginBottom: 4, textTransform: 'uppercase' as const, letterSpacing: '0.04em' },
  paramValue: { fontSize: 13, fontWeight: 600 },
  breakdownAlert: { background: '#fff0f0', border: '1px solid #fecaca', color: '#dc2626', padding: '8px 12px', borderRadius: 8, fontSize: 13, marginBottom: 8 },
  remarksBox: { background: '#f8f9fa', padding: '8px 12px', borderRadius: 8, fontSize: 13, color: '#555', marginBottom: 8 },
  actions: { display: 'flex', gap: 10, marginTop: 12 },
  btnApprove: { flex: 1, padding: '10px', background: '#10b981', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' },
  btnReject: { flex: 1, padding: '10px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' },
  btnDisabled: { flex: 1, padding: '10px', background: '#aaa', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, cursor: 'not-allowed' },
};