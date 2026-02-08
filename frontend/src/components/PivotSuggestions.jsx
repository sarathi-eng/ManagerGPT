import { ArrowRight, RefreshCw } from "lucide-react";

export default function PivotSuggestions({ pivots }) {
  if (!pivots || pivots.length === 0) {
    return null;
  }

  return (
    <div className="bg-gradient-to-br from-purple-900/20 to-pink-900/20 border border-purple-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <RefreshCw className="text-purple-400" size={24} />
        Alternative Approaches (Pivots)
      </h3>

      <div className="text-sm text-slate-400 mb-4">
        Instead of the original plan, consider these alternatives:
      </div>

      <div className="space-y-4">
        {pivots.map((pivot, idx) => (
          <div key={idx} className="bg-slate-900/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-lg text-purple-300">{pivot.pivot}</h4>
              <span className="px-3 py-1 bg-purple-500/30 text-purple-300 rounded-full text-sm">
                {(pivot.viability * 100).toFixed(0)}% viable
              </span>
            </div>

            <div className="text-sm text-slate-300 mb-3">{pivot.reasoning}</div>

            <div>
              <div className="text-sm font-medium text-purple-400 mb-2">Required Changes:</div>
              <ul className="space-y-1">
                {pivot.changes_needed.map((change, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <ArrowRight className="text-purple-400 flex-shrink-0 mt-0.5" size={14} />
                    <span>{change}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
