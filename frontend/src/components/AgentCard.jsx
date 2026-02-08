import {
  AlertCircle,
  BarChart,
  CheckCircle,
  ClipboardList,
  Cpu,
  Loader,
  Search,
  Shield,
  XCircle,
} from "lucide-react";

const statusConfig = {
  working: {
    icon: Loader,
    iconClass: "text-blue-400 animate-spin",
    borderClass: "border-blue-500",
    bgClass: "bg-blue-500/10",
  },
  complete: {
    icon: CheckCircle,
    iconClass: "text-green-400",
    borderClass: "border-green-500",
    bgClass: "bg-green-500/10",
  },
  rejected: {
    icon: XCircle,
    iconClass: "text-red-400",
    borderClass: "border-red-500",
    bgClass: "bg-red-500/10",
  },
  error: {
    icon: AlertCircle,
    iconClass: "text-yellow-400",
    borderClass: "border-yellow-500",
    bgClass: "bg-yellow-500/10",
  },
};

const agentIcons = {
  Planner: ClipboardList,
  Researcher: Search,
  Analyst: BarChart,
  Critic: Shield,
  System: Cpu,
};

const formatTime = (timestamp) => {
  if (!timestamp) return "";
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(timestamp)
    ? timestamp
    : `${timestamp}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString();
};

export default function AgentCard({ log }) {
  const config = statusConfig[log.status] || statusConfig.working;
  const StatusIcon = config.icon;
  const AgentIcon = agentIcons[log.agent] || Cpu;

  return (
    <div
      className={`flex items-start gap-4 p-4 rounded-lg border-l-4 ${config.borderClass} ${config.bgClass} backdrop-blur bg-slate-800/50 animate-slideIn`}
    >
      <div className="flex flex-col items-center gap-2">
        <AgentIcon className="text-slate-300" size={20} />
        <StatusIcon className={config.iconClass} size={20} />
      </div>

      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="font-semibold text-lg">{log.agent}</span>
          <span className="text-xs text-slate-500">{formatTime(log.timestamp)}</span>
        </div>
        <p className="text-slate-300">{log.message}</p>
      </div>
    </div>
  );
}
