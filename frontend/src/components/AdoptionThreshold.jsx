import { Target } from "lucide-react";

export default function AdoptionThreshold({ adoption }) {
  if (!adoption) {
    return null;
  }

  const failurePct = Number(adoption.failure_threshold_pct || 0);
  const minimumPct = Number(adoption.minimum_adoption_pct || 0);
  const maxScale = 15;

  return (
    <div className="bg-gradient-to-br from-blue-900/20 to-cyan-900/20 border border-blue-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Target className="text-cyan-400" size={24} />
        Adoption Threshold (Go/No-Go Metric)
      </h3>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="text-center p-4 bg-slate-900/50 rounded-lg">
          <div className="text-sm text-slate-400 mb-1">Minimum for Success</div>
          <div className="text-4xl font-bold text-green-400">{minimumPct}%</div>
        </div>

        <div className="text-center p-4 bg-slate-900/50 rounded-lg">
          <div className="text-sm text-slate-400 mb-1">Failure Threshold</div>
          <div className="text-4xl font-bold text-red-400">{failurePct}%</div>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-xs text-slate-400 mb-2">
          <span>0%</span>
          <span>{failurePct}%</span>
          <span>{minimumPct}%</span>
          <span>15%+</span>
        </div>

        <div className="relative h-4 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="absolute h-full bg-red-500/30"
            style={{ width: `${(failurePct / maxScale) * 100}%` }}
          />
          <div
            className="absolute h-full bg-yellow-500/30"
            style={{
              left: `${(failurePct / maxScale) * 100}%`,
              width: `${((minimumPct - failurePct) / maxScale) * 100}%`,
            }}
          />
          <div
            className="absolute h-full bg-green-500/30"
            style={{
              left: `${(minimumPct / maxScale) * 100}%`,
              width: `${((maxScale - minimumPct) / maxScale) * 100}%`,
            }}
          />
        </div>
      </div>

      <div className="space-y-3">
        <div className="p-3 bg-slate-900/50 rounded-lg">
          <div className="text-sm font-medium text-slate-400 mb-1">KPI to Track:</div>
          <div className="text-slate-200">{adoption.kpi}</div>
        </div>

        <div className="p-3 bg-slate-900/50 rounded-lg">
          <div className="text-sm font-medium text-slate-400 mb-1">Measurement Period:</div>
          <div className="text-slate-200">{adoption.measurement_period_days} days</div>
        </div>

        <div className="p-3 bg-cyan-900/20 border-l-4 border-cyan-500 rounded">
          <div className="text-sm text-slate-300">{adoption.reasoning}</div>
        </div>
      </div>
    </div>
  );
}
