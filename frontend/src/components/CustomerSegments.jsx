import { Users } from "lucide-react";

export default function CustomerSegments({ segments }) {
  if (!segments) {
    return null;
  }

  const primary = segments.primary || {};
  const secondary = segments.secondary || {};
  const poorFit = segments.poor_fit || [];

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Users className="text-blue-400" size={24} />
        Target Customer Segments
      </h3>

      <div className="mb-4 p-4 bg-blue-900/20 border-l-4 border-blue-500 rounded">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-semibold text-blue-400">Primary Segment</h4>
          <span className="px-3 py-1 bg-blue-500/30 text-blue-300 rounded-full text-sm">
            Fit Score: {(Number(primary.fit_score || 0) * 100).toFixed(0)}%
          </span>
        </div>
        <div className="text-lg font-medium mb-1">{primary.segment}</div>
        <div className="text-sm text-slate-400 mb-2">Size: {primary.size}</div>
        <div className="text-sm text-slate-300">{primary.reasoning}</div>
      </div>

      <div className="mb-4 p-4 bg-purple-900/20 border-l-4 border-purple-500 rounded">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-semibold text-purple-400">Secondary Segment</h4>
          <span className="px-3 py-1 bg-purple-500/30 text-purple-300 rounded-full text-sm">
            Fit Score: {(Number(secondary.fit_score || 0) * 100).toFixed(0)}%
          </span>
        </div>
        <div className="text-lg font-medium mb-1">{secondary.segment}</div>
        <div className="text-sm text-slate-400 mb-2">Size: {secondary.size}</div>
        <div className="text-sm text-slate-300">{secondary.reasoning}</div>
      </div>

      {poorFit.length > 0 && (
        <div className="p-4 bg-red-900/20 border-l-4 border-red-500 rounded">
          <h4 className="font-semibold text-red-400 mb-2">❌ Avoid These Segments</h4>
          <ul className="space-y-2">
            {poorFit.map((seg, idx) => (
              <li key={idx} className="text-sm">
                <span className="font-medium text-slate-200">
                  {typeof seg === "string" ? seg : seg.segment}
                </span>
                {typeof seg === "string" ? null : (
                  <span className="text-slate-400"> — {seg.reasoning}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
