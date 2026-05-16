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
  bed1_bottom_temp: number | null;
  bed2_top_temp: number | null;
  bed2_bottom_temp: number | null;
  flue_gas_temp: number | null;
  feed_water_temp: number | null;
  gag_filter_temp: number | null;
  coal_feed_bed1_hz: number | null;
  coal_feed_bed2_hz: number | null;
  id_fan_damper: number | null;
  fd_fan1_damper: number | null;
  fd_fan2_damper: number | null;
  booster_fan1: number | null;
  booster_fan2: number | null;
  fd_pressure: number | null;
  cbd_ibd_report: string | null;
  breakdown_problem: string | null;
  remarks: string | null;
  status: string;
  coal_opening_stock?: number | null;
  coal_consumed_sep?: number | null;
  coal_consumed_refinery?: number | null;
  total_coal_consumed?: number | null;
  closing_stock?: number | null;
  cs_ratio?: number | null;
}

export default function HODDashboard({ token, onBack }: {
  token: string; onBack: () => void;
}) {
  const [dailyEntry, setDailyEntry] = useState<any>(null);
  const [coalOpeningStock, setCoalOpeningStock] = useState<number | null>(null);
  const [suggestedOpening, setSuggestedOpening] = useState<number | null>(null);
  const [coalStockApproved, setCoalStockApproved] = useState(false);
  const [coalStockInput, setCoalStockInput] = useState('');
  const [coalStockMsg, setCoalStockMsg] = useState('');
  const [boilerEntries, setBoilerEntries] = useState<LogEntry[]>([]);
  const [powerReports, setPowerReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'boiler' | 'power'>('boiler');
  const [message] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedPowerId, setExpandedPowerId] = useState<number | null>(null);
  const [loadingMsg, setLoadingMsg] = useState('Loading...');

  useEffect(() => {
    const fetchCoalStock = async () => {
      const today = new Date().toISOString().split('T')[0];
      try {
        const r1 = await fetch(`${API}/daily-entry/closing/${today}`, { headers: authHeader });
        if (r1.ok) {
          const d1 = await r1.json();
          if (d1.closing_stock) {
            setSuggestedOpening(d1.closing_stock);
            setCoalStockInput(String(d1.closing_stock));
          }
        }
        const r2 = await fetch(`${API}/daily-entry/${today}`, { headers: authHeader });
        if (r2.ok) {
          const d2 = await r2.json();
          if (d2.opening_coal_stock) {
            setCoalOpeningStock(d2.opening_coal_stock);
            setCoalStockInput(String(d2.opening_coal_stock));
            setCoalStockApproved(true);
          }
        }
      } catch { }
    };
    fetchCoalStock();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoadingMsg('Waking up server (first load takes ~30 sec)...');
    }, 5000);
    return () => clearTimeout(timer);
  }, []);

  const authHeader = { 'Authorization': `Bearer ${token || localStorage.getItem('token')}` };

  const fetchBoiler = async () => {
    setLoading(true);
    
    // 👇 Calculate exactly 24 hours ago 👇
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const dateStr = yesterday.toISOString().split('T')[0];

    try {
      // Fetch yesterday's boiler log entries
      const res = await fetch(`${API}/boiler-log/date/${dateStr}`, { headers: authHeader });
      const data = await res.json();
      setBoilerEntries(Array.isArray(data) ? data : []);

      // Fetch yesterday's daily entry summary
      const res2 = await fetch(`${API}/daily-entry/${dateStr}`, { headers: authHeader });
      if (res2.ok) {
        const d2 = await res2.json();
        setDailyEntry(d2); // we'll add this state
      }
    } catch { setBoilerEntries([]); }
    finally { setLoading(false); }
  };

  const fetchPower = async () => {
    setLoading(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      const res = await fetch(`${API}/power-consumption/date/${today}`, { headers: authHeader });
      if (res.ok) {
        const data = await res.json();
        setPowerReports(data ? [data] : []);
      } else {
        setPowerReports([]);
      }
    } catch { setPowerReports([]); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (tab === 'boiler') fetchBoiler();
    else fetchPower();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const downloadBoilerDailyExcel = async (date: string) => {
    const res = await fetch(
      `${API}/export/daily-boiler/${date}`,
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
      `${API}/export/power-monthly/${now.getFullYear()}/${now.getMonth() + 1}`,
      { headers: { 'Authorization': `Bearer ${token || localStorage.getItem('token') || ''}` } }
    );
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `Power_Monthly_${now.getFullYear()}_${now.getMonth() + 1}.xlsx`; a.click();
    window.URL.revokeObjectURL(url);
  };

  const approveOpeningStock = async () => {
    const today = new Date().toISOString().split('T')[0];
    const val = parseFloat(coalStockInput);
    if (!val || isNaN(val)) { setCoalStockMsg('Enter a valid number'); return; }
    try {
      // Try daily-entry first, fallback to daily-report
      const res = await fetch(`${API}/daily-entry/${today}/opening`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ opening_stock: val }),
      });
      if (res.ok) {
        setCoalOpeningStock(val);
        setCoalStockApproved(true);
        setCoalStockMsg(`✅ Opening stock set to ${val} MT`);
        setTimeout(() => setCoalStockMsg(''), 4000);
      } else {
        setCoalStockMsg('Failed — check server');
      }
    } catch { setCoalStockMsg('Failed to set opening stock'); }
  };

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
              📊 Today's Power Excel
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

      {/* ── BOILER LOG ── */}
      {tab === 'boiler' && (
        <div style={s.content}>

          {/* 1. Coal stock FIRST */}
          <div style={{
            background: coalStockApproved ? '#f0fff4' : '#fffbeb',
            border: `1.5px solid ${coalStockApproved ? '#86efac' : '#fcd34d'}`,
            borderRadius: 12,
            padding: '14px 18px',
            marginBottom: 16,
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' as const, gap: 10 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#0f3460', marginBottom: 4 }}>
                  🪨 Today's Opening Coal Stock (MT)
                </div>
                {suggestedOpening && (
                  <div style={{ fontSize: 11, color: '#666' }}>
                    Suggested from yesterday's closing: <strong>{suggestedOpening} MT</strong>
                  </div>
                )}
                {!suggestedOpening && (
                  <div style={{ fontSize: 11, color: '#888' }}>Yesterday's closing not found — enter manually</div>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="number" step="any"
                  value={coalStockInput}
                  onChange={e => { setCoalStockInput(e.target.value); setCoalStockApproved(false); }}
                  placeholder="e.g. 919.175"
                  style={{ padding: '8px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 14, width: 130, outline: 'none' }}
                />
                <button
                  onClick={approveOpeningStock}
                  style={{
                    background: coalStockApproved ? '#10b981' : '#0f3460',
                    color: '#fff', border: 'none', borderRadius: 8,
                    padding: '9px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 700,
                  }}
                >
                  {coalStockApproved ? '✓ Approved' : '✓ Approve & Set'}
                </button>
              </div>
            </div>
            {coalStockMsg && <div style={{ fontSize: 12, marginTop: 8, color: '#166534' }}>{coalStockMsg}</div>}
          </div>

          {/* 2. Info bar SECOND */}
          <div style={s.sectionInfo}>
            📋 Today's boiler log entries — submitted automatically by operators every 2 hours
          </div>

          {dailyEntry && (
            <div style={{ background: '#f0f9ff', borderRadius: 12, padding: '14px 18px', marginBottom: 12, border: '1px solid #bae6fd' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#0f3460', marginBottom: 10 }}>
                📊 Today's Daily Summary — {dailyEntry.operator_name}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
                {[
                  ['Coal Arrival', `${dailyEntry.coal_arrival_indian ?? 0} MT`],
                  ['Steam SEP', `${dailyEntry.steam_sep_consumed ?? 0} KG`],
                  ['Steam REFL', `${dailyEntry.steam_refl_consumed ?? 0} KG`],
                  ['C/S Ratio', `${dailyEntry.cs_ratio ?? '—'}`],
                  ['Avg Feed Water', `${dailyEntry.avg_feed_water ?? '—'}°C`],
                  ['Avg FD Fan 1', `${dailyEntry.avg_fd_fan1 ?? '—'}%`],
                  ['Avg FD Fan 2', `${dailyEntry.avg_fd_fan2 ?? '—'}%`],
                  ['Coal Bunker', `${dailyEntry.coal_bunker_pct ?? '—'}%`],
                ].map(([label, val]) => (
                  <div key={label as string} style={{ background: '#fff', borderRadius: 8, padding: '8px 10px' }}>
                    <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase', marginBottom: 3 }}>{label}</div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{val}</div>
                  </div>
                ))}
              </div>
              {dailyEntry.remarks && <div style={{ marginTop: 8, fontSize: 12, color: '#555' }}>📝 {dailyEntry.remarks}</div>}
            </div>
          )}

          {loading ? (
            <div style={s.empty}>{loadingMsg}</div>
          ) : boilerEntries.length === 0 ? (
            <div style={s.empty}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#444' }}>No entries today</div>
              <div style={{ fontSize: 13, color: '#888', marginTop: 6 }}>Operators have not submitted yet</div>
            </div>
          ) : boilerEntries.map(entry => (
            <div key={entry.id} style={s.card}>
              <div style={{ ...s.cardHeader, cursor: 'pointer' }} onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}>
                <div style={s.cardLeft}>
                  <span style={s.entryId}>Entry #{entry.id}</span>
                  <span style={{ ...s.shiftBadge }}>Shift {entry.shift}</span>
                  <span style={s.dateText}>{entry.log_date} · {String(entry.log_time).slice(0, 5)}</span>
                  {entry.operator_name && <span style={{ fontSize: 12, color: '#666' }}>👤 {entry.operator_name}</span>}
                </div>
                <span style={{ fontSize: 12, color: '#888' }}>{expandedId === entry.id ? '▲ Hide' : '▼ Show All'}</span>
              </div>

              {expandedId === entry.id && (
                <div style={{ marginTop: 12 }}>
                  <div style={s.paramGrid}>
                    <Param label="Steam Pressure" value={entry.steam_pressure} unit="KG/CM" />
                    <Param label="Steam Flow SEP" value={entry.steam_flow_sep} unit="KG" />
                    <Param label="Steam Flow REFL" value={entry.steam_flow_refl} unit="KG" />
                    <Param label="Drum Water Level" value={entry.drum_water_level} unit="%" />
                    <Param label="Feed Water Temp" value={entry.feed_water_temp} unit="°C" />
                    <Param label="Bed 1 Top" value={entry.bed1_top_temp} unit="°C" />
                    <Param label="Bed 1 Bottom" value={entry.bed1_bottom_temp} unit="°C" />
                    <Param label="Bed 2 Top" value={entry.bed2_top_temp} unit="°C" />
                    <Param label="Bed 2 Bottom" value={entry.bed2_bottom_temp} unit="°C" />
                    <Param label="Flue Gas Temp" value={entry.flue_gas_temp} unit="°C" />
                    <Param label="GAG Filter Temp" value={entry.gag_filter_temp} unit="°C" />
                    <Param label="Coal Feed Bed1" value={entry.coal_feed_bed1_hz} unit="HZ" />
                    <Param label="Coal Feed Bed2" value={entry.coal_feed_bed2_hz} unit="HZ" />
                    <Param label="ID Fan Damper" value={entry.id_fan_damper} unit="%" />
                    <Param label="FD Fan 1" value={entry.fd_fan1_damper} unit="%" />
                    <Param label="FD Fan 2" value={entry.fd_fan2_damper} unit="%" />
                    <Param label="Booster Fan 1" value={entry.booster_fan1} unit="%" />
                    <Param label="Booster Fan 2" value={entry.booster_fan2} unit="%" />
                    <Param label="FD Pressure" value={entry.fd_pressure} unit="MM/WC" />
                  </div>
                  {entry.cbd_ibd_report && <div style={s.remarksBox}>📋 CBD/IBD: {entry.cbd_ibd_report}</div>}
                  {entry.breakdown_problem && <div style={s.breakdownAlert}>🚨 Breakdown: {entry.breakdown_problem}</div>}
                  {entry.remarks && <div style={s.remarksBox}>💬 {entry.remarks}</div>}

                  {/* Coal & Steam if filled */}
                  {entry.coal_opening_stock && (
                    <div style={{ marginTop: 10, background: '#f0f9ff', borderRadius: 8, padding: 10 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#0f3460', marginBottom: 8 }}>🪨 Coal & Steam</div>
                      <div style={s.paramGrid}>
                        <Param label="Opening Stock" value={entry.coal_opening_stock} unit="MT" />
                        <Param label="Consumed SEP" value={entry.coal_consumed_sep} unit="MT" />
                        <Param label="Consumed REFL" value={entry.coal_consumed_refinery} unit="MT" />
                        <Param label="Total Coal" value={entry.total_coal_consumed} unit="MT" />
                        <Param label="Closing Stock" value={entry.closing_stock} unit="MT" />
                        <Param label="C/S Ratio" value={entry.cs_ratio} unit="" />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {entry.breakdown_problem && !expandedId && (
                <div style={s.breakdownAlert}>🚨 Breakdown: {entry.breakdown_problem}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── POWER ── */}
      {tab === 'power' && (
        <div style={s.content}>
          {loading ? (
            <div style={s.empty}>{loadingMsg}</div>
          ) : powerReports.length === 0 ? <div style={s.empty}>No power reports found</div>
            : powerReports.map((r: any) => (
              <div key={r.id} style={s.card}>
                <div style={{ ...s.cardHeader, cursor: 'pointer' }}
                  onClick={() => setExpandedPowerId(expandedPowerId === r.id ? null : r.id)}>
                  <span style={s.entryId}>📅 {r.reading_date} — Shift {r.shift || 'A'}</span>
                  <span style={{ fontSize: 12, color: '#888' }}>{expandedPowerId === r.id ? '▲ Hide' : '▼ All Params'}</span>
                </div>

                <div style={s.paramGrid}>
                  <Param label="Total KWH" value={
                    (r.sep_units || 0) + (r.prep_units || 0) + (r.solar_units || 0) + (r.boiler_units || 0) +
                    (r.refinery_units || 0) + (r.etp_units || 0) + (r.packing_units || 0) + (r.admin_units || 0)
                  } unit="KWH" />
                  <Param label="Solar" value={r.solar_units} unit="KWH" />
                  <Param label="MSEDCL" value={r.msedcl_units} unit="KWH" />
                  <Param label="Power Factor" value={r.power_factor} unit="" />
                </div>

                {expandedPowerId === r.id && (
                  <div style={{ marginTop: 10 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px,1fr))', gap: 8 }}>
                      {[['SEP', 'sep_units'], ['PREP', 'prep_units'], ['Solar', 'solar_units'], ['Silo', 'silo_units'],
                      ['DOC', 'doc_units'], ['D-Silo', 'dsilo_units'], ['ACM', 'acm_units'], ['Boiler', 'boiler_units'],
                      ['CHP', 'chp_units'], ['DM Plant', 'dm_units'], ['UG Tank', 'ug_tank_units'], ['Refinery', 'refinery_units'],
                      ['ETP', 'etp_units'], ['Packing', 'packing_units'], ['Admin', 'admin_units'], ['DG Set', 'dg_units'],
                      ['MSEDCL', 'msedcl_units']].map(([label, key]) => (
                        <Param key={key} label={label} value={r[key]} unit="KWH" />
                      ))}
                      <Param label="kVAh" value={r.power_kvah} unit="" />
                      <Param label="Power Factor" value={r.power_factor} unit="" />
                    </div>
                    {r.dg_reason && <div style={s.remarksBox}>🛢️ DG: {r.dg_reason}</div>}
                  </div>
                )}
              </div>
            ))}
        </div>
      )}

    </div>
  );
}

function Param({ label, value, unit, warn }: {
  label: string; value: number | null | undefined; unit: string; warn?: boolean;
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
  breakdownAlert: { background: '#fff0f0', border: '1px solid #fecaca', color: '#dc2626', padding: '8px 12px', borderRadius: 8, fontSize: 13, marginTop: 8 },
  remarksBox: { background: '#f8f9fa', padding: '8px 12px', borderRadius: 8, fontSize: 13, color: '#555', marginTop: 8 },
};
