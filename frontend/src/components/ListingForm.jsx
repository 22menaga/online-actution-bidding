import { useEffect, useMemo, useRef, useState } from 'react';
import { Products } from '../api.js';
import { Badge, Field, Icon, money, useAsync, useToast } from '../ui.jsx';

const MAX_PHOTOS = 4;
const MAX_MB = 5;
const OK_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const CONF_TONE = { high: 'ok', medium: 'warn', low: 'bad' };

/** Visual price range: the bar shows 0 -> a bit above the high estimate; the gold span is the expected selling range. */
function RangeBar({ low, high, start, currency }) {
  const max = high * 1.2;
  const pct = (v) => `${Math.min(100, (v / max) * 100)}%`;
  return (
    <div style={{ margin: '18px 0 8px' }}>
      <div style={{ position: 'relative', height: 14, borderRadius: 8, background: 'rgba(255,255,255,.07)' }}>
        <div style={{ position: 'absolute', left: pct(low), width: `calc(${pct(high)} - ${pct(low)})`, top: 0, bottom: 0, borderRadius: 8, background: 'var(--gold)', boxShadow: '0 0 18px rgba(224,170,72,.5)' }} />
        {start != null && <div title={`Suggested starting price ${money(start, 0)}`} style={{ position: 'absolute', left: pct(start), top: -5, width: 3, height: 24, borderRadius: 2, background: 'var(--pink)' }} />}
      </div>
      <div className="row between small" style={{ marginTop: 8 }}>
        <span><b className="price" style={{ fontSize: 17 }}>{money(low, 0)}</b> <span className="faint">low</span></span>
        {start != null && <span style={{ color: 'var(--pink)' }}>▲ start at {money(start, 0)}</span>}
        <span><span className="faint">high</span> <b className="price" style={{ fontSize: 17 }}>{money(high, 0)}</b></span>
      </div>
      <div className="faint small center" style={{ marginTop: 2 }}>Expected resale / auction range ({currency})</div>
    </div>
  );
}

function AIResult({ r, onApply }) {
  if (!r.sellable) return <div className="banner"><Icon name="shield" /><div>{r.summary}</div></div>;
  return (
    <div className="card pad" style={{ background: 'rgba(0,0,0,.28)', animation: 'rise .4s both' }}>
      <div className="row between">
        <div><div className="eyebrow">AI market estimate</div><b style={{ fontSize: 18 }}>{r.item_name}</b>{r.maker_or_brand && <span className="faint small"> · {r.maker_or_brand}</span>}</div>
        <Badge status={CONF_TONE[r.confidence]}>{r.confidence} confidence</Badge>
      </div>
      <RangeBar low={r.estimated_low} high={r.estimated_high} start={r.suggested_start_price} currency={r.currency} />
      {r.value_drivers?.length > 0 && <ul className="small mute" style={{ margin: '12px 0 0', paddingLeft: 18 }}>{r.value_drivers.map((v) => <li key={v}>{v}</li>)}</ul>}
      {r.risks?.length > 0 && <div className="small" style={{ marginTop: 10, color: 'var(--gold1)' }}>⚠ {r.risks.join(' · ')}</div>}
      {r.questions_for_seller?.length > 0 && <div className="small faint" style={{ marginTop: 8 }}>To firm this up: {r.questions_for_seller.join(' · ')}</div>}
      <div className="row" style={{ marginTop: 14 }}>
        <button type="button" className="btn gold sm" onClick={onApply}><Icon name="check" size={16} /> Use these details</button>
        <span className="faint small">Fills name, category, condition, description and reference price. You can edit everything.</span>
      </div>
      <p className="faint small" style={{ margin: '12px 0 0' }}>AI estimate from photos only — not a professional appraisal. The final price is decided by bidders.</p>
    </div>
  );
}

export default function ListingForm({ onCreated }) {
  const toast = useToast();
  const cats = useAsync(Products.categories, []);
  const status = useAsync(Products.aiStatus, []);
  const blank = { name: '', description: '', starting_price: '', condition: 'Good', category: '' };
  const [f, setF] = useState(blank);
  const [files, setFiles] = useState([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [result, setResult] = useState(null);
  const [aiError, setAiError] = useState('');
  const input = useRef(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const previews = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);
  useEffect(() => () => previews.forEach(URL.revokeObjectURL), [previews]);

  const addFiles = (list) => {
    const next = [...files];
    for (const file of list) {
      if (!OK_TYPES.includes(file.type)) { toast(`${file.name}: only JPEG, PNG or WebP photos.`, 'err'); continue; }
      if (file.size > MAX_MB * 1024 * 1024) { toast(`${file.name}: photos must be ${MAX_MB}MB or smaller.`, 'err'); continue; }
      if (next.length >= MAX_PHOTOS) { toast(`You can add up to ${MAX_PHOTOS} photos.`, 'warn'); break; }
      next.push(file);
    }
    setFiles(next); setResult(null); setAiError('');
  };
  const removeAt = (i) => { setFiles(files.filter((_, k) => k !== i)); setResult(null); };

  const analyse = async () => {
    setAnalysing(true); setAiError(''); setResult(null);
    try { setResult(await Products.aiEstimate(files, f.description)); } catch (x) { setAiError(x.message); } finally { setAnalysing(false); }
  };

  const apply = () => {
    const cat = cats.data?.results.find((c) => c.name === result.category);
    setF({ ...f, name: result.item_name || f.name, description: result.description || f.description, condition: result.condition || f.condition, starting_price: String(result.estimated_mid ?? f.starting_price), category: cat ? String(cat.id) : f.category });
    toast('Details filled in from the AI estimate. Review and edit anything.', 'ok');
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!files.length) return toast('Add at least one photo of the item.', 'err');
    setBusy(true);
    try {
      const p = await Products.create({ ...f, category: Number(f.category), ...(result?.sellable ? { ai_estimate_id: result.id } : {}) });
      for (const file of files) await Products.image(p.id, file);
      await Products.submit(p.id);
      toast('Product submitted for approval', 'ok');
      setF(blank); setFiles([]); setResult(null);
      onCreated();
    } catch (x) { toast(x.message, 'err'); } finally { setBusy(false); }
  };

  const aiOn = status.data?.enabled;

  return (
    <form className="card glow pad" onSubmit={submit}>
      <h3>List a new item</h3>

      <label>Photos (JPEG / PNG / WebP, up to {MAX_PHOTOS}, {MAX_MB}MB each)</label>
      <div
        className={`drop ${drag ? 'over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }}
        onClick={() => input.current?.click()}
        role="button" tabIndex={0} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        aria-label="Add photos"
      >
        <input ref={input} type="file" hidden accept={OK_TYPES.join(',')} multiple onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
        {files.length === 0 ? (<><div style={{ fontSize: 34 }}>📷</div><b>Drop photos here or click to browse</b><div className="faint small">Clear, well-lit photos from a few angles give the best AI estimate</div></>) : (
          <div className="previews" onClick={(e) => e.stopPropagation()}>
            {previews.map((src, i) => (
              <div key={src} className={`thumbcard ${analysing ? 'scanning' : ''}`}>
                <img src={src} alt={`Photo ${i + 1}`} />
                <button type="button" aria-label={`Remove photo ${i + 1}`} onClick={() => removeAt(i)}>×</button>
              </div>
            ))}
            {files.length < MAX_PHOTOS && <button type="button" className="thumbcard add" onClick={() => input.current?.click()}>＋</button>}
          </div>
        )}
      </div>

      {files.length > 0 && (
        <div style={{ margin: '14px 0' }}>
          {aiOn === false && <div className="banner info small"><Icon name="shield" /> AI price estimates are not switched on yet. The site owner can enable them by adding <b>ANTHROPIC_API_KEY</b> to <b>backend/.env</b>. You can still list your item below.</div>}
          {aiOn && !result && (
            <button type="button" className="btn pink block" disabled={analysing} onClick={analyse}>
              {analysing ? 'Analysing your photos… (about 10–20 seconds)' : <><Icon name="bolt" size={18} /> Estimate market value with AI</>}
            </button>
          )}
          {aiError && <div className="err" role="alert">{aiError}{' '}<button type="button" className="chip" onClick={analyse}>Try again</button></div>}
          {result && <AIResult r={result} onApply={apply} />}
        </div>
      )}

      <Field label="Name"><input value={f.name} onChange={set('name')} required /></Field>
      <Field label="Category">
        <select value={f.category} onChange={set('category')} required>
          <option value="">Select…</option>
          {cats.data?.results.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Field>
      <Field label="Description"><textarea rows={4} value={f.description} onChange={set('description')} required /></Field>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}><Field label="Reference price"><input type="number" min="0.01" step="0.01" value={f.starting_price} onChange={set('starting_price')} required /></Field></div>
        <div style={{ flex: 1 }}><Field label="Condition"><input value={f.condition} onChange={set('condition')} required /></Field></div>
      </div>
      <p><button className="btn gold" disabled={busy || analysing}>{busy ? 'Submitting…' : 'Submit for approval'}</button></p>
    </form>
  );
}
