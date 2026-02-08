import { CheckCircle, TrendingUp } from "lucide-react";

export default function BreakEvenCard({ breakeven }) {
  if (!breakeven) {
    return null;
  }

  const keyDriver = breakeven.key_driver || "";
  const assumptions = breakeven.assumptions || [];

  return (
    <div className="bg-gradient-to-br from-green-900/20 to-emerald-900/20 border border-green-700 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-4">
        <TrendingUp className="text-green-400" size={24} />
        <h3 className="text-xl font-semibold">Break-Even Analysis</h3>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="text-center">
          <div className="text-3xl font-bold text-green-400">
            {breakeven.months_min}-{breakeven.months_max}
          </div>
          <div className="text-sm text-slate-400">Months to Break-Even</div>
        </div>

        <div className="flex items-center justify-center">
          <div className="text-center">
            <div className="text-sm text-slate-400 mb-1">Key Driver</div>
            <div className="font-semibold text-slate-200">
              {keyDriver.length > 50 ? `${keyDriver.substring(0, 50)}...` : keyDriver}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-slate-900/50 rounded-lg p-4">
        <div className="text-sm font-medium text-slate-400 mb-2">Critical Assumptions:</div>
        <ul className="space-y-1 text-sm">
          {assumptions.map((assumption, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <CheckCircle className="text-green-400 flex-shrink-0 mt-0.5" size={14} />
              <span className="text-slate-300">{assumption}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
