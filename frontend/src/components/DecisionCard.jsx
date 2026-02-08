import { AlertTriangle, ThumbsDown, ThumbsUp } from "lucide-react";
import SourceHighlightedText from "./SourceHighlightedText.jsx";

const decisionConfig = {
  PROCEED: {
    color: "green",
    icon: ThumbsUp,
    label: "Recommended to Proceed",
  },
  STOP: {
    color: "red",
    icon: ThumbsDown,
    label: "Not Recommended",
  },
  INVESTIGATE: {
    color: "yellow",
    icon: AlertTriangle,
    label: "Further Investigation Needed",
  },
};

export default function DecisionCard({ result, sourceMap }) {
  const config = decisionConfig[result.final_decision] || decisionConfig.INVESTIGATE;
  const Icon = config.icon;
  const colorMap = {
    green: { text: "text-green-400", bar: "bg-green-500" },
    red: { text: "text-red-400", bar: "bg-red-500" },
    yellow: { text: "text-yellow-400", bar: "bg-yellow-500" },
  };
  const colors = colorMap[config.color];
  const fallbackConfidence =
    result.confidence ?? result.business_analysis?.confidence ?? result.business_analysis?.analysis?.confidence;
  const confidenceValue = result.confidence_score ?? fallbackConfidence ?? 0;
  const confidencePct = Math.round(Number(confidenceValue || 0) * 100);
  const modelInfo = result.model_info || {};
  const researchInfo = result.research_info || {};
  const businessModel = modelInfo.business_analyst_model || "Unknown";
  const researchProvider = researchInfo.provider || "unknown";
  const sourcesCount = Number(researchInfo.sources_count || 0);

  return (
    <div>
      <div className="text-center mb-6">
        <Icon className={`inline-block ${colors.text} mb-2`} size={48} />
        <h2 className="text-3xl font-bold">{config.label}</h2>
      </div>

      <div className="mb-6">
        <div className="flex justify-between mb-2">
          <span className="text-slate-400">Confidence</span>
          <span className="font-semibold">{confidencePct}%</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-3">
          <div
            className={`${colors.bar} h-3 rounded-full transition-all duration-1000`}
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      <div>
        <h3 className="text-xl font-semibold mb-3">Analysis</h3>
        <div className="text-xs text-slate-400 mb-3">
          Model: {businessModel} via OpenRouter · Research: {researchProvider} ({sourcesCount} sources)
        </div>
        <div className="text-slate-300 leading-relaxed">
          <SourceHighlightedText
            text={result.reasoning || "No analysis summary available."}
            sourceMap={sourceMap}
          />
        </div>
      </div>
    </div>
  );
}
