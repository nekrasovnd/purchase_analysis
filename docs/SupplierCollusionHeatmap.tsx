// SupplierCollusion Heatmap — React + ECharts
// Строит матрицу совместных участий поставщиков для выявления картельных кластеров
// Требует: echarts, echarts-for-react, @mui/material (или простой CSS)

import React, { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

// ─── Типы ────────────────────────────────────────────────────────────────────
interface LotParticipation {
  lot_id: string;
  supplier_inn: string;
  supplier_name: string;
  is_winner: boolean;
  bid_price: number;
}

interface CollusionHeatmapProps {
  participations: LotParticipation[];
  minCoBidRate?: number; // скрыть пары с низкой частотой совместных участий
  topN?: number;         // показывать только top-N поставщиков по частоте
}

// ─── Утилиты расчёта матрицы ─────────────────────────────────────────────────
function buildCollusionMatrix(
  participations: LotParticipation[],
  topN: number
): {
  suppliers: string[];
  supplierNames: Map<string, string>;
  matrix: number[][];
  winMatrix: number[][];
} {
  // Группируем по лоту: lot_id → Set<supplier_inn>
  const lotMap = new Map<string, Set<string>>();
  const lotWinMap = new Map<string, string>(); // lot → winner_inn
  const supplierLots = new Map<string, Set<string>>();
  const supplierNames = new Map<string, string>();

  for (const p of participations) {
    if (!lotMap.has(p.lot_id)) lotMap.set(p.lot_id, new Set());
    lotMap.get(p.lot_id)!.add(p.supplier_inn);
    if (p.is_winner) lotWinMap.set(p.lot_id, p.supplier_inn);

    if (!supplierLots.has(p.supplier_inn)) supplierLots.set(p.supplier_inn, new Set());
    supplierLots.get(p.supplier_inn)!.add(p.lot_id);
    supplierNames.set(p.supplier_inn, p.supplier_name);
  }

  // Выбираем топ-N поставщиков по кол-ву участий
  const ranked = Array.from(supplierLots.entries())
    .sort((a, b) => b[1].size - a[1].size)
    .slice(0, topN)
    .map(([inn]) => inn);

  const n = ranked.length;

  // Матрица co_bid_rate[i][j] = |A∩B| / |A∪B|  (Jaccard similarity)
  const matrix: number[][] = Array.from({ length: n }, () => Array(n).fill(0));
  // Матрица "победитель→второй" — для выявления циклического сговора
  const winMatrix: number[][] = Array.from({ length: n }, () => Array(n).fill(0));

  for (let i = 0; i < n; i++) {
    matrix[i][i] = 1; // диагональ = 1
    for (let j = i + 1; j < n; j++) {
      const a = supplierLots.get(ranked[i])!;
      const b = supplierLots.get(ranked[j])!;

      const intersection = new Set([...a].filter((x) => b.has(x)));
      const union = new Set([...a, ...b]);
      const jaccard = union.size > 0 ? intersection.size / union.size : 0;

      matrix[i][j] = jaccard;
      matrix[j][i] = jaccard;

      // Паттерн: A побеждает, B второй (или наоборот)
      let abWins = 0, baWins = 0;
      for (const lotId of intersection) {
        const winner = lotWinMap.get(lotId);
        if (winner === ranked[i]) abWins++;
        else if (winner === ranked[j]) baWins++;
      }
      if (intersection.size > 0) {
        winMatrix[i][j] = abWins / intersection.size;
        winMatrix[j][i] = baWins / intersection.size;
      }
    }
  }

  return { suppliers: ranked, supplierNames, matrix, winMatrix };
}

// ─── Основной компонент ───────────────────────────────────────────────────────
export const SupplierCollusionHeatmap: React.FC<CollusionHeatmapProps> = ({
  participations,
  minCoBidRate = 0.05,
  topN = 30,
}) => {
  const [mode, setMode] = useState<"jaccard" | "win">("jaccard");

  const { suppliers, supplierNames, matrix, winMatrix } = useMemo(
    () => buildCollusionMatrix(participations, topN),
    [participations, topN]
  );

  // Сокращаем имена для осей
  const labels = suppliers.map((inn) => {
    const name = supplierNames.get(inn) || inn;
    return name.length > 20 ? name.slice(0, 18) + "…" : name;
  });

  const activeMatrix = mode === "jaccard" ? matrix : winMatrix;

  // Формируем данные ECharts: [[row, col, value], ...]
  const heatData: [number, number, number][] = [];
  const riskPairs: { a: string; b: string; score: number }[] = [];

  for (let i = 0; i < activeMatrix.length; i++) {
    for (let j = 0; j < activeMatrix[i].length; j++) {
      const val = Math.round(activeMatrix[i][j] * 100) / 100;
      heatData.push([j, i, val]);
      if (i < j && val >= minCoBidRate && mode === "jaccard") {
        riskPairs.push({ a: labels[i], b: labels[j], score: val });
      }
    }
  }

  // Топ-5 рисковых пар для аннотации
  const topRisk = [...riskPairs].sort((a, b) => b.score - a.score).slice(0, 5);

  const option = {
    backgroundColor: "#0f172a",
    tooltip: {
      position: "top",
      formatter: (params: any) => {
        const i = params.data[1];
        const j = params.data[0];
        const val = params.data[2];
        if (mode === "jaccard") {
          return `<b>${labels[i]}</b><br/>vs<br/><b>${labels[j]}</b><br/>
                  Jaccard: <b>${(val * 100).toFixed(1)}%</b> совместных лотов<br/>
                  ${val > 0.4 ? "🚨 <span style='color:#ef4444'>Высокий риск сговора</span>" : ""}`;
        }
        return `<b>${labels[i]}</b> побеждает в <b>${(val * 100).toFixed(0)}%</b><br/>
                когда оба участвуют с <b>${labels[j]}</b>`;
      },
    },
    grid: { top: 60, bottom: 80, left: 160, right: 60 },
    xAxis: {
      type: "category",
      data: labels,
      splitArea: { show: true },
      axisLabel: {
        rotate: 45,
        color: "#94a3b8",
        fontSize: 10,
        interval: 0,
      },
    },
    yAxis: {
      type: "category",
      data: labels,
      splitArea: { show: true },
      axisLabel: { color: "#94a3b8", fontSize: 10 },
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: {
        color:
          mode === "jaccard"
            ? ["#0f172a", "#1e3a5f", "#1d4ed8", "#f59e0b", "#ef4444"]
            : ["#0f172a", "#14532d", "#16a34a", "#facc15", "#dc2626"],
      },
      textStyle: { color: "#94a3b8" },
    },
    series: [
      {
        name: mode === "jaccard" ? "Jaccard Similarity" : "Win Rate",
        type: "heatmap",
        data: heatData,
        label: {
          show: suppliers.length <= 15,
          formatter: (p: any) =>
            p.data[2] > 0.1 ? (p.data[2] * 100).toFixed(0) + "%" : "",
          color: "#fff",
          fontSize: 9,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: "rgba(239,68,68,0.5)",
          },
        },
      },
    ],
    title: {
      text:
        mode === "jaccard"
          ? "🔴 Матрица совместных участий в торгах (Jaccard)"
          : "🏆 Матрица: кто побеждает, когда оба участвуют",
      subtext: topRisk.length
        ? "Топ риск: " +
          topRisk
            .slice(0, 2)
            .map((p) => `${p.a} ↔ ${p.b} (${(p.score * 100).toFixed(0)}%)`)
            .join(" | ")
        : "",
      left: "center",
      top: 10,
      textStyle: { color: "#f1f5f9", fontSize: 14 },
      subtextStyle: { color: "#ef4444", fontSize: 11 },
    },
  };

  return (
    <div
      style={{
        background: "#0f172a",
        borderRadius: 12,
        padding: 16,
        border: "1px solid #1e293b",
      }}
    >
      {/* Переключатель режима */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {(["jaccard", "win"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: "6px 16px",
              borderRadius: 6,
              border: "none",
              cursor: "pointer",
              background: mode === m ? "#1d4ed8" : "#1e293b",
              color: mode === m ? "#fff" : "#94a3b8",
              fontSize: 12,
              fontWeight: mode === m ? 700 : 400,
            }}
          >
            {m === "jaccard" ? "Частота совместных участий" : "Паттерн победитель→второй"}
          </button>
        ))}
        <span
          style={{
            marginLeft: "auto",
            color: "#64748b",
            fontSize: 11,
            alignSelf: "center",
          }}
        >
          {suppliers.length} поставщиков · {participations.length} заявок
        </span>
      </div>

      <ReactECharts
        option={option}
        style={{ height: Math.max(400, suppliers.length * 18 + 140) }}
        theme="dark"
      />

      {/* Сигнальная панель рисков */}
      {mode === "jaccard" && topRisk.length > 0 && (
        <div
          style={{
            marginTop: 12,
            background: "#1e293b",
            borderRadius: 8,
            padding: 12,
          }}
        >
          <div style={{ color: "#ef4444", fontWeight: 700, marginBottom: 8, fontSize: 13 }}>
            🚨 Сигналы возможного сговора (Jaccard &gt; {(minCoBidRate * 100).toFixed(0)}%)
          </div>
          {topRisk.map((p, idx) => (
            <div
              key={idx}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "4px 0",
                borderBottom: "1px solid #334155",
              }}
            >
              <span
                style={{
                  background: p.score > 0.5 ? "#7f1d1d" : "#78350f",
                  color: "#fca5a5",
                  borderRadius: 4,
                  padding: "2px 6px",
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {(p.score * 100).toFixed(0)}%
              </span>
              <span style={{ color: "#cbd5e1", fontSize: 12 }}>
                {p.a} ↔ {p.b}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SupplierCollusionHeatmap;
