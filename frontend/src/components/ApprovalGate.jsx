import { useState } from "react";
import { AlertCircle } from "lucide-react";

export default function ApprovalGate({ gate, onRespond }) {
  const [modifications, setModifications] = useState("");

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-xl p-6 max-w-lg w-full border-2 border-yellow-500">
        <div className="flex items-center gap-3 mb-4">
          <AlertCircle className="text-yellow-400" size={32} />
          <h3 className="text-xl font-bold">Approval Required</h3>
        </div>

        <div className="bg-slate-900 rounded-lg p-4 mb-4">
          <p className="text-slate-300 whitespace-pre-line">{gate.description}</p>
        </div>

        <textarea
          className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 mb-4 text-slate-200"
          placeholder="Optional: Add instructions or modifications..."
          value={modifications}
          onChange={(event) => setModifications(event.target.value)}
          rows={3}
        />

        <div className="flex gap-3">
          <button
            className="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-lg"
            onClick={() => onRespond(gate.id, true, modifications)}
          >
            ✓ Approve & Continue
          </button>
          <button
            className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-lg"
            onClick={() => onRespond(gate.id, false, modifications)}
          >
            ✗ Reject
          </button>
        </div>
      </div>
    </div>
  );
}
