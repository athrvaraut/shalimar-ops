import React, { useState } from 'react';

interface Props { token: string; onBack: () => void; }

const today = () => new Date().toISOString().split('T')[0];

const SECTIONS = [
  { key: 'sep_units', label: 'SEP' },
  { key: 'prep_units', label: 'PREP' },
  { key: 'solar_units', label: 'Solar' },
  { key: 'silo_units', label: 'Silo' },
  { key: 'doc_units', label: 'DOC' },
  { key: 'dsilo_units', label: 'D-Silo' },
  { key: 'acm_units', label: 'ACM' },
  { key: 'boiler_units', label: 'Boiler' },
  { key: 'chp_units', label: 'CHP' },
  { key: 'dm_units', label: 'DM Plant' },
  { key: 'ug_tank_units', label: 'UG Tank' },
  { key: 'refinery_units', label: 'Refinery' },
  { key: 'etp_units', label: 'ETP' },
  { key: 'packing_units', label: 'Packing' },
  { key: 'admin_units', label: 'Admin' },
  { key: 'dg_units', label: 'DG Set' },
  { key: 'msedcl_units', label: 'MSEDCL' },
];

export default function PowerConsumptionForm({ token, onBack }: Props) {
  const initForm = () => {
    const base: any = { reading_date: today(), power_kvah: '', power_factor: '',
      diesel_opening_stock: '', diesel_received: '', diesel_consumed: '',
      dg_generated_units: '', dg_reason: '' };
    SECTIONS.forEach(s => base[s.key] = '');
    return base;
  };

  const [form, setForm] = useState(initForm());
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const set = (field: string, val: string) =>
    setForm((prev: any) => ({ ...prev, [field]: val }));

  // Live totals
  const totalUnits = SECTIONS.reduce((sum, s) =>
    sum + (parseFloat(form[s.key]) || 0), 0);
  const solarUnits = parseFloat(form.solar_units) || 0;
  const msedclUnits = parseFloat(form.msedcl_units) || 0;
  const gridUnits = msedclUnits + (parseFloat(form.dg_units) || 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload: any = { ...form };
    const numFields = [...SECTIONS.map(s => s.key),
      'power_kvah', 'power_factor', 'diesel_opening_stock',
      'diesel_received', 'diesel_consumed', 'dg_generated_units'];
    numFields.forEach(f => {
      payload[f] = payload[f] !== '' ? parseFloat(payload[f]) : 0;
    });

    try {
      const res = await fetch('http://127.0.0.1:8000/power-consumption', {
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
        setForm(initForm());
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
          <div style={s.headerTitle}>Power Consumption Report</div>
          <div style={s.headerSub}>Daily units per section · Solar tracking</div>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={s.form}>

        {/* Date */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📅 Report Date</div>
          <div style={{ maxWidth: 200 }}>
            <label style={s.label}>Date *</label>
            <input style={s.input} type="date" value={form.reading_date}
              onChange={e => set('reading_date', e.target.value)} required />
          </div>
        </div>

        {/* Live summary panel */}
        <div style={{ ...s.section, background: '#f0fdf4', border: '2px solid #86efac' }}>
          <div style={s.sectionTitle}>⚡ Live Summary</div>
          <div style={s.ratioGrid}>
            <SummaryBox label="Total Consumption" value={`${totalUnits.toFixed(0)} KWH`} color="#0f3460" />
            <SummaryBox label="Solar Generated" value={`${solarUnits.toFixed(0)} KWH`} color="#059669" />
            <SummaryBox label="Grid (MSEDCL+DG)" value={`${gridUnits.toFixed(0)} KWH`} color="#7c3aed" />
            <SummaryBox label="Solar Savings %" value={
              totalUnits > 0 ? `${((solarUnits / totalUnits) * 100).toFixed(1)}%` : '—'
            } color="#ea580c" />
          </div>
        </div>

        {/* All 17 sections */}
        <div style={s.section}>
          <div style={s.sectionTitle}>🏭 Section-wise Units (KWH)</div>
          <div style={s.grid4}>
            {SECTIONS.map(sec => (
              <div key={sec.key} style={s.field}>
                <label style={s.label}>{sec.label}</label>
                <input style={s.input} type="number" step="any"
                  value={form[sec.key]}
                  onChange={e => set(sec.key, e.target.value)}
                  placeholder="0" />
              </div>
            ))}
          </div>
        </div>

        {/* Power quality */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📊 Power Quality</div>
          <div style={s.row2}>
            <div style={s.field}>
              <label style={s.label}>Total kVAh</label>
              <input style={s.input} type="number" step="any"
                value={form.power_kvah} onChange={e => set('power_kvah', e.target.value)}
                placeholder="—" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Power Factor</label>
              <input style={s.input} type="number" step="0.01" min="0" max="1"
                value={form.power_factor} onChange={e => set('power_factor', e.target.value)}
                placeholder="0.95" />
            </div>
          </div>
        </div>

        {/* DG / Diesel */}
        <div style={s.section}>
          <div style={s.sectionTitle}>🛢️ DG Set & Diesel</div>
          <div style={s.grid4}>
            <div style={s.field}>
              <label style={s.label}>Diesel Opening Stock (L)</label>
              <input style={s.input} type="number" step="any"
                value={form.diesel_opening_stock}
                onChange={e => set('diesel_opening_stock', e.target.value)} placeholder="—" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Diesel Received (L)</label>
              <input style={s.input} type="number" step="any"
                value={form.diesel_received}
                onChange={e => set('diesel_received', e.target.value)} placeholder="—" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Diesel Consumed (L)</label>
              <input style={s.input} type="number" step="any"
                value={form.diesel_consumed}
                onChange={e => set('diesel_consumed', e.target.value)} placeholder="—" />
            </div>
            <div style={s.field}>
              <label style={s.label}>DG Units Generated</label>
              <input style={s.input} type="number" step="any"
                value={form.dg_generated_units}
                onChange={e => set('dg_generated_units', e.target.value)} placeholder="—" />
            </div>
          </div>
          <div style={{ ...s.field, marginTop: 10 }}>
            <label style={s.label}>DG Reason (if used)</label>
            <input style={s.input} type="text"
              value={form.dg_reason}
              onChange={e => set('dg_reason', e.target.value)}
              placeholder="e.g. Power failure 14:00–15:30" />
          </div>
        </div>

        {error && <div style={s.errorBox}>❌ {error}</div>}
        {success && (
          <div style={s.successBox}>
            ✅ Power consumption report submitted! Total: {totalUnits.toFixed(0)} KWH
          </div>
        )}

        <button type="submit" style={loading ? s.btnDisabled : s.btn} disabled={loading}>
          {loading ? 'Submitting...' : '📤 Submit Power Report'}
        </button>
      </form>
    </div>
  );
}

function SummaryBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: 10, padding: '12px 14px', textAlign: 'center' as const }}>
      <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' as const, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: '#f0f2f5', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', overflowX: 'hidden' },
  header: { background: '#0f3460', color: '#fff', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16, position: 'sticky', top: 0, zIndex: 10 },
  headerTitle: { fontSize: 16, fontWeight: 700 },
  headerSub: { fontSize: 11, opacity: 0.75, marginTop: 2 },
  backBtn: { background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 13 },
  form: { maxWidth: 720, margin: '0 auto', padding: '20px 16px 40px' },
  section: { background: '#fff', borderRadius: 12, padding: '16px 18px', marginBottom: 14, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  sectionTitle: { fontSize: 13, fontWeight: 700, color: '#0f3460', marginBottom: 14, paddingBottom: 8, borderBottom: '1px solid #f0f0f0' },
  grid4: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 },
  ratioGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 },
  row2: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { fontSize: 11, fontWeight: 600, color: '#555', textTransform: 'uppercase', letterSpacing: '0.04em' },
  input: { padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 15, outline: 'none', width: '100%', boxSizing: 'border-box' },
  btn: { width: '100%', padding: '15px', background: '#0f3460', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, fontWeight: 700, cursor: 'pointer', marginTop: 8 },
  btnDisabled: { width: '100%', padding: '15px', background: '#aaa', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, cursor: 'not-allowed', marginTop: 8 },
  errorBox: { background: '#fff0f0', border: '1px solid #ffcccc', color: '#cc0000', padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 10 },
  successBox: { background: '#f0fff4', border: '1px solid #86efac', color: '#166534', padding: '12px 16px', borderRadius: 8, fontSize: 14, marginBottom: 10 },
};