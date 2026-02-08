import { AlertTriangle } from "lucide-react";

export default function FailureSignals({ signals }) {
  if (!signals || signals.length === 0) {
    return null;
  }

  return (
    <div className="bg-slate-800/50 border border-red-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <AlertTriangle className="text-red-400" size={24} />
        Early Failure Signals
      </h3>

      <div className="text-sm text-slate-400 mb-4">
        Monitor these metrics in the first 2-4 weeks. Red flags indicate pivot needed:
      </div>

      <div className="space-y-3">
        {signals.map((signal, idx) => (
          <div
            key={idx}
            className={`p-4 rounded-lg border-l-4 ${
              signal.urgency === "HIGH"
                ? "bg-red-900/20 border-red-500"
                : "bg-yellow-900/20 border-yellow-500"
            }`}
          >
            <div className="flex items-start justify-between mb-2">
              <div className="font-semibold text-slate-200">{signal.metric}</div>
              <span
                className={`px-2 py-1 rounded text-xs ${
                  signal.urgency === "HIGH"
                    ? "bg-red-500/30 text-red-300"
                    : "bg-yellow-500/30 text-yellow-300"
                }`}
              >
                {signal.urgency || "MEDIUM"}
              </span>
            </div>

            <div className="text-sm text-slate-300 mb-2">
              <span className="font-medium">Warning if: </span>
              {signal.threshold || ""}
            </div>

            <div className="text-sm text-slate-400">
              <span className="font-medium">Action: </span>
              {signal.action || ""}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
