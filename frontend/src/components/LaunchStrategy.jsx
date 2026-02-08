import { Rocket } from "lucide-react";

export default function LaunchStrategy({ launch }) {
  if (!launch) {
    return null;
  }

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Rocket className="text-orange-400" size={24} />
        Launch Strategy
        <span className="ml-auto px-3 py-1 bg-orange-900/40 text-orange-400 rounded-full text-sm">
          {launch.approach} Approach
        </span>
      </h3>

      <div className="mb-4 text-center">
        <div className="text-3xl font-bold text-orange-400">
          {launch.total_timeline_days} days
        </div>
        <div className="text-sm text-slate-400">Total Timeline</div>
      </div>

      <div className="relative">
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-slate-700" />

        <div className="space-y-6">
          {launch.steps.map((step, idx) => (
            <div key={idx} className="relative pl-14">
              <div className="absolute left-0 w-12 h-12 bg-orange-500 rounded-full flex items-center justify-center font-bold text-white border-4 border-slate-800">
                {step.step}
              </div>

              <div className="bg-slate-900/50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold text-slate-200">{step.action}</div>
                  <div className="text-sm text-orange-400">{step.timeline_days} days</div>
                </div>

                <div className="text-sm text-slate-400">
                  <span className="font-medium">Success: </span>
                  {step.success_criteria}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 p-4 bg-orange-900/20 border-l-4 border-orange-500 rounded">
        <div className="text-sm text-slate-300">{launch.reasoning}</div>
      </div>
    </div>
  );
}
