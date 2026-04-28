import React, { useState, useEffect } from 'react';

const API = 'https://shalimar-ops.onrender.com';

interface LogEntry {
  id: number;
  shift: string;
  log_date: string;
  log_time: string;
  operator_name: string | null;
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
}

export default function HODDashboard({ token, onBack }: {
  token: string; onBack: () => void;
}) {
  const [boilerEntries, setBoilerEntries] = useState<LogEntry[]>([]);
  const [coalReports, setCoalReports] = useState<any[]>([]);
  const [powerReports, setPowerReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'boiler' | 'power'>('boiler');
  const [message] = useState('');

  const authHeader = { 'Authorization': `Bearer ${token || localStorage.getItem('token')}` };

  const fetchBoiler = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/boiler-log/today`, { headers: authHeader });
      const data = await res.json();
      setBoilerEntries(Array.isArray(data) ? data : []);
    } catch { setBoilerEntries([]); }
    finally { setLoading(false); }
  };

  const fetchCoal = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/daily-report/recent`, { headers: authHeader });
      const data = await res.json();
      setPowerReports(Array.isArray(data) ? data : []);
    } catch { setPowerReports([]); }
    finally { setLoading(false); }
  };

  const fetchPower = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/power-consumption/recent`, { headers: authHeader });
      const data = await res.json();
      setPowerReports(Array.isArray(data) ? data : []);
    } catch { setPowerReports([]); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (tab === 'boiler') fetchBoiler();
    else fetchPower();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const download = async (url: string, filename: string) => {
    try {
      const res = await fetch(url, { headers: authHeader });
      if (!res.ok) { alert('No data found for this date'); return; }
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = window.URL.createObjectURL(blob);
      a.download = filename; a.click();
      window.URL.revokeObjectURL(a.href);
    } catch { alert('Download failed — check connection'); }
  };

  const downloadBoilerDailyExcel = async (date: string) => {
    const res = await fetch(
      `https://shalimar-ops.onrender.com/export/daily-boiler/${date}`,
      { headers: { 'Authorization': `Bearer ${token || localStorage.getItem('token') || ''}` } }
    );
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `Boiler_${date}.xlsx`; a.click();
    window.URL.revokeObjectURL(url);
  };

  const downloadPowerMonthlyExcel = async () => {
    const now = new Date();
    const res = await fetch(
      `https://shalimar-ops.onrender.com/export/power-monthly/${now.getFullYear()}/${now.getMonth() + 1}`,
      { headers: { 'Authorization': `Bearer ${token || localStorage.getItem('token') || ''}` } }
    );
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `Power_Monthly_${now.getFullYear()}_${now.getMonth() + 1}.xlsx`; a.click();
    window.URL.revokeObjectURL(url);
  };

  const today = new Date().toISOString().split('T')[0];

  return (
    <div style={s.page}>

      {/* ── HEADER ── */}
      <div style={s.header}>
        <button onClick={onBack} style={s.backBtn}>← Back</button>
        <div>
          <div style={s.headerTitle}>HOD Dashboard</div>
          <div style={s.headerSub}>Sonkhamb Plant · Shalimar Nutrients</div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
          {tab === 'boiler' && (
            <button
              onClick={() => downloadBoilerDailyExcel(new Date().toISOString().split('T')[0])}
              style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
            >
              📥 Today's Boiler Excel
            </button>
          )}
          {tab === 'power' && (
            <button
              onClick={downloadPowerMonthlyExcel}
              style={{ background: '#7c3aed', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
            >
              📊 Monthly Power Excel
            </button>
          )}
        </div>
      </div>

      {/* ── TABS ── */}
      <div style={s.tabs}>
        <button style={tab === 'boiler' ? s.tabActive : s.tab} onClick={() => setTab('boiler')}>
          🔥 Boiler Log
        </button>
        <button style={tab === 'power' ? s.tabActive : s.tab} onClick={() => setTab('power')}>
          ⚡ Power
        </button>
      </div>

      {message && <div style={s.msgBox}>{message}</div>}

      {/* ── BOILER LOG ── */}
      {tab === 'boiler' && (
        <div style={s.content}>
          <div style={s.sectionInfo}>
            📋 Today's boiler log entries — submitted automatically by operators every 2 hours
          </div>
          {loading ? <div style={s.empty}>Loading...</div>
            : boilerEntries.length === 0 ? (
              <div style={s.empty}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#444' }}>No entries today</div>
                <div style={{ fontSize: 13, color: '#888', marginTop: 6 }}>Operators have not submitted yet</div>
              </div>
            ) : boilerEntries.map(entry => (
              <div key={entry.id} style={s.card}>
                <div style={s.cardHeader}>
                  <div style={s.cardLeft}>
                    <span style={s.entryId}>#{entry.id}</span>
                    <span style={s.shiftBadge}>Shift {entry.shift}</span>
                    <span style={s.dateText}>{String(entry.log_time).slice(0, 5)}</span>
                    {entry.operator_name && (
                      <span style={{ fontSize: 12, color: '#555' }}>👤 {entry.operator_name}</span>
                    )}
                  </div>
                  <button onClick={() => download(`${API}/export/daily-boiler/${entry.log_date}`, `Boiler_${entry.log_date}.xlsx`)}
                    style={s.miniBtn}>📥 Excel</button>
                </div>

                <div style={s.paramGrid}>
                  <Param label="Steam Pressure" value={entry.steam_pressure} unit="KG/CM"
                    warn={entry.steam_pressure !== null && (entry.steam_pressure < 8 || entry.steam_pressure > 12.5)} />
                  <Param label="Flow SEP" value={entry.steam_flow_sep} unit="KG" />
                  <Param label="Flow REFL" value={entry.steam_flow_refl} unit="KG" />
                  <Param label="Drum Level" value={entry.drum_water_level} unit="%" />
                  <Param label="Bed 1 Top" value={entry.bed1_top_temp} unit="°C" />
                  <Param label="Bed 2 Top" value={entry.bed2_top_temp} unit="°C" />
                  <Param label="Flue Gas" value={entry.flue_gas_temp} unit="°C"
                    warn={entry.flue_gas_temp !== null && entry.flue_gas_temp > 220} />
                  <Param label="Feed Water" value={entry.feed_water_temp} unit="°C" />
                </div>

                {entry.breakdown_problem && (
                  <div style={s.alertBox}>🚨 <strong>Breakdown:</strong> {entry.breakdown_problem}</div>
                )}
                {entry.remarks && <div style={s.remarksBox}>💬 {entry.remarks}</div>}
              </div>
            ))}
        </div>
      )}

      {/* ── POWER ── */}
      {tab === 'power' && (
        <div style={s.content}>
          <div style={s.sectionInfo}>
            ⚡ Daily power consumption per section · Click 📥 Excel on any row to download that day's report
          </div>
          {loading ? <div style={s.empty}>Loading...</div>
            : powerReports.length === 0 ? (
              <div style={s.empty}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>⚡</div>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#444' }}>No power reports yet</div>
                <div style={{ fontSize: 13, color: '#888', marginTop: 6 }}>Go to Power Consumption form and submit a report</div>
              </div>
            ) : powerReports.map((r: any) => {
              const total = (r.sep_units || 0) + (r.prep_units || 0) + (r.solar_units || 0) + (r.silo_units || 0) +
                (r.doc_units || 0) + (r.dsilo_units || 0) + (r.acm_units || 0) + (r.boiler_units || 0) +
                (r.chp_units || 0) + (r.dm_units || 0) + (r.ug_tank_units || 0) + (r.refinery_units || 0) +
                (r.etp_units || 0) + (r.packing_units || 0) + (r.admin_units || 0) + (r.dg_units || 0);
              const solarPct = total > 0 ? ((r.solar_units || 0) / total * 100).toFixed(1) : '0';
              return (
                <div key={r.id} style={s.card}>
                  <div style={s.cardHeader}>
                    <div style={s.cardLeft}>
                      <span style={s.entryId}>📅 {r.reading_date}</span>
                      <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 99, background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>
                        Total: {total.toFixed(0)} KWH
                      </span>
                      {r.solar_units > 0 && (
                        <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 99, background: '#f0fdf4', color: '#059669', border: '1px solid #86efac' }}>
                          ☀️ Solar: {r.solar_units} KWH ({solarPct}%)
                        </span>
                      )}
                    </div>
                    <button onClick={() => download(`${API}/export/power/${r.reading_date}`, `Power_${r.reading_date}.xlsx`)}
                      style={s.miniBtn}>📥 Excel</button>
                  </div>
                  <div style={s.paramGrid}>
                    <Param label="SEP" value={r.sep_units} unit="KWH" />
                    <Param label="PREP" value={r.prep_units} unit="KWH" />
                    <Param label="Solar" value={r.solar_units} unit="KWH" />
                    <Param label="Boiler" value={r.boiler_units} unit="KWH" />
                    <Param label="Refinery" value={r.refinery_units} unit="KWH" />
                    <Param label="ETP" value={r.etp_units} unit="KWH" />
                    <Param label="MSEDCL" value={r.msedcl_units} unit="KWH" />
                    <Param label="Power Factor" value={r.power_factor} unit="" />
                  </div>
                  {r.dg_reason && <div style={s.remarksBox}>🛢️ DG: {r.dg_reason}</div>}
                </div>
              );
            })}
        </div>
      )}

    </div>
  );
}

function Param({ label, value, unit, warn }: {
  label: string; value: number | null; unit: string; warn?: boolean;
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
  header: { background: '#0f3460', color: '#fff', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 12, position: 'sticky', top: 0, zIndex: 10, flexWrap: 'wrap' as const },
  headerTitle: { fontSize: 16, fontWeight: 700 },
  headerSub: { fontSize: 11, opacity: 0.7, marginTop: 2 },
  backBtn: { background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13 },
  refreshBtn: { background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', fontSize: 14 },
  dlBtn: { background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 600 },
  miniBtn: { background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, padding: '5px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 600 },
  tabs: { display: 'flex', background: '#fff', borderBottom: '2px solid #e5e7eb', padding: '0 20px' },
  tab: { padding: '14px 24px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, color: '#666', borderBottom: '3px solid transparent', fontWeight: 500 },
  tabActive: { padding: '14px 24px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, color: '#0f3460', fontWeight: 700, borderBottom: '3px solid #0f3460' },
  sectionInfo: { background: '#fff', borderRadius: 10, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: '#555', border: '1px solid #e5e7eb' },
  content: { maxWidth: 800, margin: '0 auto', padding: '16px 16px 40px' },
  empty: { textAlign: 'center', padding: '60px 20px', color: '#888' },
  msgBox: { background: '#f0fff4', border: '1px solid #86efac', color: '#166534', padding: '10px 20px', fontSize: 13, textAlign: 'center' },
  card: { background: '#fff', borderRadius: 12, padding: '16px 18px', marginBottom: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.07)' },
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, paddingBottom: 10, borderBottom: '1px solid #f0f0f0', flexWrap: 'wrap' as const, gap: 8 },
  cardLeft: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const },
  cardRight: { display: 'flex', alignItems: 'center', gap: 8 },
  entryId: { fontSize: 14, fontWeight: 700, color: '#111' },
  shiftBadge: { background: '#eff6ff', color: '#1d4ed8', fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 99 },
  dateText: { fontSize: 12, color: '#666' },
  paramGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 8 },
  param: { background: '#f8f9fa', borderRadius: 8, padding: '7px 10px' },
  paramWarn: { background: '#fff8f0', border: '1px solid #fed7aa' },
  paramLabel: { fontSize: 10, color: '#888', marginBottom: 3, textTransform: 'uppercase' as const, letterSpacing: '0.04em' },
  paramValue: { fontSize: 13, fontWeight: 600 },
  alertBox: { background: '#fff0f0', border: '1px solid #fecaca', color: '#dc2626', padding: '8px 12px', borderRadius: 8, fontSize: 13, marginTop: 8 },
  remarksBox: { background: '#f8f9fa', padding: '8px 12px', borderRadius: 8, fontSize: 13, color: '#555', marginTop: 8 },
};