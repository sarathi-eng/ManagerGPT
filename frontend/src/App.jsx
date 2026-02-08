import { useEffect, useState } from "react";
import ApprovalGate from "./components/ApprovalGate.jsx";
import GoalInput from "./components/GoalInput.jsx";
import AgentDashboard from "./components/AgentDashboard.jsx";
import FinalReport from "./components/FinalReport.jsx";
import {
  createEventSource,
  executeGoal,
  fetchPendingApprovals,
  fetchSession,
  respondToApproval,
} from "./utils/api.js";

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [agentLogs, setAgentLogs] = useState([]);
  const [finalResult, setFinalResult] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const [pendingApproval, setPendingApproval] = useState(null);
  const [isFetchingResult, setIsFetchingResult] = useState(false);

  const fetchFinalResult = async (id) => {
    setIsFetchingResult(true);
    const maxAttempts = 20;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      try {
        const data = await fetchSession(id);
        const status = data?.status;
        if (status === "completed" || status === "failed") {
          setFinalResult(data);
          setAgentLogs([]);
          setIsRunning(false);
          setIsFetchingResult(false);
          return;
        }
      } catch (err) {
        // transient error; retry
      }
      await new Promise((resolve) => setTimeout(resolve, 750));
    }

    setError("Unable to load final report.");
    setIsRunning(false);
    setIsFetchingResult(false);
  };

  const startEventStream = (id) => {
    const eventSource = createEventSource(id);

    eventSource.onmessage = (event) => {
      let update;
      try {
        update = JSON.parse(event.data);
      } catch (e) {
        return;
      }
      setAgentLogs((prev) => [...prev, update]);

      if (update.status === "complete" && update.agent === "System") {
        eventSource.close();
        fetchFinalResult(id);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      if (id) {
        fetchFinalResult(id);
      } else {
        setIsRunning(false);
        setError("Stream connection lost. Please retry.");
      }
    };
  };

  useEffect(() => {
    if (!sessionId || !isRunning || isFetchingResult || finalResult) {
      return undefined;
    }

    const intervalId = setInterval(async () => {
      try {
        const gates = await fetchPendingApprovals(sessionId);
        if (gates.length > 0) {
          setPendingApproval((current) => current || gates[0]);
        } else {
          setPendingApproval(null);
        }
      } catch (err) {
        // ignore polling errors
      }
    }, 2000);

    return () => clearInterval(intervalId);
  }, [sessionId, isRunning, isFetchingResult, finalResult]);

  const handleApprovalResponse = async (gateId, approved, modificationsText) => {
    const modifications = modificationsText?.trim()
      ? { notes: modificationsText.trim() }
      : {};
    try {
      await respondToApproval(gateId, approved, modifications);
      setPendingApproval(null);
    } catch (err) {
      setError("Failed to respond to approval. Please retry.");
    }
  };

  const handleGoalSubmit = async (payload) => {
    setIsRunning(true);
    setAgentLogs([]);
    setFinalResult(null);
    setError("");
    setSessionId(null);
    setPendingApproval(null);

    try {
      const response = await executeGoal(payload);
      setSessionId(response.session_id);
      startEventStream(response.session_id);
    } catch (err) {
      setError("Failed to start workflow. Please try again.");
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 text-white">
      <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-12">
          <h1 className="text-5xl font-bold mb-2">ManagerGPT</h1>
          <p className="text-slate-400">Autonomous AI Workforce</p>
        </header>

        {!sessionId && <GoalInput onSubmit={handleGoalSubmit} />}

        {sessionId && (
          <>
            {!finalResult && <AgentDashboard logs={agentLogs} isRunning={isRunning} />}
            {finalResult && <FinalReport result={finalResult} />}
          </>
        )}

        {pendingApproval && (
          <ApprovalGate gate={pendingApproval} onRespond={handleApprovalResponse} />
        )}

        {error && (
          <div className="mt-6 text-center text-red-400">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
