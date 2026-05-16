import React, { useState, useEffect } from 'react';

const TIME_SLOTS = ['07:00', '09:00', '11:00', '13:00', '15:00', '17:00',
  '19:00', '21:00', '23:00', '01:00', '03:00', '05:00'];

const today = () => {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().split('T')[0];
};

const avg = (arr: (number | null)[]) => {
  const vals = arr.filter(x => x !== null && x !== undefined && !isNaN(x as number)) as number[];
  return vals.length ? Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100 : null;
};

interface Props { token: string; onBack: () => void; }

export default function BoilerLogForm({ token, onBack }: Props) {
  const [date, setDate] = useState(today());
  const [operatorName, setOperatorName] = useState('');
  const [locked, setLocked] = useState(false);
  const [existingId, setExistingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchingDate, setFetchingDate] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  // Coal & Steam
  const [coal, setCoal] = useState({
    coal_arrival_indian: '',
    coal_thermic: '',
    coal_bunker_pct: '',
    steam_pressure_ok: 'true'
  });

  // Steam Flow
  const [steam, setSteam] = useState({
    steam_sep_opening: '', steam_sep_closing: '',
    steam_refl_opening: '', steam_refl_closing: ''
  });

  // 12-reading arrays
  const [feedWater, setFeedWater] = useState<(string)[]>(Array(12).fill(''));
  const [fd1, setFd1] = useState<(string)[]>(Array(12).fill(''));
  const [fd2, setFd2] = useState<(string)[]>(Array(12).fill(''));
  const [remarks, setRemarks] = useState('');
  // Add these 3 new state arrays after your existing state declarations:
  const [serverFW, setServerFW] = useState<boolean[]>(Array(12).fill(false));
  const [serverFD1, setServerFD1] = useState<boolean[]>(Array(12).fill(false));
  const [serverFD2, setServerFD2] = useState<boolean[]>(Array(12).fill(false));

  // Live calculations
  const steamSepConsumed = (parseFloat(steam.steam_sep_closing) || 0) - (parseFloat(steam.steam_sep_opening) || 0);
  const steamReflConsumed = (parseFloat(steam.steam_refl_closing) || 0) - (parseFloat(steam.steam_refl_opening) || 0);
  const totalSteam = steamSepConsumed + steamReflConsumed;

  const fwNums = feedWater.map(x => x !== '' ? parseFloat(x) : null);
  const fd1Nums = fd1.map(x => x !== '' ? parseFloat(x) : null);
  const fd2Nums = fd2.map(x => x !== '' ? parseFloat(x) : null);
  const avgFW = avg(fwNums);
  const avgFD1 = avg(fd1Nums);
  const avgFD2 = avg(fd2Nums);

  // Fetch existing entry when date changes
  useEffect(() => {
    if (!date) return;
    const authToken = token || localStorage.getItem('token') || '';
    setFetchingDate(true);
    fetch(`https://shalimar-ops.onrender.com/daily-entry/${date}`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    }).then(r => {
      if (r.ok) return r.json();
      throw new Error('not found');
    }).then(data => {
      // Pre-fill all fields
      setExistingId(data.id);
      setOperatorName(data.operator_name || '');
      setCoal({
        coal_arrival_indian: data.coal_arrival_indian ?? '',
        coal_thermic: data.coal_thermic ?? '',
        coal_bunker_pct: data.coal_bunker_pct ?? '',
        steam_pressure_ok: data.steam_pressure_ok ? 'true' : 'false',
      });
      setSteam({
        steam_sep_opening: data.steam_sep_opening ?? '',
        steam_sep_closing: data.steam_sep_closing ?? '',
        steam_refl_opening: data.steam_refl_opening ?? '',
        steam_refl_closing: data.steam_refl_closing ?? ''
      });
      const fw = Array.isArray(data.feed_water_temps) ? data.feed_water_temps : Array(12).fill('');
      const f1 = Array.isArray(data.fd_fan1_dampers) ? data.fd_fan1_dampers : Array(12).fill('');
      const f2 = Array.isArray(data.fd_fan2_dampers) ? data.fd_fan2_dampers : Array(12).fill('');
      setFeedWater(fw.map((x: any) => x ?? ''));
      setFd1(f1.map((x: any) => x ?? ''));
      setFd2(f2.map((x: any) => x ?? ''));
      setServerFW(fw.map((x: any) => x !== null && x !== undefined && x !== ''));
      setServerFD1(f1.map((x: any) => x !== null && x !== undefined && x !== ''));
      setServerFD2(f2.map((x: any) => x !== null && x !== undefined && x !== ''));
      setRemarks(data.remarks || '');
      setLocked(true);
    }).catch(() => {
      setLocked(false);
      setExistingId(null);
      // Reset form
      setOperatorName('');
      setCoal({
        coal_arrival_indian: '', coal_thermic: '',
        coal_bunker_pct: '', steam_pressure_ok: 'true'
      });
      setSteam({ steam_sep_opening: '', steam_sep_closing: '', steam_refl_opening: '', steam_refl_closing: '' });
      setFeedWater(Array(12).fill(''));
      setFd1(Array(12).fill(''));
      setFd2(Array(12).fill(''));
      setServerFW(Array(12).fill(false));
      setServerFD1(Array(12).fill(false));
      setServerFD2(Array(12).fill(false));
      setRemarks('');
    }).finally(() => setFetchingDate(false));
  }, [date]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setError(''); setSuccess('');
    const authToken = token || localStorage.getItem('token') || '';
    const payload = {
      entry_date: date,
      operator_name: operatorName,
      opening_coal_stock: 0,
      coal_arrival_indian: parseFloat(coal.coal_arrival_indian) || 0,
      coal_arrival_imported: 0,
      coal_consumed_sep: 0,
      coal_consumed_refinery: 0,
      coal_thermic: parseFloat(coal.coal_thermic) || 0,
      coal_bunker_pct: parseFloat(coal.coal_bunker_pct) || null,
      steam_pressure_ok: coal.steam_pressure_ok === 'true',
      coal_rate_per_mt: null,
      ...Object.fromEntries(Object.entries(steam).map(([k, v]) => [k, v !== '' ? parseFloat(v) : null])),
      feed_water_temps: fwNums,
      fd_fan1_dampers: fd1Nums,
      fd_fan2_dampers: fd2Nums,
      remarks
    };
    try {
      const res = await fetch('https://shalimar-ops.onrender.com/daily-entry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        setSuccess(`✅ Saved! C/S Ratio: ${data.cs_ratio} | Closing Stock: ${data.closing_stock} MT | Avg Feed Water: ${data.avg_feed_water}°C`);
        setLocked(true);
        setExistingId(data.id);
      } else {
        setError(JSON.stringify(data.detail || 'Save failed'));
      }
    } catch { setError('Cannot connect to server'); }
    finally { setLoading(false); }
  };

  const C = (field: keyof typeof coal, val: string) => setCoal(p => ({ ...p, [field]: val }));
  const S = (field: keyof typeof steam, val: string) => setSteam(p => ({ ...p, [field]: val }));

  return (
    <div style={s.page}>
      <div style={s.header}>
        <button onClick={onBack} style={s.backBtn}>← Back</button>
        <div>
          <div style={s.headerTitle}>Daily Boiler Entry</div>
          <div style={s.headerSub}>Boiler No. 15936 · Sonkhamb Plant</div>
        </div>
        {locked && (
          <button onClick={() => setLocked(false)} style={s.modifyBtn}>✏️ Modify</button>
        )}
      </div>

      {locked && (
        <div style={s.lockedBanner}>
          🔒 Entry for {date} already submitted. Click <strong>Modify</strong> to edit.
        </div>
      )}

      <form onSubmit={handleSubmit} style={s.form}>

        {/* Basic Info */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📋 Entry Details</div>
          <div style={s.row2}>
            <Field label="Date *">
              <input style={{ ...s.input, ...(locked ? s.locked : {}) }} type="date"
                value={date} onChange={e => setDate(e.target.value)}
                disabled={locked} required />
            </Field>
            <Field label="Operator Name *">
              <input style={{ ...s.input, ...(locked ? s.locked : {}) }} type="text"
                value={operatorName} onChange={e => setOperatorName(e.target.value)}
                placeholder="e.g. Saurav Joshi" disabled={locked} required />
            </Field>
          </div>
          {fetchingDate && <div style={s.fetchNote}>Checking existing entry...</div>}
        </div>

        {/* Coal & Steam Summary */}
        <div style={s.section}>
          <div style={s.sectionTitle}>🪨 Daily Coal & Steam Summary <span style={s.note}>Fill once per day</span></div>

          <div style={s.row2}>
            <NumField label="Coal Arrival Indian (MT)" value={coal.coal_arrival_indian}
              onChange={v => C('coal_arrival_indian', v)} locked={locked && coal.coal_arrival_indian !== '' && coal.coal_arrival_indian !== '0'} />
            <NumField label="Coal Thermic Boiler (MT)" value={coal.coal_thermic}
              onChange={v => C('coal_thermic', v)} locked={locked && coal.coal_thermic !== '' && coal.coal_thermic !== '0'} />
          </div>
          <div style={s.row2}>
            <NumField label="Coal Bunker (%)" value={coal.coal_bunker_pct}
              onChange={v => C('coal_bunker_pct', v)} locked={locked && coal.coal_bunker_pct !== ''} />
            <Field label="Steam Pressure OK">
              <select style={{ ...s.select, ...(locked && coal.steam_pressure_ok !== '' ? s.locked : {}) }}
                value={coal.steam_pressure_ok} onChange={e => C('steam_pressure_ok', e.target.value)}
                disabled={locked && coal.steam_pressure_ok !== ''}>
                <option value="true">Yes — Normal</option>
                <option value="false">No — Issue</option>
              </select>
            </Field>
          </div>
        </div>

        {/* Steam Flow */}
        <div style={s.section}>
          <div style={s.sectionTitle}>♨️ Steam Flow Meter Readings</div>
          <div style={s.row2}>
            <NumField label="Opening Steam Flow SEP (KG)" value={steam.steam_sep_opening}
              onChange={v => S('steam_sep_opening', v)} locked={locked} />
            <NumField label="Closing Steam Flow SEP (KG)" value={steam.steam_sep_closing}
              onChange={v => S('steam_sep_closing', v)} locked={locked} />
          </div>
          <div style={s.row2}>
            <NumField label="Opening Steam Flow REFL (KG)" value={steam.steam_refl_opening}
              onChange={v => S('steam_refl_opening', v)} locked={locked} />
            <NumField label="Closing Steam Flow REFL (KG)" value={steam.steam_refl_closing}
              onChange={v => S('steam_refl_closing', v)} locked={locked} />
          </div>
          {(steamSepConsumed !== 0 || steamReflConsumed !== 0) && (
            <div style={s.calcBox}>
              <CalcItem label="SEP Steam Consumed" value={`${steamSepConsumed.toFixed(0)} KG`} />
              <CalcItem label="REFL Steam Consumed" value={`${steamReflConsumed.toFixed(0)} KG`} />
              <CalcItem label="Total Steam" value={`${totalSteam.toFixed(0)} KG`} highlight />
            </div>
          )}
        </div>

        {/* Feed Water Temp — 12 boxes */}
        <div style={s.section}>
          <div style={s.sectionTitle}>
            💧 Feed Water Temperature (°C)
            {avgFW !== null && <span style={s.avgBadge}>AVG: {avgFW}°C</span>}
          </div>
          <div style={s.grid12}>
            {TIME_SLOTS.map((t, i) => (
              <div key={t} style={s.slot}>
                <div style={s.slotLabel}>{t}</div>
                <input
                  style={{ ...s.slotInput, ...(locked && serverFW[i] ? s.lockedSlot : {}) }}
                  type="number" step="any"
                  value={feedWater[i]}
                  onChange={e => {
                    const n = [...feedWater]; n[i] = e.target.value; setFeedWater(n);
                  }}
                  readOnly={locked && serverFW[i]}
                  placeholder="—"
                />
              </div>
            ))}
          </div>
          {avgFW !== null && <div style={s.avgRow}>Average Feed Water: <strong>{avgFW}°C</strong></div>}
        </div>

        {/* FD Fan 1 — 12 boxes */}
        <div style={s.section}>
          <div style={s.sectionTitle}>
            🌀 FD Fan 1 Damper (%)
            {avgFD1 !== null && <span style={s.avgBadge}>AVG: {avgFD1}%</span>}
          </div>
          <div style={s.grid12}>
            {TIME_SLOTS.map((t, i) => (
              <div key={t} style={s.slot}>
                <div style={s.slotLabel}>{t}</div>
                <input
                  style={{ ...s.slotInput, ...(locked && serverFD1[i] ? s.lockedSlot : {}) }}
                  type="number" step="any"
                  value={fd1[i]}
                  onChange={e => {
                    const n = [...fd1]; n[i] = e.target.value; setFd1(n);
                  }}
                  readOnly={locked && serverFD1[i]}
                  placeholder="—"
                />
              </div>
            ))}
          </div>
          {avgFD1 !== null && <div style={s.avgRow}>Average FD Fan 1: <strong>{avgFD1}%</strong></div>}
        </div>

        {/* FD Fan 2 — 12 boxes */}
        <div style={s.section}>
          <div style={s.sectionTitle}>
            🌀 FD Fan 2 Damper (%)
            {avgFD2 !== null && <span style={s.avgBadge}>AVG: {avgFD2}%</span>}
          </div>
          <div style={s.grid12}>
            {TIME_SLOTS.map((t, i) => (
              <div key={t} style={s.slot}>
                <div style={s.slotLabel}>{t}</div>
                <input
                  style={{ ...s.slotInput, ...(locked && serverFD2[i] ? s.lockedSlot : {}) }}
                  type="number" step="any"
                  value={fd2[i]}
                  onChange={e => {
                    const n = [...fd2]; n[i] = e.target.value; setFd2(n);
                  }}
                  readOnly={locked && serverFD2[i]}
                  placeholder="—"
                />
              </div>
            ))}
          </div>
          {avgFD2 !== null && <div style={s.avgRow}>Average FD Fan 2: <strong>{avgFD2}%</strong></div>}
        </div>

        {/* Remarks */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📝 Remarks</div>
          <textarea style={{ ...s.textarea, ...(locked ? s.locked : {}) }}
            value={remarks} onChange={e => setRemarks(e.target.value)}
            placeholder="Any remarks for the day" rows={3}
            readOnly={locked} />
        </div>

        {/* Replace the existing button section */}
        {error && <div style={s.errorBox}>❌ {error}</div>}
        {success && <div style={s.successBox}>{success}</div>}

        {/* Show button if: not locked, OR locked but has new values in previously empty slots */}
        {(() => {
          const hasNewFW = fwNums.some((v, i) => v !== null && !serverFW[i]);
          const hasNewFD1 = fd1Nums.some((v, i) => v !== null && !serverFD1[i]);
          const hasNewFD2 = fd2Nums.some((v, i) => v !== null && !serverFD2[i]);
          const hasNewData = hasNewFW || hasNewFD1 || hasNewFD2;
          const showButton = !locked || hasNewData;

          return showButton ? (
            <button
              type="submit"
              style={loading ? s.btnDisabled : s.btn}
              disabled={loading}
            >
              {loading ? 'Saving...' : existingId ? '💾 Update Entry' : '📤 Submit Entry'}
            </button>
          ) : null;
        })()}
      </form >
    </div >
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div style={s.field}><label style={s.label}>{label}</label>{children}</div>;
}

function NumField({ label, value, onChange, locked }: {
  label: string; value: string;
  onChange: (v: string) => void; locked: boolean;
}) {
  return (
    <Field label={label}>
      <input style={{ ...s.input, ...(locked ? s.locked : {}) }}
        type="number" step="any" value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="—" readOnly={locked} />
    </Field>
  );
}

function CalcItem({ label, value, warn, highlight }: {
  label: string; value: string; warn?: boolean; highlight?: boolean;
}) {
  return (
    <div style={s.calcItem}>
      <div style={s.calcLabel}>{label}</div>
      <div style={{
        ...s.calcValue, color: warn ? '#ef4444' : highlight ? '#0f3460' : '#111',
        fontWeight: highlight ? 800 : 600
      }}>{value}</div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh', background: '#f0f2f5',
    fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
  },
  header: {
    background: '#0f3460', color: '#fff', padding: '14px 20px',
    display: 'flex', alignItems: 'center', gap: 16, position: 'sticky', top: 0, zIndex: 10
  },
  headerTitle: { fontSize: 16, fontWeight: 700 },
  headerSub: { fontSize: 11, opacity: 0.75, marginTop: 2 },
  backBtn: {
    background: 'rgba(255,255,255,0.15)', color: '#fff',
    border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6,
    padding: '6px 12px', cursor: 'pointer', fontSize: 13
  },
  modifyBtn: {
    marginLeft: 'auto', background: '#f59e0b', color: '#fff',
    border: 'none', borderRadius: 6, padding: '8px 16px',
    cursor: 'pointer', fontSize: 13, fontWeight: 700
  },
  lockedBanner: {
    background: '#fef9c3', borderBottom: '1px solid #fde047',
    padding: '10px 20px', fontSize: 13, color: '#854d0e', textAlign: 'center' as const
  },
  form: { maxWidth: 760, margin: '0 auto', padding: '20px 16px 40px' },
  section: {
    background: '#fff', borderRadius: 12, padding: '16px 18px',
    marginBottom: 14, boxShadow: '0 1px 4px rgba(0,0,0,0.06)'
  },
  sectionTitle: {
    fontSize: 13, fontWeight: 700, color: '#0f3460', marginBottom: 14,
    paddingBottom: 8, borderBottom: '1px solid #f0f0f0',
    display: 'flex', alignItems: 'center', gap: 8
  },
  note: { fontSize: 11, fontWeight: 400, color: '#999' },
  row3: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 },
  row2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: {
    fontSize: 11, fontWeight: 600, color: '#555',
    textTransform: 'uppercase' as const, letterSpacing: '0.04em'
  },
  input: {
    padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8,
    fontSize: 15, outline: 'none', width: '100%', boxSizing: 'border-box' as const
  },
  select: {
    padding: '10px 12px', border: '1.5px solid #e0e0e0',
    borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff', width: '100%'
  },
  locked: { background: '#f8f9fa', color: '#666', cursor: 'not-allowed' },
  fetchNote: { fontSize: 12, color: '#888', fontStyle: 'italic', marginTop: 4 },
  calcBox: {
    display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10,
    background: '#f0f6ff', borderRadius: 8, padding: '12px 14px', marginTop: 8
  },
  calcItem: { textAlign: 'center' as const },
  calcLabel: { fontSize: 10, color: '#666', marginBottom: 4, textTransform: 'uppercase' as const },
  calcValue: { fontSize: 15 },
  avgBadge: {
    marginLeft: 'auto', background: '#dbeafe', color: '#1d4ed8',
    padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700
  },
  avgRow: {
    marginTop: 10, fontSize: 13, color: '#555', textAlign: 'right' as const,
    paddingTop: 6, borderTop: '1px solid #f0f0f0'
  },
  grid12: { display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 8 },
  slot: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 },
  slotLabel: { fontSize: 10, fontWeight: 600, color: '#888' },
  slotInput: {
    width: '100%', padding: '8px 4px', border: '1.5px solid #e0e0e0',
    borderRadius: 6, fontSize: 13, textAlign: 'center' as const, outline: 'none'
  },
  lockedSlot: { background: '#f0f6ff', borderColor: '#bfdbfe', color: '#1d4ed8' },
  emptySlot: { background: '#f8f9fa', color: '#aaa' },
  textarea: {
    width: '100%', padding: '10px 12px', border: '1.5px solid #e0e0e0',
    borderRadius: 8, fontSize: 14, resize: 'vertical' as const,
    fontFamily: 'inherit', boxSizing: 'border-box' as const
  },
  btn: {
    width: '100%', padding: '15px', background: '#0f3460', color: '#fff',
    border: 'none', borderRadius: 10, fontSize: 16, fontWeight: 700,
    cursor: 'pointer', marginTop: 8
  },
  btnDisabled: {
    width: '100%', padding: '15px', background: '#aaa', color: '#fff',
    border: 'none', borderRadius: 10, fontSize: 16, cursor: 'not-allowed', marginTop: 8
  },
  errorBox: {
    background: '#fff0f0', border: '1px solid #ffcccc', color: '#cc0000',
    padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 10
  },
  successBox: {
    background: '#f0fff4', border: '1px solid #86efac', color: '#166534',
    padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 10
  },
};