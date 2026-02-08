import { DollarSign } from "lucide-react";

export default function PricingFeasibility({ pricing }) {
  if (!pricing) {
    return null;
  }

  const pricePoints = pricing.price_points || {};
  const sensitivity = pricing.sensitivity || "MEDIUM";

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <DollarSign className="text-emerald-400" size={24} />
        Pricing Feasibility
      </h3>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="text-center p-4 bg-slate-900/50 rounded-lg">
          <div className="text-sm text-slate-400 mb-1">Optimal Min</div>
          <div className="text-2xl font-bold text-emerald-400">{pricing.optimal_min}</div>
        </div>
        <div className="text-center p-4 bg-slate-900/50 rounded-lg">
          <div className="text-sm text-slate-400 mb-1">Optimal Max</div>
          <div className="text-2xl font-bold text-emerald-400">{pricing.optimal_max}</div>
        </div>
      </div>

      <div className="mb-4 p-3 bg-slate-900/50 rounded-lg">
        <div className="text-sm text-slate-400 mb-1">Price Sensitivity</div>
        <div className="font-semibold text-slate-200">{sensitivity}</div>
      </div>

      {Object.keys(pricePoints).length > 0 && (
        <div>
          <div className="text-sm font-medium text-slate-400 mb-2">Price Points</div>
          <div className="space-y-2">
            {Object.entries(pricePoints).map(([price, assessment]) => (
              <div key={price} className="flex items-center justify-between text-sm">
                <span className="text-slate-300">{price}</span>
                <span className="text-slate-400">{assessment}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {pricing.reasoning && (
        <div className="mt-4 p-3 bg-emerald-900/20 border-l-4 border-emerald-500 rounded">
          <div className="text-sm text-slate-300">{pricing.reasoning}</div>
        </div>
      )}
    </div>
  );
}
