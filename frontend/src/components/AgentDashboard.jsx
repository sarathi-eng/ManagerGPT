import { useEffect, useRef } from "react";
import { Loader } from "lucide-react";
import AgentCard from "./AgentCard.jsx";
import ProgressBar from "./ProgressBar.jsx";

export default function AgentDashboard({ logs, isRunning }) {
  const logsEndRef = useRef(null);

  const latestInfo = [...logs]
    .reverse()
    .find((log) => log?.metadata?.estimated_time);
  const latestProgress = [...logs]
    .reverse()
    .find((log) => log?.metadata?.progress || log?.metadata?.elapsed);

  const estimatedTime = latestInfo?.metadata?.estimated_time || 0;
  const elapsedTime = latestProgress?.metadata?.elapsed || 0;

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-semibold">AI Workforce Activity</h2>
        {isRunning && (
          <div className="flex items-center gap-2 text-blue-400">
            <Loader className="animate-spin" size={20} />
            <span>Processing...</span>
          </div>
        )}
      </div>

      {isRunning && estimatedTime > 0 && (
        <ProgressBar estimatedTime={estimatedTime} elapsedTime={elapsedTime} />
      )}

      <div className="space-y-3">
        {logs.length === 0 && (
          <div className="space-y-3">
            {[...Array(3)].map((_, index) => (
              <div
                key={index}
                className="h-20 rounded-lg bg-slate-800/40 border border-slate-700 animate-pulse"
              />
            ))}
          </div>
        )}

        {logs.map((log, index) => (
          <AgentCard key={`${log.agent}-${index}`} log={log} />
        ))}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}
