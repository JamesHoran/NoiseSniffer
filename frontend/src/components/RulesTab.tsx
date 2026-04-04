import { useState, useEffect } from 'react';

const API = 'http://localhost:8000';

const NOTES = [
  'C3','D3','E3','F3','G3','A3','B3',
  'C4','D4','E4','F4','G4','A4','B4',
  'C5','D5','E5','F5','G5','A5','B5',
] as const;
type SoundType = typeof NOTES[number];

interface Rule {
  port: number;
  ip_whitelist: string[];
  sound_type: SoundType;
  frequency_hz: number | null;
  frequency_boost: number;
}

const EMPTY_FORM = {
  port: '',
  ip_whitelist: '',
  sound_type: 'A4' as SoundType,
  frequency_hz: '',
  frequency_boost: '1.0',
};

const inputCls =
  'w-full rounded bg-gray-800 border border-gray-600 text-white px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500';
const labelCls = 'block text-xs text-gray-400 mb-1';

export function RulesTab() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${API}/rules`)
      .then(r => r.json())
      .then(setRules)
      .catch(() => setError('Could not load rules from server.'));
  }, []);

  const set = (field: keyof typeof EMPTY_FORM) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm(prev => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const port = parseInt(form.port);
    if (!port || port < 1 || port > 65535) {
      setError('Port must be between 1 and 65535.');
      return;
    }

    const rule: Rule = {
      port,
      ip_whitelist: form.ip_whitelist
        ? form.ip_whitelist.split(',').map(s => s.trim()).filter(Boolean)
        : [],
      sound_type: form.sound_type,
      frequency_hz: null, // frequency_hz: form.frequency_hz ? parseFloat(form.frequency_hz) : null,
      frequency_boost: parseFloat(form.frequency_boost) || 1.0,
    };

    const res = await fetch(`${API}/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rule),
    });

    if (res.ok) {
      const saved: Rule = await res.json();
      setRules(prev => {
        const idx = prev.findIndex(r => r.port === saved.port);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = saved;
          return next;
        }
        return [...prev, saved];
      });
      setForm(EMPTY_FORM);
    } else {
      setError('Failed to save rule.');
    }
  };

  const handleDelete = async (port: number) => {
    const res = await fetch(`${API}/rules/${port}`, { method: 'DELETE' });
    if (res.ok) {
      setRules(prev => prev.filter(r => r.port !== port));
    } else {
      setError('Failed to delete rule.');
    }
  };

  return (
    <div className="p-4 text-white max-w-2xl">

      {/* Add rule form */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 mb-6">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">New Rule</h2>
        <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-3">

          <div>
            <label className={labelCls}>Port</label>
            <input
              type="number" min={1} max={65535} required
              placeholder="e.g. 443"
              value={form.port}
              onChange={set('port')}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Note</label>
            <select value={form.sound_type} onChange={set('sound_type')} className={inputCls}>
              {NOTES.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {/* Frequency field commented out
          <div>
            <label className={labelCls}>Frequency <span className="text-gray-500">(Hz, empty = auto)</span></label>
            <input
              type="number" min={20} max={20000} step={1}
              placeholder="e.g. 1000"
              value={form.frequency_hz}
              onChange={set('frequency_hz')}
              className={inputCls}
            />
          </div>
          */}

          <div>
            <label className={labelCls}>Frequency Boost <span className="text-gray-500">(1.0 = neutral)</span></label>
            <input
              type="number" min={0} max={10} step={0.1}
              value={form.frequency_boost}
              onChange={set('frequency_boost')}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>IP Whitelist <span className="text-gray-500">(comma-separated, empty = all)</span></label>
            <input
              type="text"
              placeholder="e.g. 192.168.1.1, 10.0.0.5"
              value={form.ip_whitelist}
              onChange={set('ip_whitelist')}
              className={inputCls}
            />
          </div>

          {error && (
            <p className="col-span-2 text-red-400 text-xs">{error}</p>
          )}

          <div className="col-span-2 flex justify-end">
            <button
              type="submit"
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors"
            >
              Add / Update Rule
            </button>
          </div>
        </form>
      </div>

      {/* Rules list */}
      <h2 className="text-sm font-semibold text-gray-300 mb-2">Active Rules</h2>
      {rules.length === 0 ? (
        <p className="text-gray-500 text-sm">No rules configured.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {rules.map(rule => (
            <div
              key={rule.port}
              className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 flex items-center justify-between gap-4"
            >
              <div className="grid grid-cols-4 gap-4 flex-1 text-sm">
                <div>
                  <span className="text-gray-500 text-xs block">Port</span>
                  <span className="font-mono text-white">{rule.port}</span>
                </div>
                <div>
                  <span className="text-gray-500 text-xs block">Note</span>
                  <span className="text-white">{rule.sound_type}</span>
                </div>
                {/* <div>
                  <span className="text-gray-500 text-xs block">Frequency</span>
                  <span className="text-white">{rule.frequency_hz ? `${rule.frequency_hz} Hz` : 'auto'}</span>
                </div> */}
                <div>
                  <span className="text-gray-500 text-xs block">Boost</span>
                  <span className="text-white">{rule.frequency_boost.toFixed(1)}×</span>
                </div>
                <div>
                  <span className="text-gray-500 text-xs block">IP Whitelist</span>
                  <span className="text-white">
                    {rule.ip_whitelist.length > 0 ? rule.ip_whitelist.join(', ') : 'all'}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleDelete(rule.port)}
                className="text-xs text-red-400 hover:text-red-300 border border-red-800 hover:border-red-600 px-3 py-1 rounded transition-colors shrink-0"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
