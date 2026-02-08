import { Search, ThumbsDown, ThumbsUp } from "lucide-react";

const verdictConfig = {
  PROCEED: {
    label: "RECOMMENDED",
    icon: ThumbsUp,
    classes: {
      container: "bg-gradient-to-br from-green-900/30 to-green-900/10 border-green-600",
      icon: "text-green-400",
      label: "text-green-400",
      title: "text-green-300",
      accent: "border-green-500",
    },
  },
  STOP: {
    label: "NOT RECOMMENDED",
    icon: ThumbsDown,
    classes: {
      container: "bg-gradient-to-br from-red-900/30 to-red-900/10 border-red-600",
      icon: "text-red-400",
      label: "text-red-400",
      title: "text-red-300",
      accent: "border-red-500",
    },
  },
  INVESTIGATE: {
    label: "CONDITIONAL",
    icon: Search,
    classes: {
      container: "bg-gradient-to-br from-yellow-900/30 to-yellow-900/10 border-yellow-600",
      icon: "text-yellow-400",
      label: "text-yellow-400",
      title: "text-yellow-300",
      accent: "border-yellow-500",
    },
  },
};

const ExecutiveNarrative = ({ narrative, recommendation }) => {
  if (!narrative) return null;

  const config = verdictConfig[recommendation] || verdictConfig.INVESTIGATE;
  const Icon = config.icon;

  return (
    <div
      className={`
      ${config.classes.container}
      border-2
      rounded-xl p-6 mb-6
    `}
    >
      <div className="flex items-center gap-3 mb-4">
        <Icon className={config.classes.icon} size={32} />
        <div>
          <div className={`text-sm font-medium ${config.classes.label}`}>AI VERDICT</div>
          <div className={`text-2xl font-bold ${config.classes.title}`}>
            {config.label}
          </div>
        </div>
      </div>

      <div
        className={`text-lg text-slate-100 leading-relaxed border-l-4 ${config.classes.accent} pl-4`}
      >
        {narrative}
      </div>
    </div>
  );
};

export default ExecutiveNarrative;
