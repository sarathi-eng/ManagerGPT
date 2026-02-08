const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001";

export const executeGoal = async (payload) => {
  const response = await fetch(`${API_BASE}/api/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Failed to start workflow");
  }
  return response.json();
};

export const fetchSession = async (sessionId) => {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch session");
  }
  return response.json();
};

export const createEventSource = (sessionId) =>
  new EventSource(`${API_BASE}/api/stream/${sessionId}`);

export const fetchPendingApprovals = async (sessionId) => {
  const response = await fetch(`${API_BASE}/api/approvals/${sessionId}/pending`);
  if (!response.ok) {
    throw new Error("Failed to fetch approvals");
  }
  return response.json();
};

export const respondToApproval = async (gateId, approved, modifications) => {
  const response = await fetch(`${API_BASE}/api/approvals/${gateId}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved, modifications }),
  });
  if (!response.ok) {
    throw new Error("Failed to respond to approval");
  }
  return response.json();
};

export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Failed to upload document");
  }

  return response.json();
};

export const createShareLink = async (sessionId) => {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/share`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Failed to create share link");
  }
  return response.json();
};
