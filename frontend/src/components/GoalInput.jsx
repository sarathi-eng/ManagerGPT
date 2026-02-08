import { useState } from "react";
import FileUpload from "./FileUpload.jsx";

const examples = [
  "Should I launch an AI tutoring app for high schoolers?",
  "Is now a good time to start a coffee roasting business?",
  "Should I expand my SaaS product to enterprise customers?",
];

export default function GoalInput({ onSubmit }) {
  const [goal, setGoal] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [vendors, setVendors] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [documentIds, setDocumentIds] = useState([]);
  const [executionMode, setExecutionMode] = useState("strict");
  const [maxResearchDepth, setMaxResearchDepth] = useState("deep");
  const [maxRuntime, setMaxRuntime] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = () => {
    if (goal.trim().length < 10) {
      setError("Please provide more details about your goal");
      return;
    }
    setError("");
    onSubmit({
      goal: goal.trim(),
      business_name: businessName.trim() || null,
      competitor_names: competitors
        ? competitors
            .split(",")
            .map((name) => name.trim())
            .filter(Boolean)
        : [],
      vendor_names: vendors
        ? vendors
            .split(",")
            .map((name) => name.trim())
            .filter(Boolean)
        : [],
      document_ids: documentIds,
      execution_mode: executionMode,
      max_research_depth: maxResearchDepth,
      max_runtime: maxRuntime ? Number(maxRuntime) : null,
    });
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur rounded-xl p-8 border border-slate-700 shadow-lg shadow-blue-500/10">
      <h2 className="text-2xl font-semibold mb-4">Business Analysis</h2>

      <textarea
        className="w-full bg-slate-900 border border-slate-600 rounded-lg p-4 text-white placeholder-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 outline-none min-h-[120px] resize-none"
        placeholder="What business decision do you need help with?"
        value={goal}
        onChange={(event) => setGoal(event.target.value)}
      />

      <div className="mb-4 mt-4">
        <label className="block text-sm font-medium mb-2">Execution Mode</label>
        <div className="grid grid-cols-3 gap-2">
          {["fast", "balanced", "strict"].map((mode) => (
            <button
              key={mode}
              type="button"
              className={`p-3 rounded-lg border ${
                executionMode === mode
                  ? "border-blue-500 bg-blue-500/20"
                  : "border-slate-600 bg-slate-800"
              }`}
              onClick={() => setExecutionMode(mode)}
            >
              <div className="font-semibold capitalize">{mode}</div>
              <div className="text-xs text-slate-400">
                {mode === "fast" && "Minimal validation"}
                {mode === "balanced" && "Normal checks"}
                {mode === "strict" && "Heavy verification"}
              </div>
            </button>
          ))}
        </div>
      </div>

      <FileUpload
        onFilesUploaded={(ids) =>
          setDocumentIds((prev) => [...prev, ...ids.filter((id) => !prev.includes(id))])
        }
      />

      <button
        type="button"
        className="mt-3 text-blue-400 hover:text-blue-300 text-sm"
        onClick={() => setShowAdvanced((current) => !current)}
      >
        {showAdvanced ? "− Hide" : "+ Show"} Advanced Options
      </button>

      {showAdvanced && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="text-sm text-slate-300">Max Research Depth</label>
              <select
                className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-slate-200"
                value={maxResearchDepth}
                onChange={(event) => setMaxResearchDepth(event.target.value)}
              >
                <option value="basic">Basic (5 sources)</option>
                <option value="standard">Standard (10 sources)</option>
                <option value="deep">Deep (20+ sources)</option>
              </select>
            </div>

            <div>
              <label className="text-sm text-slate-300">Max Runtime</label>
              <select
                className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-slate-200"
                value={maxRuntime}
                onChange={(event) => setMaxRuntime(event.target.value)}
              >
                <option value="">No limit</option>
                <option value="60">1 minute</option>
                <option value="120">2 minutes</option>
                <option value="300">5 minutes</option>
              </select>
            </div>
          </div>
          <input
            type="text"
            className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white placeholder-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 outline-none"
            placeholder="Existing business name (optional)"
            value={businessName}
            onChange={(event) => setBusinessName(event.target.value)}
          />

          <input
            type="text"
            className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white placeholder-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 outline-none"
            placeholder="Competitors (comma-separated, optional)"
            value={competitors}
            onChange={(event) => setCompetitors(event.target.value)}
          />

          <input
            type="text"
            className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white placeholder-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 outline-none"
            placeholder="Key vendors/suppliers (comma-separated, optional)"
            value={vendors}
            onChange={(event) => setVendors(event.target.value)}
          />
        </div>
      )}

      <div className="flex items-center justify-between mt-2 text-sm text-slate-400">
        <span>{goal.trim().length} / 10</span>
        {error && <span className="text-red-400">{error}</span>}
      </div>

      <button
        className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:bg-slate-600 disabled:cursor-not-allowed"
        onClick={handleSubmit}
        disabled={!goal.trim()}
      >
        Analyze Business
      </button>

      <div className="mt-6">
        <p className="text-sm text-slate-400 mb-3">Try an example:</p>
        <div className="flex flex-wrap gap-2">
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              className="text-sm px-3 py-1 rounded-full border border-slate-600 text-slate-300 hover:text-white hover:border-blue-400 transition"
              onClick={() => setGoal(example)}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
