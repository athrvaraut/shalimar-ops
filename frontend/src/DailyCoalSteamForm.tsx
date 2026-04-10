import React, { useState } from 'react';

interface Props { token: string; onBack: () => void; }

const today = () => new Date().toISOString().split('T')[0];

export default function DailyCoalSteamForm({ token, onBack }: Props) {
  const [form, setForm] = useState({
    report_date: today(),
    opening_coal_stock: '',
    coal_arrival_indian: '',
    coal_arrival_imported: '',
    coal_consumed_sep: '',
    coal_consumed_refinery: '',
    coal_thermic: '',
    steam_sep_opening: '',
    steam_sep_closing: '',
    steam_refl_opening: '',
    steam_refl_closing: '',
    feed_water_temp: '',
    coal_bunker_pct: '',
    steam_pressure_ok: true,
    coal_rate_per_mt: '',
    coal_gcv: '',
  });

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const set = (field: string, val: string | boolean) =>
    setForm(prev => ({ ...prev, [field]: val }));

  // Auto-calculations — live preview
  const totalCoal = (
    (parseFloat(form.coal_consumed_sep) || 0) +
    (parseFloat(form.coal_consumed_refinery) || 0) +
    (parseFloat(form.coal_thermic) || 0)
  );
  const closingStock = (
    (parseFloat(form.opening_coal_stock) || 0) +
    (parseFloat(form.coal_arrival_indian) || 0) +
    (parseFloat(form.coal_arrival_imported) || 0) -
    totalCoal
  );
  const steamSep = (parseFloat(form.steam_sep_closing) || 0) - (parseFloat(form.steam_sep_opening) || 0);
  const steamRefl = (parseFloat(form.steam_refl_closing) || 0) - (parseFloat(form.steam_refl_opening) || 0);
  const totalSteam = steamSep + steamRefl;
  const csRatio = totalCoal > 0 ? (totalSteam / totalCoal).toFixed(3) : '—';
  const csRatioNum = totalCoal > 0 ? totalSteam / totalCoal : null;
  const csWarn = csRatioNum !== null && (csRatioNum < 5.0 || csRatioNum > 5.6);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const numFields = [
      'opening_coal_stock','coal_arrival_indian','coal_arrival_imported',
      'coal_consumed_sep','coal_consumed_refinery','coal_thermic',
      'steam_sep_opening','steam_sep_closing','steam_refl_opening',
      'steam_refl_closing','feed_water_temp','coal_bunker_pct',
      'coal_rate_per_mt','coal_gcv'
    ];

    const payload: any = { ...form };
    numFields.forEach(f => {
      payload[f] = payload[f] !== '' ? parseFloat(payload[f]) : 0;
    });

    try {
      const res = await fetch('https://shalimar-ops.onrender.com/daily-report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 4000);
      } else {
        const data = await res.json();
        setError(JSON.stringify(data.detail || 'Submission failed'));
      }
    } catch {
      setError('Cannot connect to server');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.page}>
      <div style={s.header}>
        <button onClick={onBack} style={s.backBtn}>← Back</button>
        <div>
          <div style={s.headerTitle}>Daily Coal & Steam Report</div>
          <div style={s.headerSub}>Auto-calculates C/S ratio · Boiler No. 15936</div>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={s.form}>

        {/* Date */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📅 Report Date</div>
          <div style={s.field}>
            <label style={s.label}>Date *</label>
            <input style={s.input} type="date" value={form.report_date}
              onChange={e => set('report_date', e.target.value)} required />
          </div>
        </div>

        {/* Live C/S Ratio Panel */}
        <div style={{
          ...s.section,
          background: csWarn ? '#fff8f0' : '#f0fdf4',
          border: `2px solid ${csWarn ? '#f97316' : '#86efac'}`
        }}>
          <div style={s.sectionTitle}>
            {csWarn ? '⚠️' : '✅'} Live C/S Ratio (Auto-calculated)
          </div>
          <div style={s.ratioGrid}>
            <RatioBox label="Total Coal (MT)" value={totalCoal > 0 ? totalCoal.toFixed(3) : '—'} />
            <RatioBox label="Steam SEP (KG)" value={steamSep > 0 ? steamSep.toFixed(0) : '—'} />
            <RatioBox label="Steam REFL (KG)" value={steamRefl > 0 ? steamRefl.toFixed(0) : '—'} />
            <RatioBox label="Total Steam (KG)" value={totalSteam > 0 ? totalSteam.toFixed(0) : '—'} />
            <RatioBox label="Closing Stock (MT)" value={closingStock.toFixed(3)} />
            <div style={{ ...s.ratioBox, background: csWarn ? '#fff0e0' : '#d1fae5', gridColumn: 'span 1' }}>
              <div style={s.ratioLabel}>C/S RATIO</div>
              <div style={{
                ...s.ratioValue,
                fontSize: 28,
                color: csWarn ? '#ea580c' : '#059669'
              }}>
                {csRatio}
              </div>
              {csWarn && csRatioNum && (
                <div style={{ fontSize: 10, color: '#ea580c', marginTop: 2 }}>
                  Target: 5.0–5.6
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Coal Stock */}
        <div style={s.section}>
          <div style={s.sectionTitle}>🪨 Coal Stock & Consumption</div>
          <div style={s.row3}>
            <Inp label="Opening Coal Stock (MT)" value={form.opening_coal_stock}
              onChange={v => set('opening_coal_stock', v)} required />
            <Inp label="Coal Arrival — Indian (MT)" value={form.coal_arrival_indian}
              onChange={v => set('coal_arrival_indian', v)} />
            <Inp label="Coal Arrival — Imported (MT)" value={form.coal_arrival_imported}
              onChange={v => set('coal_arrival_imported', v)} />
          </div>
          <div style={s.row3}>
            <Inp label="Coal Consumed — SEP (MT)" value={form.coal_consumed_sep}
              onChange={v => set('coal_consumed_sep', v)} required />
            <Inp label="Coal Consumed — Refinery (MT)" value={form.coal_consumed_refinery}
              onChange={v => set('coal_consumed_refinery', v)} required />
            <Inp label="Coal to Thermic Boiler (MT)" value={form.coal_thermic}
              onChange={v => set('coal_thermic', v)} />
          </div>
          {/* Auto-calculated display */}
          <div style={s.calcRow}>
            <div style={s.calcBox}>
              <span style={s.calcLabel}>Total Coal Consumed</span>
              <span style={s.calcValue}>{totalCoal > 0 ? `${totalCoal.toFixed(3)} MT` : '—'}</span>
            </div>
            <div style={s.calcBox}>
              <span style={s.calcLabel}>Closing Stock</span>
              <span style={s.calcValue}>{`${closingStock.toFixed(3)} MT`}</span>
            </div>
          </div>
        </div>

        {/* Steam Meter Readings */}
        <div style={s.section}>
          <div style={s.sectionTitle}>♨️ Steam Meter Readings (KG)</div>
          <div style={{ marginBottom: 10, fontSize: 12, color: '#666' }}>
            Enter the meter reading at start and end of day
          </div>
          <div style={s.row2}>
            <Inp label="SEP Steam — Opening Reading" value={form.steam_sep_opening}
              onChange={v => set('steam_sep_opening', v)} required />
            <Inp label="SEP Steam — Closing Reading" value={form.steam_sep_closing}
              onChange={v => set('steam_sep_closing', v)} required />
          </div>
          <div style={s.calcRow}>
            <div style={s.calcBox}>
              <span style={s.calcLabel}>SEP Steam Consumed</span>
              <span style={s.calcValue}>{steamSep > 0 ? `${steamSep.toFixed(0)} KG` : '—'}</span>
            </div>
          </div>
          <div style={s.row2}>
            <Inp label="REFL Steam — Opening Reading" value={form.steam_refl_opening}
              onChange={v => set('steam_refl_opening', v)} required />
            <Inp label="REFL Steam — Closing Reading" value={form.steam_refl_closing}
              onChange={v => set('steam_refl_closing', v)} required />
          </div>
          <div style={s.calcRow}>
            <div style={s.calcBox}>
              <span style={s.calcLabel}>REFL Steam Consumed</span>
              <span style={s.calcValue}>{steamRefl > 0 ? `${steamRefl.toFixed(0)} KG` : '—'}</span>
            </div>
            <div style={s.calcBox}>
              <span style={s.calcLabel}>Total Steam</span>
              <span style={s.calcValue}>{totalSteam > 0 ? `${totalSteam.toFixed(0)} KG` : '—'}</span>
            </div>
          </div>
        </div>

        {/* Other Parameters */}
        <div style={s.section}>
          <div style={s.sectionTitle}>⚙️ Other Parameters</div>
          <div style={s.row3}>
            <Inp label="Feed Water Temp (°C)" value={form.feed_water_temp}
              onChange={v => set('feed_water_temp', v)} />
            <Inp label="Coal Bunker Level (%)" value={form.coal_bunker_pct}
              onChange={v => set('coal_bunker_pct', v)} />
            <div style={s.field}>
              <label style={s.label}>Steam Pressure OK?</label>
              <select style={s.select}
                value={form.steam_pressure_ok ? 'yes' : 'no'}
                onChange={e => set('steam_pressure_ok', e.target.value === 'yes')}>
                <option value="yes">Yes — Normal</option>
                <option value="no">No — Problem</option>
              </select>
            </div>
          </div>
          <div style={s.row2}>
            <Inp label="Coal Rate per MT (₹)" value={form.coal_rate_per_mt}
              onChange={v => set('coal_rate_per_mt', v)}
              hint="Father updates monthly" />
            <Inp label="Coal GCV (Kcal/kg)" value={form.coal_gcv}
              onChange={v => set('coal_gcv', v)} />
          </div>
        </div>

        {error && <div style={s.errorBox}>❌ {error}</div>}
        {success && (
          <div style={s.successBox}>
            ✅ Daily report submitted! C/S Ratio: <strong>{csRatio}</strong>
          </div>
        )}

        <button type="submit"
          style={loading ? s.btnDisabled : s.btn}
          disabled={loading}>
          {loading ? 'Submitting...' : '📤 Submit Daily Report'}
        </button>
      </form>
    </div>
  );
}

function Inp({ label, value, onChange, required, hint }: {
  label: string; value: string;
  onChange: (v: string) => void;
  required?: boolean; hint?: string;
}) {
  return (
    <div style={s.field}>
      <label style={s.label}>
        {label}
        {hint && <span style={{ fontWeight: 400, color: '#999', textTransform: 'none' as const }}> · {hint}</span>}
      </label>
      <input style={s.input} type="number" step="any"
        value={value} onChange={e => onChange(e.target.value)}
        placeholder="—" required={required} />
    </div>
  );
}

function RatioBox({ label, value }: { label: string; value: string }) {
  return (
    <div style={s.ratioBox}>
      <div style={s.ratioLabel}>{label}</div>
      <div style={s.ratioValue}>{value}</div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: '#f0f2f5', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' },
  header: { background: '#0f3460', color: '#fff', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16, position: 'sticky', top: 0, zIndex: 10 },
  headerTitle: { fontSize: 16, fontWeight: 700 },
  headerSub: { fontSize: 11, opacity: 0.75, marginTop: 2 },
  backBtn: { background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13 },
  form: { maxWidth: 720, margin: '0 auto', padding: '20px 16px 40px' },
  section: { background: '#fff', borderRadius: 12, padding: '16px 18px', marginBottom: 14, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  sectionTitle: { fontSize: 13, fontWeight: 700, color: '#0f3460', marginBottom: 14, paddingBottom: 8, borderBottom: '1px solid #f0f0f0' },
  row3: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 10 },
  row2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 10 },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { fontSize: 11, fontWeight: 600, color: '#555', textTransform: 'uppercase', letterSpacing: '0.04em' },
  input: { padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 15, outline: 'none', width: '100%', boxSizing: 'border-box' },
  select: { padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff' },
  calcRow: { display: 'flex', gap: 10, marginTop: 6, marginBottom: 10 },
  calcBox: { flex: 1, background: '#f8f9fa', borderRadius: 8, padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  calcLabel: { fontSize: 12, color: '#666' },
  calcValue: { fontSize: 14, fontWeight: 700, color: '#0f3460' },
  ratioGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 },
  ratioBox: { background: '#f8f9fa', borderRadius: 10, padding: '12px 14px', textAlign: 'center' },
  ratioLabel: { fontSize: 10, color: '#888', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 },
  ratioValue: { fontSize: 18, fontWeight: 700, color: '#111' },
  btn: { width: '100%', padding: '15px', background: '#0f3460', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, fontWeight: 700, cursor: 'pointer', marginTop: 8 },
  btnDisabled: { width: '100%', padding: '15px', background: '#aaa', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, cursor: 'not-allowed', marginTop: 8 },
  errorBox: { background: '#fff0f0', border: '1px solid #ffcccc', color: '#cc0000', padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 10 },
  successBox: { background: '#f0fff4', border: '1px solid #86efac', color: '#166534', padding: '12px 16px', borderRadius: 8, fontSize: 14, marginBottom: 10 },
};