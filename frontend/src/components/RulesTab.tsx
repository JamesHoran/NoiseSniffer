import { useState, useEffect } from "react";

const API = "http://localhost:8000";

// All notes C3–B5 in chromatic order, including sharps
const NOTES = [
  'C3','C#3','D3','D#3','E3','F3','F#3','G3','G#3','A3','A#3','B3',
  'C4','C#4','D4','D#4','E4','F4','F#4','G4','G#4','A4','A#4','B4',
  'C5','C#5','D5','D#5','E5','F5','F#5','G5','G#5','A5','A#5','B5',
] as const;
type SoundType = (typeof NOTES)[number];

const SOUNDS = ['synth', 'piano'] as const;
type Sound = typeof SOUNDS[number];

interface Rule {
  port: number;
  ip_whitelist: string[];
  sound: Sound;
  sound_type: SoundType;
  frequency_boost: number;
}

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------
// "443 → .138" and "443 → .60" are intentionally separate presets because
// rules are keyed by port — two rules for port 443 can't coexist.

const PRESETS: Record<string, Rule[]> = {
  'Current Rules': [
    { port: 443,  ip_whitelist: [],                 sound: 'piano', sound_type: 'C4',  frequency_boost: 5.0 },
    { port: 80,   ip_whitelist: [],                 sound: 'synth', sound_type: 'E4',  frequency_boost: 8.0 },
    { port: 53,   ip_whitelist: [],                 sound: 'piano', sound_type: 'B4',  frequency_boost: 8.0 },
    { port: 3702, ip_whitelist: [],                 sound: 'synth', sound_type: 'G5',  frequency_boost: 6.0 },
    { port: 7844, ip_whitelist: [],                 sound: 'synth', sound_type: 'G4',  frequency_boost: 5.0 },
    { port: 22,   ip_whitelist: [],                 sound: 'piano', sound_type: 'F#5', frequency_boost: 8.0 },
  ],
  'Local Only (.138)': [
    { port: 443,  ip_whitelist: ['172.17.78.138'],  sound: 'piano', sound_type: 'C4',  frequency_boost: 5.0 },
    { port: 80,   ip_whitelist: ['172.17.78.138'],  sound: 'synth', sound_type: 'E4',  frequency_boost: 8.0 },
    { port: 53,   ip_whitelist: ['172.17.78.138'],  sound: 'piano', sound_type: 'B4',  frequency_boost: 8.0 },
    { port: 3702, ip_whitelist: ['172.17.78.138'],  sound: 'synth', sound_type: 'G5',  frequency_boost: 6.0 },
    { port: 7844, ip_whitelist: ['172.17.78.138'],  sound: 'synth', sound_type: 'G4',  frequency_boost: 5.0 },
    { port: 22,   ip_whitelist: ['172.17.78.138'],  sound: 'piano', sound_type: 'F#5', frequency_boost: 8.0 },
  ],
  '443 → .138': [
    { port: 443,  ip_whitelist: ['172.17.78.138'],  sound: 'piano', sound_type: 'C4',  frequency_boost: 5.0 },
  ],
  '443 → .60': [
    { port: 443,  ip_whitelist: ['172.17.28.60'],   sound: 'piano', sound_type: 'E4',  frequency_boost: 5.0 },
  ],
};

const PRESET_NAMES = Object.keys(PRESETS) as (keyof typeof PRESETS)[];

// ---------------------------------------------------------------------------

const EMPTY_FORM = {
  port: '',
  ip_whitelist: '',
  sound: 'synth' as Sound,
  sound_type: 'A4' as SoundType,
  frequency_boost: '1.0',
};

const inputCls =
  "w-full rounded-lg bg-zinc-900/50 border border-zinc-700 text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all placeholder:text-zinc-500";
const labelCls = "block text-xs font-medium text-zinc-400 mb-1.5";

export function RulesTab() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [selectedPreset, setSelectedPreset] = useState(PRESET_NAMES[0]);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${API}/rules`)
      .then(r => r.json())
      .then(setRules)
      .catch(() => setError("Could not load rules from server."));
  }, []);

  const set = (field: keyof typeof EMPTY_FORM) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const port = parseInt(form.port);
    if (!port || port < 1 || port > 65535) {
      setError("Port must be between 1 and 65535.");
      return;
    }

    const rule: Rule = {
      port,
      ip_whitelist: form.ip_whitelist
        ? form.ip_whitelist
            .split(",")
            .map(s => s.trim())
            .filter(Boolean)
        : [],
      sound: form.sound,
      sound_type: form.sound_type,
      frequency_boost: parseFloat(form.frequency_boost) || 1.0,
    };

    const res = await fetch(`${API}/rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
      setError("Failed to save rule.");
    }
  };

  const handleDelete = async (port: number) => {
    const res = await fetch(`${API}/rules/${port}`, { method: "DELETE" });
    if (res.ok) {
      setRules(prev => prev.filter(r => r.port !== port));
    } else {
      setError("Failed to delete rule.");
    }
  };

  const handleApplyPreset = async () => {
    setError('');
    const preset = PRESETS[selectedPreset];

    // Delete all current rules first
    await Promise.all(rules.map(r =>
      fetch(`${API}/rules/${r.port}`, { method: 'DELETE' })
    ));

    // POST each preset rule
    const results = await Promise.all(preset.map(rule =>
      fetch(`${API}/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rule),
      }).then(r => r.ok ? r.json() : null)
    ));

    const saved = results.filter(Boolean) as Rule[];
    if (saved.length !== preset.length) {
      setError('Some preset rules failed to apply.');
    }
    setRules(saved);
  };

  return (
    <div className="p-4 text-white max-w-2xl">

      {/* Presets */}
      <div className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-700/50 rounded-xl p-5 mb-4 shadow-lg">
        <h2 className="text-sm font-semibold text-zinc-200 mb-3 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-purple-500"></span>
          Presets
        </h2>
        <div className="flex gap-2">
          <select
            value={selectedPreset}
            onChange={e => setSelectedPreset(e.target.value)}
            className={inputCls}
          >
            {PRESET_NAMES.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          <button
            onClick={handleApplyPreset}
            className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-sm font-medium rounded-lg transition-all duration-200 shadow-lg shadow-purple-900/20 shrink-0"
          >
            Apply Preset
          </button>
        </div>
      </div>

      {/* Add rule form */}
      <div className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-700/50 rounded-xl p-5 mb-6 shadow-lg">
        <h2 className="text-sm font-semibold text-zinc-200 mb-4 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-green-500"></span>
          New Rule
        </h2>
        <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Port</label>
            <input
              type="number"
              min={1}
              max={65535}
              required
              placeholder="e.g. 443"
              value={form.port}
              onChange={set("port")}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Sound</label>
            <select value={form.sound} onChange={set('sound')} className={inputCls}>
              {SOUNDS.map(s => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className={labelCls}>Note</label>
            <select value={form.sound_type} onChange={set("sound_type")} className={inputCls}>
              {NOTES.map(t => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className={labelCls}>
              Frequency Boost <span className="text-gray-500">(1.0 = neutral)</span>
            </label>
            <input
              type="number"
              min={0}
              max={10}
              step={0.1}
              value={form.frequency_boost}
              onChange={set("frequency_boost")}
              className={inputCls}
            />
          </div>

          <div className="col-span-2">
            <label className={labelCls}>IP Whitelist <span className="text-gray-500">(comma-separated, empty = all)</span></label>
            <input
              type="text"
              placeholder="e.g. 192.168.1.1, 10.0.0.5"
              value={form.ip_whitelist}
              onChange={set("ip_whitelist")}
              className={inputCls}
            />
          </div>

          {error && <p className="col-span-2 text-red-400 text-xs bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">{error}</p>}

          <div className="col-span-2 flex justify-end">
            <button type="submit" className="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-sm font-medium rounded-lg transition-all duration-200 shadow-lg shadow-purple-900/20">
              Add / Update Rule
            </button>
          </div>
        </form>
      </div>

      {/* Rules list */}
      <h2 className="text-sm font-semibold text-zinc-200 mb-3 flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-blue-500"></span>
        Active Rules
      </h2>
      {rules.length === 0 ? (
        <p className="text-gray-500 text-sm">No rules configured.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {rules.map(rule => (
            <div
              key={rule.port}
              className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-700/50 rounded-xl px-5 py-3 flex items-center justify-between gap-4 shadow-md hover:border-zinc-600/50 transition-colors"
            >
              <div className="grid grid-cols-5 gap-4 flex-1 text-sm">
                <div>
                  <span className="text-zinc-500 text-xs block">Port</span>
                  <span className="font-mono text-white font-medium">{rule.port}</span>
                </div>
                <div>
                  <span className="text-zinc-500 text-xs block">Sound</span>
                  <span className="text-white capitalize">{rule.sound ?? 'synth'}</span>
                </div>
                <div>
                  <span className="text-zinc-500 text-xs block">Note</span>
                  <span className="text-white">{rule.sound_type}</span>
                </div>
                <div>
                  <span className="text-zinc-500 text-xs block">Boost</span>
                  <span className="text-white">{rule.frequency_boost.toFixed(1)}×</span>
                </div>
                <div>
                  <span className="text-zinc-500 text-xs block">IP Whitelist</span>
                  <span className="text-white">{rule.ip_whitelist.length > 0 ? rule.ip_whitelist.join(", ") : "all"}</span>
                </div>
              </div>
              <button
                onClick={() => handleDelete(rule.port)}
                className="text-xs text-red-400 hover:text-red-300 border border-red-900/50 hover:border-red-700 hover:bg-red-950/30 px-3 py-1.5 rounded-lg transition-all shrink-0"
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
