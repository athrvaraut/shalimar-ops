import React, { useState, useEffect } from 'react';

const API = 'https://shalimar-ops.onrender.com';

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
  const [coalReports, setCoalReports] = useState<any[]>([]);
  const [powerReports, setPowerReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'pending' | 'today' | 'coal' | 'power'>('pending');
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [message, setMessage] = useState('');

  const authToken = token || localStorage.getItem('token') || '';

  const fetchEntries = async () => {
    setLoading(true);
    try {
      const endpoint = tab === 'pending'
        ? `${API}/boiler-log/pending`
        : `${API}/boiler-log/today`;
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

  const fetchCoalReports = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/daily-report/recent`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const data = await res.json();
      setCoalReports(Array.isArray(data) ? data : []);
    } catch {
      setCoalReports([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchPowerReports = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/power-consumption/recent`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const data = await res.json();
      setPowerReports(Array.isArray(data) ? data : []);
    } catch {
      setPowerReports([]);
    } finally {
      setLoading(false);
    }
  };

  // Single useEffect — runs correct fetch based on tab
  useEffect(() => {
    if (tab === 'pending' || tab === 'today') fetchEntries();
    else if (tab === 'coal') fetchCoalReports();
    else if (tab === 'power') fetchPowerReports();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const handleAction = async (id: number, action: 'approve' | 'reject') => {
    setActionLoading(id);
    try {
      const res = await fetch(`${API}/boiler-log/${id}/${action}`, {
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
    const res = await fetch(`${API}/export/daily-boiler/${date}`,
      { headers: { 'Authorization': `Bearer ${authToken}` } });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `Boiler_Report_${date}.xlsx`; a.click();
    window.URL.revokeObjectURL(url);
  };

  const downloadCoalExcel = async (date: string) => {
    const res = await fetch(`${API}/export/daily-boiler/${date}`,
      { headers: { 'Authorization': `Bearer ${authToken}` } });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `Coal_Steam_${date}.xlsx`; a.click();
    window.URL.revokeObjectURL(url);
  };

  const downloadPowerExcel = async (date: string) => {
    const res = await fetch(`${API}/export/power/${date}`,
      { headers: { 'Authorization': `Bearer ${authToken}` } });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `Power_${date}.xlsx`; a.click();
    window.URL.revokeObjectURL(url);
  };

  const downloadMonthlyCoal = async () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const res = await fetch(`${API}/export/monthly-coal/${year}/${month}`,
      { headers: { 'Authorization': `Bearer ${authToken}` } });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `Monthly_Coal_${year}_${month}.xlsx`; a.click();
    window.URL.revokeObjectURL(url);
  };

  const statusColor = (st: string) => ({
    pending: '#f59e0b',
    approved: '#10b981',
    rejected: '#ef4444'
  }[st] || '#888');

  return (
    <div style={s.page}>

      {/* ── HEADER ── */}
      <div style={s.header}>
        <button onClick={onBack} style={s.backBtn}>← Back</button>
        <div>
          <div style={s.headerTitle}>HOD Dashboard</div>
          <div style={s.headerSub}>Review & approve entries</div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginLeft: 'auto', flexWrap: 'wrap' as const }}>
          <button onClick={() => {
            if (tab === 'pending' || tab === 'today') fetchEntries();
            else if (tab === 'coal') fetchCoalReports();
            else fetchPowerReports();
          }} style={s.refreshBtn}>🔄 Refresh</button>
          <button onClick={() => downloadExcel(new Date().toISOString().split('T')[0])}
            style={s.dlBtn}>📥 Today's Excel</button>
          <button onClick={downloadMonthlyCoal}
            style={{ ...s.dlBtn, background: '#7c3aed' }}>📊 Monthly Report</button>
        </div>
      </div>

      {/* ── TABS ── */}
      <div style={s.tabs}>
        <button style={tab === 'pending' ? s.tabActive : s.tab} onClick={() => setTab('pending')}>⏳ Pending</button>
        <button style={tab === 'today' ? s.tabActive : s.tab} onClick={() => setTab('today')}>📅 Today's Logs</button>
        <button style={tab === 'coal' ? s.tabActive : s.tab} onClick={() => setTab('coal')}>🪨 Coal & Steam</button>
        <button style={tab === 'power' ? s.tabActive : s.tab} onClick={() => setTab('power')}>⚡ Power</button>
      </div>

      {message && <div style={s.msgBox}>{message}</div>}

      {/* ── BOILER LOGS (pending + today) ── */}
      {(tab === 'pending' || tab === 'today') && (
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
                {tab === 'pending' ? 'All entries have been reviewed' : 'Operators have not submitted yet'}
              </div>
            </div>
          ) : (
            entries.map(entry => (
              <div key={entry.id} style={s.card}>
                <div style={s.cardHeader}>
                  <div style={s.cardLeft}>
                    <span style={s.entryId}>Entry #{entry.id}</span>
                    <span style={{
                      ...s.statusBadge,
                      background: statusColor(entry.status) + '20',
                      color: statusColor(entry.status),
                      border: `1px solid ${statusColor(entry.status)}40`
                    }}>{entry.status.toUpperCase()}</span>
                  </div>
                  <div style={s.cardRight}>
                    <span style={s.shiftBadge}>Shift {entry.shift}</span>
                    <span style={s.dateText}>{entry.log_date} · {String(entry.log_time).slice(0, 5)}</span>
                  </div>
                </div>

                <div style={s.paramGrid}>
                  <Param label="Steam Pressure" value={entry.steam_pressure} unit="KG/CM"
                    warn={entry.steam_pressure !== null && (entry.steam_pressure < 8 || entry.steam_pressure > 12.5)} />
                  <Param label="Steam Flow SEP" value={entry.steam_flow_sep} unit="KG" />
                  <Param label="Steam Flow REFL" value={entry.steam_flow_refl} unit="KG" />
                  <Param label="Drum Water Level" value={entry.drum_water_level} unit="%" />
                  <Param label="Bed 1 Top Temp" value={entry.bed1_top_temp} unit="°C" />
                  <Param label="Bed 2 Top Temp" value={entry.bed2_top_temp} unit="°C" />
                  <Param label="Flue Gas Temp" value={entry.flue_gas_temp} unit="°C"
                    warn={entry.flue_gas_temp !== null && entry.flue_gas_temp > 220} />
                  <Param label="Feed Water Temp" value={entry.feed_water_temp} unit="°C" />
                </div>

                {entry.breakdown_problem && (
                  <div style={s.breakdownAlert}>
                    🚨 <strong>Breakdown:</strong> {entry.breakdown_problem}
                  </div>
                )}

                {entry.remarks && (
                  <div style={s.remarksBox}>💬 {entry.remarks}</div>
                )}

                {entry.status === 'pending' && (
                  <div style={s.actions}>
                    <button style={actionLoading === entry.id ? s.btnDisabled : s.btnApprove}
                      disabled={actionLoading === entry.id}
                      onClick={() => handleAction(entry.id, 'approve')}>
                      {actionLoading === entry.id ? '...' : '✓ Approve'}
                    </button>
                    <button style={actionLoading === entry.id ? s.btnDisabled : s.btnReject}
                      disabled={actionLoading === entry.id}
                      onClick={() => handleAction(entry.id, 'reject')}>
                      {actionLoading === entry.id ? '...' : '✗ Reject'}
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* ── COAL & STEAM TAB ── */}
      {tab === 'coal' && (
        <div style={s.content}>
          {loading ? (
            <div style={s.empty}>Loading...</div>
          ) : coalReports.length === 0 ? (
            <div style={s.empty}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🪨</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>No coal reports yet</div>
              <div style={{ fontSize: 13, color: '#888', marginTop: 6 }}>Submit a Daily Coal & Steam report first</div>
            </div>
          ) : (
            coalReports.map((r: any) => (
              <div key={r.id} style={s.card}>
                <div style={s.cardHeader}>
                  <div style={s.cardLeft}>
                    <span style={s.entryId}>📅 {r.report_date}</span>
                    <span style={{
                      ...s.statusBadge,
                      background: r.cs_ratio && r.cs_ratio >= 5.0 && r.cs_ratio <= 5.6 ? '#d1fae5' : '#fff0f0',
                      color: r.cs_ratio && r.cs_ratio >= 5.0 && r.cs_ratio <= 5.6 ? '#059669' : '#dc2626',
                      border: '1px solid #ccc'
                    }}>C/S: {r.cs_ratio || '—'}</span>
                  </div>
                  <button onClick={() => downloadCoalExcel(r.report_date)}
                    style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                    📥 Excel
                  </button>
                </div>
                <div style={s.paramGrid}>
                  <Param label="Opening Stock" value={r.opening_coal_stock} unit="MT" />
                  <Param label="Coal Consumed" value={r.total_coal_consumed} unit="MT" />
                  <Param label="Closing Stock" value={r.closing_stock} unit="MT" />
                  <Param label="Total Steam" value={r.total_steam} unit="KG" />
                  <Param label="SEP Steam" value={r.steam_sep_consumed} unit="KG" />
                  <Param label="REFL Steam" value={r.steam_refl_consumed} unit="KG" />
                  <Param label="Feed Water" value={r.feed_water_temp} unit="°C" />
                  <Param label="Coal Bunker" value={r.coal_bunker_pct} unit="%" />
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── POWER TAB ── */}
      {tab === 'power' && (
        <div style={s.content}>
          {loading ? (
            <div style={s.empty}>Loading...</div>
          ) : powerReports.length === 0 ? (
            <div style={s.empty}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>⚡</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>No power reports yet</div>
              <div style={{ fontSize: 13, color: '#888', marginTop: 6 }}>Submit a Power Consumption report first</div>
            </div>
          ) : (
            powerReports.map((r: any) => (
              <div key={r.id} style={s.card}>
                <div style={s.cardHeader}>
                  <div style={s.cardLeft}>
                    <span style={s.entryId}>⚡ {r.reading_date}</span>
                    <span style={{ ...s.statusBadge, background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>
                      PF: {r.power_factor || '—'}
                    </span>
                  </div>
                  <button onClick={() => downloadPowerExcel(r.reading_date)}
                    style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                    📥 Excel
                  </button>
                </div>
                <div style={s.paramGrid}>
                  <Param label="SEP" value={r.sep_units} unit="KWH" />
                  <Param label="PREP" value={r.prep_units} unit="KWH" />
                  <Param label="Solar" value={r.solar_units} unit="KWH" />
                  <Param label="Boiler" value={r.boiler_units} unit="KWH" />
                  <Param label="Refinery" value={r.refinery_units} unit="KWH" />
                  <Param label="MSEDCL" value={r.msedcl_units} unit="KWH" />
                  <Param label="DG Units" value={r.dg_units} unit="KWH" />
                  <Param label="ETP" value={r.etp_units} unit="KWH" />
                </div>
              </div>
            ))
          )}
        </div>
      )}

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
  refreshBtn: { background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13 },
  dlBtn: { background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  tabs: { display: 'flex', background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '0 20px', overflowX: 'auto' as const },
  tab: { padding: '12px 16px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, color: '#666', borderBottom: '2px solid transparent', whiteSpace: 'nowrap' as const },
  tabActive: { padding: '12px 16px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, color: '#0f3460', fontWeight: 700, borderBottom: '2px solid #0f3460', whiteSpace: 'nowrap' as const },
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