import { BookOpen, Lightbulb } from "lucide-react";

export default function ComparableCases({ cases }) {
  if (!cases || cases.length === 0) {
    return null;
  }

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <BookOpen className="text-indigo-400" size={24} />
        Comparable Case Studies
      </h3>

      <div className="space-y-4">
        {cases.map((case_, idx) => (
          <div key={idx} className="bg-slate-900/50 rounded-lg p-4 border-l-4 border-indigo-500">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-lg">{case_.business}</h4>
              <span
                className={`px-3 py-1 rounded-full text-sm ${
                  case_.outcome.startsWith("SUCCESS")
                    ? "bg-green-900/40 text-green-400"
                    : case_.outcome.startsWith("MIXED")
                    ? "bg-yellow-900/40 text-yellow-400"
                    : "bg-red-900/40 text-red-400"
                }`}
              >
                {String(case_.outcome || "").split(" - ")[0]}
              </span>
            </div>

            <div className="text-sm text-slate-400 mb-3">Model: {case_.model}</div>

            {String(case_.outcome || "").includes(" - ") && (
              <div className="text-sm text-slate-300 mb-3">
                {String(case_.outcome || "").split(" - ")[1]}
              </div>
            )}

            <div>
              <div className="text-sm font-medium text-indigo-400 mb-2">Key Lessons:</div>
              <ul className="space-y-1">
                {(case_.lessons || []).map((lesson, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <Lightbulb className="text-indigo-400 flex-shrink-0 mt-0.5" size={14} />
                    <span>{lesson}</span>
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
