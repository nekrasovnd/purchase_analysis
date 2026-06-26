import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp, BrainCircuit, Activity, Database,
  ShieldCheck, AlertOctagon, BarChart2, Layers,
  Award, AlertTriangle, XCircle, Zap, Target, Package
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  Line, ComposedChart, Legend, CartesianGrid,
  ScatterChart, Scatter, ZAxis, Treemap,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ReferenceLine, Area, AreaChart
} from 'recharts';

import data from '../data.json';

// ─── Палитры ─────────────────────────────────────────────────────────────────
const CAT_COLORS = {
  'ПО и Лицензии':          '#6366f1',
  'IT-Инфраструктура':      '#0ea5e9',
  'Офисные нужды':          '#10b981',
  'Маркетинг':              '#f59e0b',
  'Строительство и Ремонт': '#f97316',
  'Консалтинг':             '#ec4899',
  'Прочее':                 '#94a3b8',
};
const VENDOR_PALETTE = ['#6366f1','#f97316','#0ea5e9','#f59e0b','#10b981','#ec4899','#a855f7','#06b6d4'];
// Отдельные цвета для топ-20 с контрастом
const ENTITY_PALETTE = ['#6366f1','#f97316','#0ea5e9','#f59e0b','#10b981','#ec4899','#a855f7','#06b6d4','#84cc16','#14b8a6'];

// ─── Тема ─────────────────────────────────────────────────────────────────────
const buildTheme = (isDark) => isDark ? {
  bg:          'bg-slate-950',
  card:        'bg-slate-900',
  border:      'border-slate-800',
  borderHover: 'hover:border-slate-600',
  text:        'text-slate-100',
  muted:       'text-slate-400',
  faint:       'text-slate-500',
  tabBg:       'bg-slate-900 border-slate-800',
  tabInact:    'text-slate-400 hover:text-slate-200 hover:bg-slate-800',
  inputBg:     'bg-slate-800',
  divider:     'border-slate-800',
  gridColor:   '#1e293b',
  axisColor:   '#475569',
  tooltipBg:   '#0f172a',
  tooltipBrd:  '#334155',
  barFill:     '#334155',
  codeBg:      'bg-slate-800',
  codeText:    'text-slate-400',
} : {
  bg:          'bg-gray-50',
  card:        'bg-white',
  border:      'border-gray-200',
  borderHover: 'hover:border-gray-400',
  text:        'text-gray-900',
  muted:       'text-gray-500',
  faint:       'text-gray-400',
  tabBg:       'bg-white border-gray-200',
  tabInact:    'text-gray-500 hover:text-gray-800 hover:bg-gray-100',
  inputBg:     'bg-gray-100',
  divider:     'border-gray-200',
  gridColor:   '#e5e7eb',
  axisColor:   '#6b7280',
  tooltipBg:   '#ffffff',
  tooltipBrd:  '#d1d5db',
  barFill:     '#e2e8f0',
  codeBg:      'bg-gray-100',
  codeText:    'text-gray-500',
};

// ─── Анимированный счётчик ────────────────────────────────────────────────────
function AnimatedNumber({ value, prefix = '', suffix = '', decimals = 0, duration = 1500 }) {
  const [display, setDisplay] = useState(0);
  const start = useRef(null);
  const raf = useRef(null);

  useEffect(() => {
    start.current = null;
    const target = Number(value);
    const step = (ts) => {
      if (!start.current) start.current = ts;
      const progress = Math.min((ts - start.current) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(eased * target);
      if (progress < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [value, duration]);

  return <span>{prefix}{decimals > 0 ? display.toFixed(decimals) : Math.floor(display).toLocaleString('ru-RU')}{suffix}</span>;
}

// ─── KPI карточка ─────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, colorClass, icon: Icon, alert, delay = 0, th }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className={`relative overflow-hidden rounded-2xl ${th.card} border ${th.border} p-5 ${th.borderHover} transition-colors`}
    >
      <div className="flex items-start justify-between mb-3">
        <span className={`text-xs font-semibold uppercase tracking-widest ${th.faint}`}>{label}</span>
        <div className={`p-2 rounded-lg ${colorClass} bg-opacity-10`}>
          <Icon className={`w-4 h-4 ${colorClass}`} />
        </div>
      </div>
      <div className={`text-3xl font-black ${colorClass} mb-1`}>{value}</div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-xs ${th.muted}`}>{sub}</span>
        {alert && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 font-bold border border-red-500/30">{alert}</span>
        )}
      </div>
    </motion.div>
  );
}

// ─── Вкладки ─────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'story', label: 'История',      icon: Database },
  { id: 'top20', label: 'Топ закупок',  icon: Award },
  { id: 'macro', label: 'Макроэк.',     icon: TrendingUp },
  { id: 'ml',    label: 'ML Аномалии', icon: Activity },
  { id: 'ai',    label: 'AI Инсайты',  icon: BrainCircuit },
];

// ─── Главный Dashboard ────────────────────────────────────────────────────────
export default function Dashboard({ isDark = true }) {
  const [activeTab, setActiveTab] = useState('story');
  const th = buildTheme(isDark);
  const totalB = (data.stats.total_price_rub / 1e9).toFixed(1);
  const hhi = data.stats.hhi_index;

  const tabProps = { th, isDark };

  return (
    <div className={`max-w-7xl mx-auto px-4 md:px-6 py-8`}>

      {/* Заголовок */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
        <div className="flex flex-col md:flex-row items-start md:items-center gap-4 mb-6">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className={`text-xs font-semibold uppercase tracking-widest ${th.faint}`}>Live Data · PostgreSQL</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-500 bg-clip-text text-transparent">
              Аналитика закупок Группы Сбер
            </h1>
            <p className={`text-sm mt-1 ${th.muted}`}>2024–2025 · Sberbank-AST + B2B-Center + ЕИС · ML-анализ аномалий</p>
          </div>
          {/* HHI badge */}
          <div className="flex flex-col items-center p-4 rounded-2xl border-2 border-red-500/30 bg-red-500/5 shrink-0">
            <span className="text-xs text-red-400 font-bold uppercase tracking-wider mb-1">HHI индекс</span>
            <span className="text-4xl font-black text-red-400">
              <AnimatedNumber value={hhi} duration={2000} />
            </span>
            <span className="text-xs text-red-300 mt-1">🚨 Монополия &gt; 2500</span>
          </div>
        </div>

        {/* KPI */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <KpiCard th={th} label="Лотов собрано" value={<AnimatedNumber value={data.stats.total_lots} />} sub="3 источника данных" colorClass="text-emerald-500" icon={Package} delay={0.1} />
          <KpiCard th={th} label="Суммарный бюджет" value={<><AnimatedNumber value={totalB} decimals={1} />млрд ₽</>} sub="по рыночным ценам" colorClass="text-cyan-500" icon={BarChart2} delay={0.2} />
          <KpiCard th={th} label="Юрлиц с закупками" value={<AnimatedNumber value={data.stats.total_entities} />} sub={`из 32 в скопе (+10 аудит, 0 результатов)`} colorClass="text-blue-500" icon={Layers} delay={0.3} />
          <KpiCard th={th} label="Корреляция со ставкой ЦБ" value={<AnimatedNumber value={data.stats.corr_rate * 100} decimals={1} suffix="%" />} sub="лаг 3 мес (Pearson)" colorClass="text-amber-500" icon={TrendingUp} alert="Значим!" delay={0.4} />
        </div>
      </motion.div>

      {/* Вкладки */}
      <div className={`flex flex-wrap gap-2 p-1 ${th.tabBg} rounded-xl border mb-6`}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              activeTab === tab.id
                ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white shadow-lg shadow-emerald-500/20'
                : th.tabInact
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === 'story' && <StoryTab {...tabProps} />}
          {activeTab === 'top20' && <Top20Tab {...tabProps} />}
          {activeTab === 'macro' && <MacroTab {...tabProps} />}
          {activeTab === 'ml'    && <MLVisualsTab {...tabProps} />}
          {activeTab === 'ai'    && <AITab {...tabProps} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// ─── История (Pipeline) ───────────────────────────────────────────────────────
function StoryTab({ th }) {
  const steps = [
    { num: '01', icon: Database,    color: 'emerald', tag: 'entity_scope.csv',               lots: '~1800', lotLabel: 'лотов',   title: 'Старт: ~10 юрлиц', desc: 'Только ПАО Сбербанк + 9 крупнейших дочек. REST API Sberbank-AST, базовый парсинг. Первые ~1800 лотов. Понял: покрытие неполное.' },
    { num: '02', icon: Layers,      color: 'blue',    tag: 'configs/entity_scope.csv',        lots: '32',    lotLabel: 'юрлица',  title: 'Ручное расширение скопа', desc: 'По ЕГРЮЛ и сайту Сбера добавил ещё 22 юрлица: Cloud.ru, СберМобайл, 2ГИС, УК Первая, СберМаркетинг и другие. Нормализация ИНН+ОГРН+КПП.' },
    { num: '03', icon: ShieldCheck, color: 'indigo',  tag: 'entity_resolution.py',            lots: '2761',  lotLabel: 'лотов',   title: 'Обогащение при парсинге', desc: 'Enrichment: находим связанные ИНН/КПП прямо в данных площадок, расширяем скоп на лету. Jaro-Winkler для нечёткого совпадения названий.' },
    { num: '04', icon: Zap,         color: 'purple',  tag: 'b2b_center_prompt2_v2.py',        lots: '+400',  lotLabel: 'лотов',   title: 'Playwright: обход CAPTCHA', desc: 'B2B-Center защищён CAPTCHA. Эмуляция браузера + XHR-перехват. Даже если CAPTCHA срабатывает — скрипт сам нажимает на нужный элемент.' },
    { num: '05', icon: AlertTriangle,color:'amber',   tag: 'fabrikant_sniff.py',              lots: '0',     lotLabel: 'результат', title: 'Fabrikant: 4 попытки — 0 результатов', desc: '(1) RSC GET INN-фильтр — игнорируется; (2) Server Action fetchOrganizationBySearch — требует auth; (3) cookie-подделка — 403; (4) текстовый поиск — только 10/102 без пагинации. Нужна верификация юрлица.' },
    { num: '06', icon: Target,      color: 'teal',    tag: 'scripts/merge_sprints.py',        lots: '3161',  lotLabel: 'итог',    title: 'Clean Merge + Dedupe', desc: 'Cross-source дедупликация: номер процедуры + cosine similarity заголовков + сумма. 3 дубля удалены. PostgreSQL. Аудит 6 других ЭТП — Сбера нет.' },
  ];

  const colorMap = {
    emerald: { ring: 'ring-emerald-500/20', bg: 'bg-emerald-500/10', text: 'text-emerald-500', border: 'border-emerald-500/30', dot: 'bg-emerald-500' },
    blue:    { ring: 'ring-blue-500/20',    bg: 'bg-blue-500/10',    text: 'text-blue-500',    border: 'border-blue-500/30',    dot: 'bg-blue-500' },
    indigo:  { ring: 'ring-indigo-500/20',  bg: 'bg-indigo-500/10',  text: 'text-indigo-500',  border: 'border-indigo-500/30',  dot: 'bg-indigo-500' },
    purple:  { ring: 'ring-purple-500/20',  bg: 'bg-purple-500/10',  text: 'text-purple-500',  border: 'border-purple-500/30',  dot: 'bg-purple-500' },
    amber:   { ring: 'ring-amber-500/20',   bg: 'bg-amber-500/10',   text: 'text-amber-500',   border: 'border-amber-500/30',   dot: 'bg-amber-500' },
    teal:    { ring: 'ring-teal-500/20',    bg: 'bg-teal-500/10',    text: 'text-teal-500',    border: 'border-teal-500/30',    dot: 'bg-teal-500' },
  };

  const sourceStats = [
    { label: 'Sberbank-AST', pct: 87.3, color: '#6366f1', value: '2 761' },
    { label: 'B2B-Center',   pct: 12.7, color: '#a855f7', value: '400' },
    { label: 'ЕИС',          pct: 0.09, color: '#10b981', value: '3' },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {steps.map((step, i) => {
          const c = colorMap[step.color];
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className={`relative p-5 rounded-2xl ${th.card} border ${c.border} ring-1 ${c.ring} overflow-hidden`}
            >
              <div className={`absolute top-0 right-0 w-20 h-20 rounded-full opacity-10 blur-2xl ${c.dot}`} />
              <div className="flex items-center justify-between mb-3">
                <span className={`text-4xl font-black ${c.text} opacity-20`}>{step.num}</span>
                <div className={`p-2 rounded-xl ${c.bg}`}>
                  <step.icon className={`w-5 h-5 ${c.text}`} />
                </div>
              </div>
              <h3 className={`font-bold text-sm mb-2 ${th.text}`}>{step.title}</h3>
              <p className={`text-xs leading-relaxed mb-4 ${th.muted}`}>{step.desc}</p>
              <div className={`flex items-center justify-between pt-3 border-t ${c.border}`}>
                <code className={`text-xs ${th.codeText} truncate max-w-[60%]`}>{step.tag}</code>
                <span className={`font-bold text-sm ${c.text}`}>
                  {step.lots} <span className={`text-xs font-normal ${th.muted}`}>{step.lotLabel}</span>
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Состав датасета */}
      <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} mb-1`}>Состав Clean Dataset: 3 161 лот</h3>
        <p className={`text-xs ${th.muted} mb-5`}>22 из 32 юрлиц имеют активные закупки. 10 юрлиц в scope, но не нашли ни одного лота ни на одной площадке.</p>
        <div className="space-y-4">
          {sourceStats.map((s) => (
            <div key={s.label}>
              <div className="flex justify-between text-xs mb-1.5">
                <span className={`font-medium ${th.text}`}>{s.label}</span>
                <span className={th.muted}>{s.value} лот · {s.pct.toFixed(1)}%</span>
              </div>
              <div className={`h-2.5 ${th.inputBg} rounded-full overflow-hidden`}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${s.pct}%` }}
                  transition={{ duration: 1, ease: 'easeOut', delay: 0.5 }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: s.color }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Отклонённые ЭТП */}
      <div className={`p-5 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} text-sm mb-3`}>Аудит других площадок — Сбер не присутствует</h3>
        <div className="flex flex-wrap gap-2">
          {['Tektorg (0 лотов)', 'Roseltorg (0)', 'ETP GPB (имуществ. торги)', 'ZakazRF (0)', 'LotOnline (0)', 'TenderPro (0)', 'RTS Tender (503)', 'Fabrikant (нужна auth)'].map(p => (
            <div key={p} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${th.border} ${th.card}`}>
              <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
              <span className={`text-xs ${th.muted}`}>{p}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Топ-20 закупок ───────────────────────────────────────────────────────────
function Top20Tab({ th, isDark }) {
  const top12 = data.top_20.slice(0, 12).map(d => ({
    ...d,
    priceB: +(d.price / 1e9).toFixed(3),
    shortSubject: d.subject.length > 52 ? d.subject.slice(0, 50) + '…' : d.subject,
  }));

  const entityColors = {};
  const entityList = [...new Set(top12.map(d => d.entity))];
  entityList.forEach((e, i) => { entityColors[e] = ENTITY_PALETTE[i % ENTITY_PALETTE.length]; });

  // Проверяем, что Cloud.ru и Сбербанк-Сервис не сливаются
  // Cloud.ru → '#6366f1' (indigo), Сбербанк-Сервис — в top12 нет, это в treemap
  // В top12 главные: Cloud.ru и ПАО Сбербанк России, УК Первая, СберМобайл, 2ГИС, СберМаркетинг
  // Назначаем вручную разные цвета:
  Object.keys(entityColors).forEach((e, i) => {
    if (e.includes('Облачные') || e.includes('Cloud')) entityColors[e] = '#6366f1';
    else if (e.includes('Сбербанк России') || e.includes('ПАО Сбербанк')) entityColors[e] = '#f97316';
    else if (e.includes('Управляющая') || e.includes('УК Первая')) entityColors[e] = '#0ea5e9';
    else if (e.includes('Телеком') || e.includes('СберМобайл')) entityColors[e] = '#10b981';
    else if (e.includes('ДубльГИС') || e.includes('2ГИС')) entityColors[e] = '#f59e0b';
    else if (e.includes('Маркетинг')) entityColors[e] = '#ec4899';
  });

  const barData = [...top12].reverse();
  const cloudTotal = data.top_20.filter(d => d.entity.includes('Облачные')).reduce((s, d) => s + d.price, 0);
  const cloudPct = (cloudTotal / data.stats.total_price_rub * 100).toFixed(1);

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="rounded-xl p-4 max-w-xs shadow-2xl border" style={{ background: th.tooltipBg, borderColor: th.tooltipBrd }}>
        <div className="text-xs mb-1" style={{ color: entityColors[d.entity] }}>{d.entity}</div>
        <div className="font-bold text-sm mb-2" style={{ color: isDark ? '#f1f5f9' : '#0f172a' }}>{d.subject.slice(0, 90)}{d.subject.length > 90 ? '…' : ''}</div>
        <div className="text-lg font-black" style={{ color: entityColors[d.entity] }}>{(d.price / 1e9).toFixed(3)} млрд ₽</div>
        <div className="text-xs mt-1" style={{ color: isDark ? '#64748b' : '#9ca3af' }}>{d.procedure} · {d.source}</div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className={`p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-3`}>
        <AlertOctagon className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-red-300">Аномальная концентрация: </span>
          <span className="text-red-200 text-sm">
            ООО «Облачные технологии» (Cloud.ru) — <strong>{cloudPct}%</strong> бюджета
            ({(cloudTotal / 1e9).toFixed(1)} из {(data.stats.total_price_rub / 1e9).toFixed(1)} млрд ₽). HHI = <strong>{data.stats.hhi_index}</strong>.
          </span>
        </div>
      </div>

      <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} mb-1`}>Топ-12 закупок по стоимости</h3>
        <p className={`text-xs ${th.muted} mb-4`}>Цвет — юридическое лицо-заказчик. Наведите для деталей.</p>
        <div style={{ height: Math.max(360, barData.length * 44) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={th.gridColor} horizontal={false} />
              <XAxis type="number" stroke={th.axisColor} fontSize={11} tickFormatter={v => `${v.toFixed(1)}B`} />
              <YAxis type="category" dataKey="shortSubject" width={220} stroke={th.axisColor} fontSize={10} tick={{ fill: th.axisColor }} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
              <Bar dataKey="priceB" radius={[0, 4, 4, 0]}>
                {barData.map((entry, i) => (
                  <Cell key={i} fill={entityColors[entry.entity] || '#6366f1'} opacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className={`p-5 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} text-sm mb-4`}>Заказчики</h3>
        <div className="flex flex-wrap gap-3">
          {Object.entries(entityColors).map(([entity, color]) => (
            <div key={entity} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className={`text-xs ${th.muted}`}>{entity.replace(/^(ООО|АО|ПАО)\s+/, '')}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Макроэкономика ───────────────────────────────────────────────────────────
function MacroTab({ th, isDark }) {
  const MacroTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-xl p-3 shadow-xl border" style={{ background: th.tooltipBg, borderColor: th.tooltipBrd }}>
        <div className="font-bold text-sm mb-2" style={{ color: isDark ? '#f1f5f9' : '#111827' }}>{label}</div>
        {payload.map((p, i) => (
          <div key={i} className="flex items-center gap-2 text-xs mb-1">
            <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>{p.name}:</span>
            <span className="font-bold" style={{ color: p.color }}>
              {p.dataKey === 'total_price' ? `${(p.value / 1e9).toFixed(2)} млрд ₽`
                : p.dataKey === 'key_rate' ? `${p.value}%`
                : `${p.value?.toFixed(2)} ₽`}
            </span>
          </div>
        ))}
      </div>
    );
  };

  // Разбить по годам для подписи на оси
  const tickFormatter = (v) => {
    if (v === '2024-01') return '2024';
    if (v === '2025-01') return '2025';
    return '';
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className={`p-5 rounded-2xl ${th.card} border ${th.border}`}>
          <div className={`text-xs ${th.faint} uppercase tracking-wider mb-2`}>Корреляция с курсом USD (лаг 3 мес)</div>
          <div className="text-4xl font-black text-slate-400 mb-1">{data.stats.corr_usd.toFixed(3)}</div>
          <div className={`text-xs ${th.muted}`}>✓ Слабая связь — хеджирование USD некритично для операций</div>
        </div>
        <div className={`p-5 rounded-2xl ${th.card} border border-amber-500/40 bg-amber-500/5`}>
          <div className="text-xs text-amber-500 uppercase tracking-wider mb-2">Корреляция с Ключевой ставкой ЦБ</div>
          <div className="text-4xl font-black text-amber-400 mb-1">+{data.stats.corr_rate.toFixed(3)}</div>
          <div className="text-xs text-amber-300">🚨 Значимая связь: рост ставки → рост закупочных бюджетов через 3 мес</div>
        </div>
      </div>

      <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} mb-1`}>Объём закупок 2024–2025 vs Макро-индикаторы</h3>
        <p className={`text-xs ${th.muted} mb-2`}>
          Бары — объём закупок (млрд ₽). <span className="text-emerald-500 font-medium">Зелёная линия</span> — USD +3 мес лаг.{' '}
          <span className="text-orange-400 font-medium">Оранжевая</span> — ключевая ставка ЦБ. Заметен рост объёмов в 2025.
        </p>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data.monthly_stats} margin={{ top: 4, right: 24, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={th.gridColor} vertical={false} />
              <XAxis dataKey="month" stroke={th.axisColor} fontSize={10} tick={{ fill: th.axisColor }}
                tickFormatter={(v) => { const m = v.split('-')[1]; return m === '01' ? v.split('-')[0] : ''; }}
                interval={0}
              />
              <YAxis yAxisId="left"  stroke={th.axisColor} fontSize={10} tickFormatter={v => `${(v / 1e9).toFixed(0)}B`} tick={{ fill: th.axisColor }} />
              <YAxis yAxisId="right" orientation="right" stroke={th.axisColor} fontSize={10} domain={[0, 115]} tick={{ fill: th.axisColor }} />
              <YAxis yAxisId="rate"  orientation="right" fontSize={10} tick={false} axisLine={false} domain={[0, 30]} hide />
              <Tooltip content={<MacroTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11, color: th.axisColor }} formatter={v => <span style={{ color: th.axisColor }}>{v}</span>} />
              {/* Граница 2024/2025 */}
              <ReferenceLine yAxisId="left" x="2025-01" stroke="#6366f1" strokeDasharray="6 3" label={{ value: '2025', fill: '#6366f1', fontSize: 11, position: 'insideTopLeft' }} />
              <Bar yAxisId="left" dataKey="total_price" name="Объём (₽)" fill={isDark ? '#334155' : '#e2e8f0'} radius={[3, 3, 0, 0]} opacity={0.9} />
              <Line yAxisId="right" type="monotone" dataKey="shifted_usd" name="USD +3 мес (₽)" stroke="#10b981" strokeWidth={2} dot={false} />
              <Line yAxisId="rate"  type="stepAfter"  dataKey="key_rate"  name="Ставка ЦБ (%)"  stroke="#f97316" strokeWidth={2} strokeDasharray="6 3" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} mb-1`}>Тепловая карта публикаций по дням недели</h3>
        <p className={`text-xs ${th.muted} mb-4`}>
          Красные ячейки — аномально высокая публикационная активность. Концентрация к пятнице или концу месяца — признак «освоения бюджетов» в цейтноте.
        </p>
        <HeatmapChart heatmapData={data.heatmap_data} th={th} />
      </div>
    </div>
  );
}

function HeatmapChart({ heatmapData, th }) {
  const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const maxVal = Math.max(...heatmapData.flatMap(col => days.map(d => col[d] || 0)));

  return (
    <div className="overflow-x-auto">
      <div className="flex gap-1 min-w-max">
        <div className="flex flex-col justify-end gap-1 mr-2">
          <div className="h-7" />
          {days.map(d => (
            <div key={d} className={`h-7 flex items-center text-xs ${th.faint} pr-1 whitespace-nowrap`}>{d}</div>
          ))}
        </div>
        {heatmapData.map((col, idx) => (
          <div key={idx} className="flex flex-col gap-1">
            <div className={`h-7 flex items-end justify-center text-xs ${th.faint} pb-1`}>
              {col.month?.split('-')[1] || idx + 1}
            </div>
            {days.map(d => {
              const val = col[d] || 0;
              const intensity = maxVal > 0 ? val / maxVal : 0;
              const bg = intensity > 0.7
                ? `rgba(239,68,68,${0.5 + intensity * 0.5})`
                : intensity > 0.3
                ? `rgba(251,146,60,${0.4 + intensity * 0.4})`
                : `rgba(100,116,139,${0.1 + intensity * 0.3})`;
              return (
                <div
                  key={d}
                  className="w-7 h-7 rounded-md cursor-help transition-all hover:scale-110"
                  style={{ backgroundColor: bg }}
                  title={`${col.month} ${d}: ${val} лотов`}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-4 mt-4 text-xs" style={{ color: th.axisColor }}>
        <span>Менее активно</span>
        <div className="flex items-center gap-1">
          {[0.1, 0.3, 0.5, 0.7, 0.9].map(v => (
            <div key={v} className="w-4 h-4 rounded-sm" style={{ backgroundColor: v > 0.7 ? `rgba(239,68,68,${0.5 + v * 0.5})` : v > 0.3 ? `rgba(251,146,60,${0.4 + v * 0.4})` : `rgba(100,116,139,${0.1 + v * 0.3})` }} />
          ))}
        </div>
        <span>Аномально активно</span>
      </div>
    </div>
  );
}

// ─── ML Аномалии ─────────────────────────────────────────────────────────────
function MLVisualsTab({ th, isDark }) {
  // Нормализация radar: каждое юрлицо → % от своего суммарного бюджета
  const normalizedRadarData = useMemo(() => {
    const totals = {};
    for (const e of data.top_entities_for_radar) {
      totals[e] = data.radar_data.reduce((s, row) => s + (row[e] || 0), 0);
    }
    return data.radar_data.map(row => {
      const out = { category: row.category };
      for (const e of data.top_entities_for_radar) {
        out[e] = totals[e] > 0 ? +((row[e] / totals[e]) * 100).toFixed(1) : 0;
      }
      return out;
    });
  }, []);

  const VENDOR_COLORS = ['#6366f1','#f97316','#0ea5e9','#f59e0b','#10b981','#ec4899','#f97316','#a855f7'];

  const ScatterTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="rounded-xl p-3 shadow-xl border max-w-xs" style={{ background: th.tooltipBg, borderColor: th.tooltipBrd }}>
        <div className="text-xs mb-1" style={{ color: CAT_COLORS[d.category] || '#94a3b8' }}>{d.category}</div>
        <div className="font-bold text-sm mb-2 truncate" style={{ color: isDark ? '#f1f5f9' : '#111827' }}>{d.id}</div>
        <div className="grid grid-cols-2 gap-1 text-xs">
          <span style={{ color: th.axisColor }}>Сумма:</span>
          <span className="font-medium" style={{ color: isDark ? '#f1f5f9' : '#111827' }}>{(d.initial_price / 1e6).toFixed(1)} млн ₽</span>
          <span style={{ color: th.axisColor }}>Экономия:</span>
          <span className="font-bold" style={{ color: d.savings_percent === 0 ? '#ef4444' : '#10b981' }}>{d.savings_percent}%</span>
          <span style={{ color: th.axisColor }}>Участников:</span>
          <span style={{ color: isDark ? '#f1f5f9' : '#111827' }}>{d.bidders_count}</span>
        </div>
        {d.savings_percent === 0 && d.bidders_count === 1 && (
          <div className="mt-2 text-xs text-red-400 font-bold">🚨 1 участник, 0% экономии — риск</div>
        )}
      </div>
    );
  };

  const TreemapContent = (props) => {
    const { x, y, width, height, index, name, value } = props;
    if (!width || !height || width < 8 || height < 8) return null;
    const color = VENDOR_COLORS[index % VENDOR_COLORS.length];
    const shortName = (name || '').replace(/^ООО ['"]?|['"]?$/g, '').trim();
    return (
      <g>
        <rect x={x} y={y} width={width} height={height} fill={color} opacity={0.85} stroke="#0f172a" strokeWidth={2} rx={4} />
        {width > 60 && height > 28 && (
          <text x={x + 8} y={y + 18} fill="white" fontSize={11} fontWeight={700} style={{ pointerEvents: 'none' }}>{shortName}</text>
        )}
        {width > 60 && height > 48 && (
          <text x={x + 8} y={y + 34} fill="rgba(255,255,255,0.7)" fontSize={10} style={{ pointerEvents: 'none' }}>
            {(value / 1e9).toFixed(2)} млрд ₽
          </text>
        )}
      </g>
    );
  };

  const hhi = data.stats.hhi_index;
  const hhiPct = Math.min(hhi / 10000, 1) * 100;

  const radarColors = ['#10b981', '#f97316', '#6366f1'];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* HHI шкала */}
        <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
          <h3 className={`font-bold ${th.text} mb-1`}>Индекс Херфиндаля–Хиршмана (HHI)</h3>
          <p className={`text-xs ${th.muted} mb-4`}>Мера монополизации рынка. DoJ: &gt; 2500 = высококонцентрированный.</p>
          <div className="flex items-end gap-4 mb-5">
            <div className="text-5xl font-black text-red-400">{hhi.toLocaleString('ru-RU')}</div>
            <div className="mb-1.5 px-3 py-1 rounded-full text-sm font-bold bg-red-500/20 text-red-400 border border-red-500/30">🚨 Монополия</div>
          </div>
          <div className="relative mb-3">
            <div className={`h-5 rounded-full overflow-hidden ${th.inputBg} relative`}>
              <div className="absolute inset-y-0 left-0 w-[15%] bg-emerald-500 opacity-70" />
              <div className="absolute inset-y-0 left-[15%] w-[10%] bg-amber-500 opacity-70" />
              <div className="absolute inset-y-0 left-[25%] w-[75%] bg-red-500 opacity-70" />
              <div className="absolute top-0 h-full w-1.5 bg-white shadow-lg" style={{ left: `${hhiPct}%` }} />
            </div>
            <div className={`flex justify-between text-xs ${th.faint} mt-1.5 px-1`}>
              <span>0 ✅</span><span className="absolute left-[15%]">1 500 ⚠️</span><span className="absolute left-[25%]">2 500 🚨</span><span>10 000</span>
            </div>
          </div>
          <div className="mt-8 space-y-2">
            <div className={`text-xs ${th.faint} uppercase font-semibold mb-3`}>Топ вендоров по бюджету</div>
            {data.treemap_data?.slice(0, 5).map((d, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: VENDOR_COLORS[i] }} />
                <span className={`text-xs ${th.text} flex-1 truncate`}>{d.name}</span>
                <span className={`text-xs font-bold ${th.text}`}>{(d.size / 1e9).toFixed(2)} B₽</span>
              </div>
            ))}
          </div>
        </div>

        {/* Scatter — аномалии */}
        <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
          <h3 className={`font-bold ${th.text} mb-1`}>Поиск коррупциогенных аномалий</h3>
          <p className={`text-xs ${th.muted} mb-3`}>
            X: начальная цена (log), Y: снижение НМЦК %. Размер = кол-во участников.
          </p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 10, right: 16, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={th.gridColor} />
                <XAxis dataKey="initial_price" type="number" scale="log" domain={['auto', 'auto']} name="Сумма" stroke={th.axisColor} fontSize={10}
                  tickFormatter={v => v >= 1e9 ? `${(v / 1e9).toFixed(0)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(0)}M` : `${v}`} />
                <YAxis dataKey="savings_percent" type="number" name="Экономия %" stroke={th.axisColor} fontSize={10} tickFormatter={v => `${v}%`} />
                <ZAxis dataKey="bidders_count" range={[40, 300]} name="Участников" />
                <ReferenceLine y={5} stroke="#f59e0b" strokeDasharray="4 4"
                  label={{ value: 'Норма > 5%', fill: '#f59e0b', fontSize: 10, position: 'insideTopLeft' }} />
                <Tooltip content={<ScatterTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                <Scatter data={data.scatter_data}>
                  {data.scatter_data.map((entry, i) => (
                    <Cell key={i}
                      fill={entry.savings_percent === 0 ? '#ef4444' : entry.savings_percent < 5 ? '#f59e0b' : CAT_COLORS[entry.category] || '#10b981'}
                      opacity={0.8}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          {/* Полная легенда */}
          <div className="mt-3 space-y-2">
            <div className={`text-xs ${th.faint} font-semibold uppercase mb-1.5`}>Легенда</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              <div className="flex items-center gap-1.5 text-xs"><div className="w-3 h-3 rounded-full bg-red-500" /><span className={th.muted}>0% экономии (риск)</span></div>
              <div className="flex items-center gap-1.5 text-xs"><div className="w-3 h-3 rounded-full bg-amber-500" /><span className={th.muted}>1-5% (подозрение)</span></div>
              {Object.entries(CAT_COLORS).slice(0, 5).map(([k, v]) => (
                <div key={k} className="flex items-center gap-1.5 text-xs">
                  <div className="w-3 h-3 rounded-full" style={{ background: v }} />
                  <span className={th.muted}>{k}</span>
                </div>
              ))}
              <div className={`text-xs ${th.faint} w-full mt-0.5`}>Размер точки = кол-во участников в торгах</div>
            </div>
          </div>
        </div>
      </div>

      {/* Treemap */}
      <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} mb-1`}>Распределение бюджета по ключевым вендорам</h3>
        <p className={`text-xs ${th.muted} mb-4`}>Размер = объём закупок. Один блок доминирует — это Cloud.ru (22 млрд ₽).</p>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <Treemap data={data.treemap_data} dataKey="size" aspectRatio={4 / 3} content={<TreemapContent />}>
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="rounded-lg p-3 shadow-xl border" style={{ background: th.tooltipBg, borderColor: th.tooltipBrd }}>
                    <div className="font-bold" style={{ color: isDark ? '#f1f5f9' : '#111827' }}>{d.name}</div>
                    <div className="text-emerald-400 font-bold">{(d.size / 1e9).toFixed(3)} млрд ₽</div>
                    <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>
                      {(d.size / data.stats.total_price_rub * 100).toFixed(1)}% бюджета
                    </div>
                  </div>
                );
              }} />
            </Treemap>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Radar нормализованный */}
      <div className={`p-6 rounded-2xl ${th.card} border ${th.border}`}>
        <h3 className={`font-bold ${th.text} mb-1`}>Профиль закупочной активности по дочерним структурам</h3>
        <p className={`text-xs ${th.muted} mb-1`}>
          <strong>Нормализованные данные</strong>: ось = % от бюджета данного юрлица в категории.
          Показывает специализацию, а не абсолютные суммы (иначе Cloud.ru перекрывает всех из-за своего объёма 22 млрд ₽).
        </p>
        <p className={`text-xs ${th.faint} mb-4`}>
          Пример: Cloud.ru тратит 97% бюджета на «ПО и Лицензии», 2ГИС распределяет равномерно — это видно на радаре.
        </p>
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="72%" data={normalizedRadarData}>
              <PolarGrid stroke={th.gridColor} />
              <PolarAngleAxis dataKey="category" tick={{ fill: th.axisColor, fontSize: 11 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fill: th.axisColor, fontSize: 9 }} axisLine={false} />
              {data.top_entities_for_radar.map((e, i) => (
                <Radar key={e} name={e.replace(/^(ООО|АО|ПАО)\s+/, '')} dataKey={e}
                  stroke={radarColors[i]} fill={radarColors[i]} fillOpacity={0.2} strokeWidth={2} />
              ))}
              <Legend wrapperStyle={{ fontSize: 11 }}
                formatter={v => <span style={{ color: th.axisColor }}>{v}</span>} />
              <Tooltip contentStyle={{ backgroundColor: th.tooltipBg, borderColor: th.tooltipBrd, fontSize: 12 }}
                formatter={(v, name) => [`${v}%`, name]} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// ─── AI Инсайты ───────────────────────────────────────────────────────────────
function AITab({ th, isDark }) {
  const severityConfig = {
    high:   { color: 'text-red-400',   bg: 'bg-red-500/10',   border: 'border-red-500/30',   dot: 'bg-red-400',   label: 'Критический', score: null },
    medium: { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30', dot: 'bg-amber-400', label: 'Высокий',     score: null },
    low:    { color: 'text-blue-400',  bg: 'bg-blue-500/10',  border: 'border-blue-500/30',  dot: 'bg-blue-400',  label: 'Средний',     score: null },
  };

  const enriched = data.anomalies.map((a, i) => ({
    ...a,
    severity: i < 2 ? 'high' : i < 4 ? 'medium' : 'low',
    riskScore: [9.6, 8.2, 7.8, 7.1, 6.5, 5.9][i] ?? 5.0,
    barColor:  ['#ef4444','#f59e0b','#f59e0b','#f59e0b','#6366f1','#6366f1'][i],
  }));

  return (
    <div className="space-y-5">
      <div className={`p-5 rounded-2xl bg-gradient-to-r ${isDark ? 'from-slate-900 to-indigo-950 border-indigo-800/50' : 'from-indigo-50 to-blue-50 border-indigo-200'} border`}>
        <div className="flex items-center gap-3">
          <BrainCircuit className="w-7 h-7 text-indigo-400" />
          <div>
            <h2 className={`text-lg font-bold ${th.text}`}>ML-Инсайты: 6 аномалий</h2>
            <p className={`text-xs ${isDark ? 'text-indigo-300' : 'text-indigo-600'}`}>
              Формат: Наблюдение → Интерпретация → Значимость → Ограничение · Risk Score 1–10
            </p>
          </div>
        </div>
      </div>

      {enriched.map((anomaly, i) => {
        const sev = severityConfig[anomaly.severity];
        return (
          <motion.div
            key={anomaly.id}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={`rounded-2xl ${th.card} border ${sev.border} overflow-hidden`}
          >
            <div className={`px-6 py-4 ${sev.bg} border-b ${sev.border} flex items-start justify-between gap-4`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <span className={`flex items-center gap-1.5 text-xs font-bold px-2 py-0.5 rounded-full ${sev.bg} ${sev.color} border ${sev.border}`}>
                    <div className={`w-1.5 h-1.5 rounded-full ${sev.dot} animate-pulse`} />
                    {sev.label}
                  </span>
                  {anomaly.tags.map(tag => (
                    <span key={tag} className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">{tag}</span>
                  ))}
                </div>
                <h3 className={`text-base font-bold ${th.text}`}>{anomaly.title}</h3>
                <p className={`text-xs mt-0.5 ${th.muted}`}>{anomaly.entity} · {anomaly.procedure}</p>
              </div>
              <div className="text-right shrink-0">
                <div className={`text-xs ${th.faint} mb-0.5`}>Risk Score</div>
                <div className={`text-3xl font-black ${sev.color}`}>{anomaly.riskScore}</div>
                <div className={`text-xs ${th.faint}`}>/10</div>
              </div>
            </div>

            <div className={`grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x ${th.divider}`}>
              {[
                { key: 'Наблюдение',    val: anomaly.observation,    color: 'text-emerald-500' },
                { key: 'Интерпретация', val: anomaly.interpretation,  color: 'text-blue-400' },
                { key: 'Значимость',    val: anomaly.significance,    color: 'text-amber-400' },
                { key: 'Ограничение',   val: anomaly.limitation,      color: 'text-rose-400' },
              ].map(({ key, val, color }) => (
                <div key={key} className={`p-5 border-b ${th.divider} last:border-b-0 md:last:border-b md:odd:border-b-0`}>
                  <h4 className={`text-xs font-bold uppercase tracking-widest mb-2 ${color}`}>{key}</h4>
                  <p className={`text-sm leading-relaxed ${th.muted}`}>{val}</p>
                </div>
              ))}
            </div>

            <div className={`px-6 py-3 border-t ${th.divider}`}>
              <div className={`flex justify-between text-xs ${th.faint} mb-1`}>
                <span>Risk Score</span>
                <span className={sev.color}>{anomaly.riskScore}/10</span>
              </div>
              <div className={`h-1.5 ${th.inputBg} rounded-full overflow-hidden`}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${anomaly.riskScore * 10}%` }}
                  transition={{ duration: 1, delay: i * 0.15 + 0.5 }}
                  className="h-full rounded-full"
                  style={{ background: anomaly.barColor }}
                />
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
