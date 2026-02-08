import { Calculator } from "lucide-react";

export default function UnitEconomics({ economics }) {
  if (!economics) {
    return null;
  }

  const breakdown = economics.breakdown || null;
  const marginColor =
    economics.gross_margin_pct >= 40
      ? "text-green-400"
      : economics.gross_margin_pct >= 25
      ? "text-yellow-400"
      : "text-red-400";

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Calculator className="text-purple-400" size={24} />
        Unit Economics
      </h3>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-4 bg-slate-900/50 rounded-lg">
          <div className="text-sm text-slate-400 mb-1">Cost per Unit</div>
          <div className="text-2xl font-bold text-red-400">₹{economics.cost_per_unit}</div>
        </div>

        <div className="text-center p-4 bg-slate-900/50 rounded-lg">
          <div className="text-sm text-slate-400 mb-1">Revenue per Unit</div>
          <div className="text-2xl font-bold text-green-400">₹{economics.revenue_per_unit}</div>
        </div>

        <div className="text-center p-4 bg-slate-900/50 rounded-lg">
          <div className="text-sm text-slate-400 mb-1">Gross Margin</div>
          <div className={`text-2xl font-bold ${marginColor}`}>
            {Number(economics.gross_margin_pct || 0).toFixed(0)}%
          </div>
        </div>
      </div>

      {breakdown && (
        <div className="mb-4">
          <div className="text-sm font-medium text-slate-400 mb-2">Cost Breakdown:</div>
          <div className="space-y-2">
            {Object.entries(breakdown).map(([category, cost]) => (
              <div key={category} className="flex items-center gap-2">
                <span className="text-sm text-slate-400 w-32">{category}</span>
                <div className="flex-1 bg-slate-700 rounded-full h-2">
                  <div
                    className="bg-purple-500 h-2 rounded-full"
                    style={{
                      width: `${(Number(cost) / Number(economics.cost_per_unit || 1)) * 100}%`,
                    }}
                  />
                </div>
                <span className="text-sm font-semibold w-16 text-right">₹{cost}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-lg">
        <div>
          <div className="text-sm text-slate-400">Economics Health</div>
          <div
            className={`text-lg font-bold ${
              economics.health === "STRONG"
                ? "text-green-400"
                : economics.health === "ACCEPTABLE"
                ? "text-yellow-400"
                : "text-red-400"
            }`}
          >
            {economics.health}
          </div>
        </div>

        <div>
          <div className="text-sm text-slate-400">Margin Buffer</div>
          <div
            className={`text-lg font-bold ${
              economics.margin_buffer === "HIGH"
                ? "text-green-400"
                : economics.margin_buffer === "MEDIUM"
                ? "text-yellow-400"
                : "text-red-400"
            }`}
          >
            {economics.margin_buffer}
          </div>
        </div>
      </div>

      {economics.notes && (
        <div className="mt-4 p-3 bg-blue-900/20 border-l-4 border-blue-500 rounded">
          <div className="text-sm text-slate-300">{economics.notes}</div>
        </div>
      )}
    </div>
  );
}
