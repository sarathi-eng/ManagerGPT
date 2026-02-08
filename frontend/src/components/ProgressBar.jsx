export default function ProgressBar({ estimatedTime, elapsedTime }) {
  if (!estimatedTime) {
    return null;
  }

  const progress = Math.min((elapsedTime / estimatedTime) * 100, 100);
  const remaining = Math.max(estimatedTime - elapsedTime, 0);

  return (
    <div className="mb-4">
      <div className="flex justify-between text-sm mb-2">
        <span>Processing...</span>
        <span className="text-slate-400">~{remaining}s remaining</span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
