import { ArrowRight, HelpCircle, Shield, XCircle } from "lucide-react";
import DefenseText from "./DefenseText.jsx";

const alternatives = {
  PROCEED: [
    { key: "why_not_stop", label: "Why not STOP?", icon: XCircle, color: "red" },
    {
      key: "why_not_investigate",
      label: "Why not INVESTIGATE?",
      icon: HelpCircle,
      color: "yellow",
    },
  ],
  STOP: [
    {
      key: "why_not_proceed",
      label: "Why not PROCEED?",
      icon: ArrowRight,
      color: "green",
    },
    {
      key: "why_not_investigate",
      label: "Why not INVESTIGATE?",
      icon: HelpCircle,
      color: "yellow",
    },
  ],
  INVESTIGATE: [
    {
      key: "why_not_proceed",
      label: "Why not PROCEED confidently?",
      icon: ArrowRight,
      color: "green",
    },
    {
      key: "why_not_stop",
      label: "Why not STOP completely?",
      icon: XCircle,
      color: "red",
    },
  ],
};

const colorClasses = {
  red: {
    border: "border-red-500",
    icon: "text-red-400",
  },
  yellow: {
    border: "border-yellow-500",
    icon: "text-yellow-400",
  },
  green: {
    border: "border-green-500",
    icon: "text-green-400",
  },
};

const DecisionDefensePanel = ({ recommendation, defenses }) => {
  const relevantDefenses = alternatives[recommendation] || [];

  if (!defenses || relevantDefenses.length === 0) return null;

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <Shield className="text-blue-400" size={24} />
        <h3 className="text-xl font-semibold">Decision Defense</h3>
      </div>

      <div className="text-sm text-slate-400 mb-4">
        Why this decision vs. alternatives:
      </div>

      <div className="space-y-4">
        {relevantDefenses.map((alt, idx) => {
          const Icon = alt.icon;
          const defense = defenses[alt.key];
          const classes = colorClasses[alt.color] || colorClasses.yellow;

          if (!defense) return null;

          return (
            <div
              key={idx}
              className={`relative bg-slate-900/50 rounded-lg p-4 border-l-4 ${classes.border} hover:bg-slate-900/70 transition-colors`}
            >
              <div className="flex items-center gap-3 mb-3">
                <Icon className={classes.icon} size={20} />
                <h4 className="font-semibold text-slate-200">{alt.label}</h4>
              </div>

              <div className="pl-8">
                <DefenseText text={defense} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 p-3 bg-blue-900/20 border-l-4 border-blue-500 rounded text-sm text-slate-400">
        <Shield className="inline mr-2" size={14} />
        This decision was evaluated against alternative approaches using available data
      </div>
    </div>
  );
};

export default DecisionDefensePanel;
