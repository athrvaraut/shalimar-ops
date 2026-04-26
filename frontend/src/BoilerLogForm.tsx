import React, { useState } from 'react';

interface BoilerLogFormProps {
  token: string;
  onBack: () => void;
}

const SHIFT_TIME_SLOTS: Record<string, string[]> = {
  'A': ['07:00', '09:00', '11:00', '13:00'],
  'B': ['15:00', '17:00', '19:00', '21:00'],
  'C': ['23:00', '01:00', '03:00', '05:00'],
};

const today = () => new Date().toISOString().split('T')[0];
const currentShift = () => {
  const h = new Date().getHours();
  if (h >= 7 && h < 15) return 'A';
  if (h >= 15 && h < 23) return 'B';
  return 'C';
};

export default function BoilerLogForm({ token, onBack }: BoilerLogFormProps) {
  const [form, setForm] = useState({
    shift: currentShift(),
    log_date: today(),
    log_time: '07:00',
    operator_name: '',
    steam_pressure: '',
    steam_flow_sep: '',
    steam_flow_refl: '',
    drum_water_level: '',
    bed1_top_temp: '',
    bed1_bottom_temp: '',
    bed2_top_temp: '',
    bed2_bottom_temp: '',
    flue_gas_temp: '',
    coal_feed_bed1_hz: '',
    coal_feed_bed2_hz: '',
    cbd_ibd_report: '',
    id_fan_damper: '',
    fd_fan1_damper: '',
    fd_fan2_damper: '',
    booster_fan1: '',
    booster_fan2: '',
    gag_filter_temp: '',
    breakdown_problem: '',
    feed_water_temp: '',
    fd_pressure: '',
    remarks: '',
    coal_opening_stock: '',
    coal_arrival: '', // <-- Combined into a single field just like you asked!
    coal_consumed_sep: '',
    coal_consumed_refinery: '',
    coal_thermic: '',
    steam_sep_opening: '',
    steam_sep_closing: '',
    steam_refl_opening: '',
    steam_refl_closing: '',
    feed_water_temp_daily: '',
    coal_bunker_pct: '',
    steam_pressure_ok: true,
    coal_rate_per_mt: '',
    coal_gcv: '',
    coal_section_filled: false
  });

  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const validate = () => {
    const w: string[] = [];
    const p = parseFloat(form.steam_pressure);
    const f = parseFloat(form.flue_gas_temp);

    if (form.steam_pressure && (p < 8 || p > 12))
      w.push(`⚠️ Steam Pressure ${p} is outside safe range (8–12 KG/CM)`);
    if (form.flue_gas_temp && f > 220)
      w.push(`⚠️ Flue Gas Temp ${f}°C is too high (max 220°C)`);
    return w;
  };

  const set = (field: string, val: string) =>
    setForm(prev => ({ ...prev, [field]: val }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const w = validate();
    setWarnings(w);
    if (w.length > 0) {
      const confirmed = window.confirm(
        w.join('\n') + '\n\nDo you still want to submit?'
      );
      if (!confirmed) return;
    }

    setLoading(true);
    setError('');

    const payload: any = { ...form };
    // Convert numeric strings to numbers, keep empty as null
    const numericFields = [
      'steam_pressure', 'steam_flow_sep', 'steam_flow_refl', 'drum_water_level',
      'bed1_top_temp', 'bed1_bottom_temp', 'bed2_top_temp', 'bed2_bottom_temp',
      'flue_gas_temp', 'coal_feed_bed1_hz', 'coal_feed_bed2_hz',
      'id_fan_damper', 'fd_fan1_damper', 'fd_fan2_damper',
      'booster_fan1', 'booster_fan2', 'gag_filter_temp',
      'feed_water_temp', 'fd_pressure'
    ];
    numericFields.forEach(f => {
      payload[f] = payload[f] !== '' ? parseFloat(payload[f]) : null;
    });

    try {
      const res = await fetch('https://shalimar-ops.onrender.com/boiler-log', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        if (form.coal_section_filled) {

          try {
            const coalPayload = {
              report_date: form.log_date,
              opening_coal_stock: parseFloat(form.coal_opening_stock) || 0,
              // --- CHANGED: Combined into a single Coal Arrival field ---
              coal_arrival: parseFloat(form.coal_arrival) || 0, 
              coal_consumed_sep: parseFloat(form.coal_consumed_sep) || 0,
              coal_consumed_refinery: parseFloat(form.coal_consumed_refinery) || 0,
              coal_thermic: parseFloat(form.coal_thermic) || 0,
              steam_sep_opening: parseFloat(form.steam_sep_opening) || 0,
              steam_sep_closing: parseFloat(form.steam_sep_closing) || 0,
              steam_refl_opening: parseFloat(form.steam_refl_opening) || 0,
              steam_refl_closing: parseFloat(form.steam_refl_closing) || 0,
              feed_water_temp: parseFloat(form.feed_water_temp_daily) || 0,
              coal_bunker_pct: parseFloat(form.coal_bunker_pct) || 0,
              steam_pressure_ok: form.steam_pressure_ok,
              coal_rate_per_mt: parseFloat(form.coal_rate_per_mt) || 0,
              coal_gcv: parseFloat(form.coal_gcv) || 0,
            };
            await fetch('https://shalimar-ops.onrender.com/daily-report', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
              body: JSON.stringify(coalPayload),
            });
            // Silently succeeds or skips (upsert handles duplicate)
          } catch {
            console.log("Failed to submit daily coal summary");
          }
        }
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        // Reset numeric fields, keep shift/date/time
        setForm(prev => ({
          ...prev,
          steam_pressure: '', steam_flow_sep: '', steam_flow_refl: '',
          drum_water_level: '', bed1_top_temp: '', bed1_bottom_temp: '',
          bed2_top_temp: '', bed2_bottom_temp: '', flue_gas_temp: '',
          coal_feed_bed1_hz: '', coal_feed_bed2_hz: '', cbd_ibd_report: '',
          id_fan_damper: '', fd_fan1_damper: '', fd_fan2_damper: '',
          booster_fan1: '', booster_fan2: '', gag_filter_temp: '',
          breakdown_problem: '', feed_water_temp: '', fd_pressure: '', remarks: '',
        }));
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
      {/* Header */}
      <div style={s.header}>
        <button onClick={onBack} style={s.backBtn}>← Back</button>
        <div>
          <div style={s.headerTitle}>Boiler Log Entry</div>
          <div style={s.headerSub}>Boiler No. 15936 · Sonkhamb Plant</div>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={s.form}>

        {/* Shift / Date / Time */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📋 Shift Details</div>
          <div style={s.row3}>
            <div style={s.field}>
              <label style={s.label}>Shift *</label>
              <select style={s.select} value={form.shift}
                onChange={e => {
                  const newShift = e.target.value;
                  set('shift', newShift);
                  set('log_time', SHIFT_TIME_SLOTS[newShift][0]);
                }} required>
                <option value="A">Shift A (7AM–3PM)</option>
                <option value="B">Shift B (3PM–11PM)</option>
                <option value="C">Shift C (11PM–7AM)</option>
              </select>
              <div style={s.field}>
                <label style={s.label}>Operator Name * <span style={s.hint}>(as written in log book)</span></label>
                <input
                  style={s.input}
                  type="text"
                  value={form.operator_name}
                  onChange={e => set('operator_name', e.target.value)}
                  placeholder="e.g. Saurav Joshi"
                  required
                />
              </div>
            </div>
            <div style={s.field}>
              <label style={s.label}>Date *</label>
              <input style={s.input} type="date" value={form.log_date}
                onChange={e => set('log_date', e.target.value)} required />
            </div>
            <div style={s.field}>
              <label style={s.label}>Time *</label>
              <select style={s.select} value={form.log_time}
                onChange={e => set('log_time', e.target.value)} required>
                {SHIFT_TIME_SLOTS[form.shift as keyof typeof SHIFT_TIME_SLOTS].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Steam Parameters */}
        <div style={s.section}>
          <div style={s.sectionTitle}>♨️ Steam Parameters</div>
          <div style={s.row3}>
            <NumInput label="Steam Pressure (KG/CM)" hint="Safe: 6–12"
              value={form.steam_pressure} onChange={v => set('steam_pressure', v)}
              warn={!!form.steam_pressure && (parseFloat(form.steam_pressure) < 6 || parseFloat(form.steam_pressure) > 12)} />
            <NumInput label="Steam Flow SEP (KG)" hint=""
              value={form.steam_flow_sep} onChange={v => set('steam_flow_sep', v)} />
            <NumInput label="Steam Flow REFL (KG)" hint=""
              value={form.steam_flow_refl} onChange={v => set('steam_flow_refl', v)} />
          </div>
          <div style={s.row2}>
            <NumInput label="Drum Water Level (%)" hint="Safe: 50–70%"
              value={form.drum_water_level} onChange={v => set('drum_water_level', v)} />
            <NumInput label="Feed Water Temp (°C)" hint=""
              value={form.feed_water_temp} onChange={v => set('feed_water_temp', v)} />
          </div>
        </div>

        {/* Bed Temperatures */}
        <div style={s.section}>
          <div style={s.sectionTitle}>🌡️ Bed Temperatures (°C)</div>
          <div style={s.row2}>
            <NumInput label="Bed 1 Top Temp" value={form.bed1_top_temp} onChange={v => set('bed1_top_temp', v)} />
            <NumInput label="Bed 1 Bottom Temp" value={form.bed1_bottom_temp} onChange={v => set('bed1_bottom_temp', v)} />
          </div>
          <div style={s.row2}>
            <NumInput label="Bed 2 Top Temp" value={form.bed2_top_temp} onChange={v => set('bed2_top_temp', v)} />
            <NumInput label="Bed 2 Bottom Temp" value={form.bed2_bottom_temp} onChange={v => set('bed2_bottom_temp', v)} />
          </div>
          <div style={s.row2}>
            <NumInput label="Flue Gas Temp (°C)" hint="Normal: 200–215°C"
              value={form.flue_gas_temp} onChange={v => set('flue_gas_temp', v)} />
            <NumInput label="GAG Filter Inlet Temp (°C)" value={form.gag_filter_temp} onChange={v => set('gag_filter_temp', v)} />
          </div>
        </div>

        {/* Coal & Fans */}
        <div style={s.section}>
          <div style={s.sectionTitle}>⚙️ Coal Feed & Fan Settings</div>
          <div style={s.row2}>
            <NumInput label="Coal Feed Bed 1 (HZ)" value={form.coal_feed_bed1_hz} onChange={v => set('coal_feed_bed1_hz', v)} />
            <NumInput label="Coal Feed Bed 2 (HZ)" value={form.coal_feed_bed2_hz} onChange={v => set('coal_feed_bed2_hz', v)} />
          </div>
          <div style={s.row3}>
            <NumInput label="ID Fan Damper (%)" value={form.id_fan_damper} onChange={v => set('id_fan_damper', v)} />
            <NumInput label="FD Fan 1 Damper (%)" value={form.fd_fan1_damper} onChange={v => set('fd_fan1_damper', v)} />
            <NumInput label="FD Fan 2 Damper (%)" value={form.fd_fan2_damper} onChange={v => set('fd_fan2_damper', v)} />
          </div>
          <div style={s.row3}>
            <NumInput label="Booster Fan 1 (%)" value={form.booster_fan1} onChange={v => set('booster_fan1', v)} />
            <NumInput label="Booster Fan 2 (%)" value={form.booster_fan2} onChange={v => set('booster_fan2', v)} />
            <div style={s.field}>
              <label style={s.label}>FD Pressure (MM/WC)</label>
              <input
                style={s.input}
                type="text"
                value={form.fd_pressure}
                onChange={e => set('fd_pressure', e.target.value)}
                placeholder="e.g. 300/300"
              />
            </div>
          </div>
        </div>

        {/* Text fields */}
        <div style={s.section}>
          <div style={s.sectionTitle}>📝 Reports & Remarks</div>
          <div style={s.field}>
            <label style={s.label}>CBD/IBD Time and Report</label>
            <input style={s.input} value={form.cbd_ibd_report}
              onChange={e => set('cbd_ibd_report', e.target.value)}
              placeholder="e.g. CBD at 10:00, IBD at 14:00" />
          </div>
          <div style={s.field}>
            <label style={s.label}>Breakdown Problem</label>
            <textarea style={s.textarea} value={form.breakdown_problem}
              onChange={e => set('breakdown_problem', e.target.value)}
              placeholder="Describe any breakdown or issue (leave blank if none)"
              rows={2} />
          </div>
          <div style={s.field}>
            <label style={s.label}>Remarks</label>
            <textarea style={s.textarea} value={form.remarks}
              onChange={e => set('remarks', e.target.value)}
              placeholder="Any additional remarks"
              rows={2} />
          </div>
        </div>
        {/* Coal & Steam Daily Summary — Optional, filled once per day */}
        <div style={{ ...s.section, border: '2px solid #e0f2fe', background: '#f0f9ff' }}>
          <div style={s.sectionTitle}>
            🪨 Daily Coal & Steam Summary
            <span style={{ fontSize: 10, fontWeight: 400, color: '#666', marginLeft: 8 }}>
              Fill once per day (any shift)
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <input type="checkbox"
              checked={!!form.coal_section_filled}
              onChange={e => set('coal_section_filled', e.target.checked as any)}
              id="coal_toggle" />
            <label htmlFor="coal_toggle" style={{ fontSize: 13, cursor: 'pointer' }}>
              Fill Coal & Steam data for today
            </label>
          </div>
          {form.coal_section_filled && (
            <>
              <div style={s.row3}>
                <NumInput label="Opening Coal Stock (MT)" value={form.coal_opening_stock}
                  onChange={v => set('coal_opening_stock', v)} />
                {/* --- CHANGED: Combined into a single Coal Arrival field --- */}
                <NumInput label="Coal Arrival (MT)" value={form.coal_arrival}
                  onChange={v => set('coal_arrival', v)} />
              </div>
              <div style={s.row3}>
                <NumInput label="Coal Consumed SEP (MT)" value={form.coal_consumed_sep}
                  onChange={v => set('coal_consumed_sep', v)} />
                <NumInput label="Coal Consumed Refinery (MT)" value={form.coal_consumed_refinery}
                  onChange={v => set('coal_consumed_refinery', v)} />
                <NumInput label="Coal Thermic Boiler (MT)" value={form.coal_thermic}
                  onChange={v => set('coal_thermic', v)} />
              </div>
              <div style={s.row2}>
                <NumInput label="SEP Steam Opening (KG)" value={form.steam_sep_opening}
                  onChange={v => set('steam_sep_opening', v)} />
                <NumInput label="SEP Steam Closing (KG)" value={form.steam_sep_closing}
                  onChange={v => set('steam_sep_closing', v)} />
              </div>
              <div style={s.row2}>
                <NumInput label="REFL Steam Opening (KG)" value={form.steam_refl_opening}
                  onChange={v => set('steam_refl_opening', v)} />
                <NumInput label="REFL Steam Closing (KG)" value={form.steam_refl_closing}
                  onChange={v => set('steam_refl_closing', v)} />
              </div>
              <div style={s.row3}>
                <NumInput label="Feed Water Temp (°C)" value={form.feed_water_temp_daily}
                  onChange={v => set('feed_water_temp_daily', v)} />
                <NumInput label="Coal Bunker (%)" value={form.coal_bunker_pct}
                  onChange={v => set('coal_bunker_pct', v)} />
                <div style={s.field}>
                  <label style={s.label}>Steam Pressure OK?</label>
                  <select style={s.select}
                    value={form.steam_pressure_ok ? 'yes' : 'no'}
                    onChange={e => set('steam_pressure_ok', (e.target.value === 'yes') as any)}>
                    <option value="yes">Yes — Normal</option>
                    <option value="no">No — Problem</option>
                  </select>
                </div>
              </div>
            </>
          )}
        </div>
        {warnings.length > 0 && (
          <div style={{
            background: '#fff7ed', border: '1px solid #fed7aa',
            borderRadius: 8, padding: '10px 14px', marginBottom: 10
          }}>
            {warnings.map((w, i) => (
              <div key={i} style={{ color: '#c2410c', fontSize: 13 }}>{w}</div>
            ))}
          </div>
        )}

        {/* Errors / Success */}
        {error && <div style={s.errorBox}>❌ {error}</div>}
        {success && <div style={s.successBox}>✅ Entry submitted successfully! Pending HOD approval.</div>}

        <button type="submit" style={loading ? s.btnDisabled : s.btn} disabled={loading}>
          {loading ? 'Submitting...' : '📤 Submit Log Entry'}
        </button>
      </form>
    </div>
  );
}

// Reusable numeric input
function NumInput({ label, value, onChange, hint, warn }: {
  label: string; value: string;
  onChange: (v: string) => void;
  hint?: string; warn?: boolean;
}) {
  return (
    <div style={s.field}>
      <label style={s.label}>{label}{hint && <span style={s.hint}> · {hint}</span>}</label>
      <input
        style={{ ...s.input, ...(warn ? s.inputWarn : {}) }}
        type="number" step="any" value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="—"
      />
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
  row3: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10, marginBottom: 12 },
  row2: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10, marginBottom: 12 },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { fontSize: 11, fontWeight: 600, color: '#555', textTransform: 'uppercase', letterSpacing: '0.04em' },
  hint: { fontWeight: 400, color: '#999', textTransform: 'none', letterSpacing: 0 },
  input: { padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 15, outline: 'none', width: '100%', boxSizing: 'border-box' },
  inputWarn: { borderColor: '#ff9800', background: '#fff8f0' },
  select: { padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 14, outline: 'none', background: '#fff' },
  textarea: { padding: '10px 12px', border: '1.5px solid #e0e0e0', borderRadius: 8, fontSize: 14, resize: 'vertical', fontFamily: 'inherit' },
  btn: { width: '100%', padding: '15px', background: '#0f3460', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, fontWeight: 700, cursor: 'pointer', marginTop: 8 },
  btnDisabled: { width: '100%', padding: '15px', background: '#aaa', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, fontWeight: 700, cursor: 'not-allowed', marginTop: 8 },
  errorBox: { background: '#fff0f0', border: '1px solid #ffcccc', color: '#cc0000', padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 10 },
  successBox: { background: '#f0fff4', border: '1px solid #86efac', color: '#166534', padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 10 },
};