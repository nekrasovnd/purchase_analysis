import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import { Sun, Moon } from 'lucide-react';

function App() {
  const [isDark, setIsDark] = useState(true);

  return (
    <div className={isDark
      ? 'min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500/30 transition-colors duration-300'
      : 'min-h-screen bg-gray-50 text-gray-900 font-sans selection:bg-cyan-200 transition-colors duration-300'
    }>
      {/* Theme toggle — fixed position */}
      <button
        onClick={() => setIsDark(d => !d)}
        className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-3 py-2 rounded-xl border text-sm font-medium shadow-lg transition-all duration-200 ${
          isDark
            ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
            : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`}
        title={isDark ? 'Светлая тема' : 'Тёмная тема'}
      >
        {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-500" />}
        <span>{isDark ? 'Светлая' : 'Тёмная'}</span>
      </button>

      <Dashboard isDark={isDark} />
    </div>
  );
}

export default App;
