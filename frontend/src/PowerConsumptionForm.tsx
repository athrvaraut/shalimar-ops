import React, { useState, useEffect } from 'react';

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
];

export default function PowerConsumptionForm({ token, onBack }: Props) {
  const initForm = () => {
    const base: any = {
      operator_name: '',
      msedcl_kwh: '',
      msedcl_kvah: '',
      reading_date: today(), power_kvah: '', power_factor: '',
      diesel_opening_stock: '', diesel_received: '', diesel_consumed: '',
      other_consumed: '', dg_generated_units: '', dg_reason: '',

      // Voltages
      voltage_r_morning: '', voltage_y_morning: '', voltage_b_morning: '',
      voltage_r_evening: '', voltage_y_evening: '', voltage_b_evening: '',

      // Currents
      current_l1: '', current_l2: '', current_l3: ''
    };
    SECTIONS.forEach(s => base[s.key] = '');
    return base;
  };

  const [locked, setLocked] = useState(false);
  const [existingId, setExistingId] = useState<number | null>(null);
  const [fetchingDate, setFetchingDate] = useState(false);
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

  useEffect(() => {
    if (!form.reading_date) return;
    const authToken = token || localStorage.getItem('token') || '';
    setFetchingDate(true);
    fetch(`https://shalimar-ops.onrender.com/power-consumption/date/${form.reading_date}`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    }).then(r => {
      if (r.ok) return r.json();
      throw new Error('not found');
    }).then(data => {
      if (data && data.id) {
        setExistingId(data.id);
        setLocked(true);
        // Pre-fill the form
        SECTIONS.forEach(sec => {
          if (data[sec.key] !== undefined) {
            setForm((prev: any) => ({ ...prev, [sec.key]: String(data[sec.key] || '') }));
          }
        });
        setForm((prev: any) => ({
          ...prev,
          msedcl_kwh: String(data.msedcl_units || ''),
          power_kvah: String(data.power_kvah || ''),
          diesel_opening_stock: String(data.diesel_opening_stock || ''),
          diesel_received: String(data.diesel_received || ''),
          diesel_consumed: String(data.diesel_consumed || ''),
          dg_generated_units: String(data.dg_generated_units || ''),
          dg_reason: data.dg_reason || '',
        }));
      }
    }).catch(() => {
      setLocked(false);
      setExistingId(null);
    }).finally(() => setFetchingDate(false));
  }, [form.reading_date]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload: any = { ...form };
    const numFields = [
      ...SECTIONS.map(s => s.key),
      'power_kvah', 'power_factor', 'diesel_opening_stock',
      'diesel_received', 'diesel_consumed', 'other_consumed', 'dg_generated_units',
      'voltage_r_morning', 'voltage_y_morning', 'voltage_b_morning',
      'voltage_r_evening', 'voltage_y_evening', 'voltage_b_evening',
      'current_l1', 'current_l2', 'current_l3'
    ];

    numFields.forEach(f => {
      // If it's empty, send null (or 0) so the backend doesn't crash
      payload[f] = payload[f] !== '' && payload[f] !== undefined ? parseFloat(payload[f]) : 0;
    });

    // Map msedcl_kwh → msedcl_units (backend column name)
    payload.msedcl_units = parseFloat(form.msedcl_kwh) || 0;
    // Auto-calculate power factor
    if (payload.msedcl_units > 0 && payload.power_kvah > 0) {
      payload.power_factor = parseFloat((payload.msedcl_units / payload.power_kvah).toFixed(4));
    }

    try {
      const res = await fetch('https://shalimar-ops.onrender.com/power-consumption', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token || localStorage.getItem('token') || ''}`
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

      {/* After the header div, before the form */}
      {locked && (
        <div style={{
          background: '#fef9c3', borderBottom: '1px solid #fde047',
          padding: '10px 20px', fontSize: 13, color: '#854d0e', textAlign: 'center' as const
        }}>
          🔒 Power entry for {form.reading_date} already submitted.{' '}
          <button onClick={() => setLocked(false)}
            style={{
              background: '#f59e0b', color: '#fff', border: 'none', borderRadius: 6,
              padding: '4px 12px', cursor: 'pointer', fontWeight: 700, marginLeft: 8
            }}>
            ✏️ Modify
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} style={s.form}>

        {/* Date */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📅 Report Date</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div style={s.field}>
              <label style={s.label}>Date *</label>
              <input style={s.input} type="date" value={form.reading_date}
                onChange={e => set('reading_date', e.target.value)} disabled={locked} required />
            </div>
            <div style={s.field}>
              <label style={s.label}>Operator Name *</label>
              <input style={s.input} type="text"
                value={form.operator_name}
                onChange={e => set('operator_name', e.target.value)}
                placeholder="e.g. Pankaj Bhejraj"
                disabled={locked} required />
            </div>
          </div>
        </div>

        {/* Live summary panel */}
        <div style={{ ...s.section, background: '#f0fdf4', border: '2px solid #86efac' }}>
          <div style={s.sectionTitle}>⚡ Live Summary</div>
          <div style={s.ratioGrid}>
            <SummaryBox label="Total KWH" value={`${totalUnits.toFixed(0)}`} color="#0f3460" />
            <SummaryBox label="Total KVAh" value={form.power_kvah ? `${parseFloat(form.power_kvah).toFixed(0)}` : '—'} color="#7c3aed" />
            <SummaryBox label="Solar KWH" value={`${solarUnits.toFixed(0)}`} color="#059669" />
            <SummaryBox label="MSEDCL KWH" value={form.msedcl_units ? `${parseFloat(form.msedcl_units).toFixed(0)}` : '—'} color="#0284c7" />
            <SummaryBox label="DG KWH" value={`${(parseFloat(form.dg_units) || 0).toFixed(0)}`} color="#d97706" />
            <SummaryBox label="Solar Savings %" value={totalUnits > 0 ? `${((solarUnits / totalUnits) * 100).toFixed(1)}%` : '—'} color="#ea580c" />
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
                  placeholder="0" disabled={locked} />
              </div>
            ))}
          </div>
        </div>

        {/* Power quality */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📊 Power Quality</div>
          <div style={s.row3}>
            <div style={s.field}>
              <label style={s.label}>MSEDCL KWH (Units)</label>
              <input style={s.input} type="number" step="any"
                value={form.msedcl_kwh}
                onChange={e => set('msedcl_kwh', e.target.value)}
                placeholder="e.g. 25680" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>Total kVAh (MSEDCL)</label>
              <input style={s.input} type="number" step="any"
                value={form.power_kvah}
                onChange={e => set('power_kvah', e.target.value)}
                placeholder="e.g. 25710" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>Power Factor (Auto)</label>
              <input style={{ ...s.input, background: '#f0fdf4', fontWeight: 700 }}
                type="text" readOnly
                value={
                  form.msedcl_kwh && form.power_kvah && parseFloat(form.power_kvah) > 0
                    ? (parseFloat(form.msedcl_kwh) / parseFloat(form.power_kvah)).toFixed(4)
                    : '—'
                } />
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
                onChange={e => set('diesel_opening_stock', e.target.value)} placeholder="—" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>Diesel Received (L)</label>
              <input style={s.input} type="number" step="any"
                value={form.diesel_received}
                onChange={e => set('diesel_received', e.target.value)} placeholder="—" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>D.G. Consumption (L)</label>
              <input style={s.input} type="number" step="any"
                value={form.diesel_consumed}
                onChange={e => set('diesel_consumed', e.target.value)} placeholder="—" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>Other Consumption (L)</label>
              <input style={s.input} type="number" step="any"
                value={form.other_consumed}
                onChange={e => set('other_consumed', e.target.value)} placeholder="—" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>DG Units Generated</label>
              <input style={s.input} type="number" step="any"
                value={form.dg_generated_units}
                onChange={e => set('dg_generated_units', e.target.value)} placeholder="—" disabled={locked} />
            </div>
          </div>
          <div style={{ ...s.field, marginTop: 10 }}>
            <label style={s.label}>DG Reason (if used)</label>
            <input style={s.input} type="text"
              value={form.dg_reason}
              onChange={e => set('dg_reason', e.target.value)}
              placeholder="e.g. Power failure 14:00–15:30" disabled={locked} />
          </div>
        </div>

        {error && <div style={s.errorBox}>❌ {error}</div>}
        {success && (
          <div style={s.successBox}>
            ✅ Power consumption report submitted! Total: {totalUnits.toFixed(0)} KWH
          </div>
        )}
        {/* Voltage Readings */}
        <div style={s.section}>
          <div style={s.sectionTitle}>⚡ Voltage & Current Readings</div>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 10 }}>
            Read from MFM-13 (red VOLT display) and Secure Elite 440
          </div>
          <div style={s.row3}>
            <div style={s.field}>
              <label style={s.label}>L1R Voltage (V)</label>
              <input style={s.input} type="number" step="0.1"
                value={form.voltage_r_morning}
                onChange={e => set('voltage_r_morning', e.target.value)}
                placeholder="e.g. 374.7" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>L2Y Voltage (V)</label>
              <input style={s.input} type="number" step="0.1"
                value={form.voltage_y_morning}
                onChange={e => set('voltage_y_morning', e.target.value)}
                placeholder="e.g. 373.6" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>L3B Voltage (V)</label>
              <input style={s.input} type="number" step="0.1"
                value={form.voltage_b_morning}
                onChange={e => set('voltage_b_morning', e.target.value)}
                placeholder="e.g. 374.4" disabled={locked} />
            </div>
          </div>
          <div style={s.row3}>
            <div style={s.field}>
              <label style={s.label}>Phase R Current (A)</label>
              <input style={s.input} type="number"
                value={form.current_l1}
                onChange={e => set('current_l1', e.target.value)}
                placeholder="e.g. 1558" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}>Phase Y Current (A)</label>
              <input style={s.input} type="number"
                value={form.current_l2}
                onChange={e => set('current_l2', e.target.value)}
                placeholder="e.g. 1688" disabled={locked} />
            </div>
            <div style={s.field}>
              <label style={s.label}> Phase B Current (A)</label>
              <input style={s.input} type="number"
                value={form.current_l3}
                onChange={e => set('current_l3', e.target.value)}
                placeholder="e.g. 1557" disabled={locked} />
            </div>
          </div>

          {/* Live current imbalance warning */}
          {form.current_l1 && form.current_l2 && form.current_l3 && (() => {
            const avg = (parseFloat(form.current_l1) + parseFloat(form.current_l2) + parseFloat(form.current_l3)) / 3;
            const max = Math.max(parseFloat(form.current_l1), parseFloat(form.current_l2), parseFloat(form.current_l3));
            const imbalance = ((max - avg) / avg * 100).toFixed(1);
            if (parseFloat(imbalance) > 5) return (
              <div style={{
                background: '#fff0f0', border: '1px solid #fecaca',
                color: '#dc2626', padding: '10px 14px', borderRadius: 8,
                fontSize: 13, marginTop: 10
              }}>
                ⚠️ Current imbalance: {imbalance}% (limit: 5%). Phase 2 overloaded.
                Logged as evidence. Inform HOD.
              </div>
            );
            return null;
          })()}
        </div>

        <button type="submit" style={loading || locked ? s.btnDisabled : s.btn} disabled={loading || locked}>
          {loading ? 'Processing...' : existingId ? '💾 Update Power Report' : '📤 Submit Power Report'}
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
  select: { padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff', width: '100%', boxSizing: 'border-box' as const },
  btn: { width: '100%', padding: '15px', background: '#0f3460', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, fontWeight: 700, cursor: 'pointer', marginTop: 8 },
  btnDisabled: { width: '100%', padding: '15px', background: '#aaa', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, cursor: 'not-allowed', marginTop: 8 },
  errorBox: { background: '#fff0f0', border: '1px solid #ffcccc', color: '#cc0000', padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 10 },
  successBox: { background: '#f0fff4', border: '1px solid #86efac', color: '#166534', padding: '12px 16px', borderRadius: 8, fontSize: 14, marginBottom: 10 },
};