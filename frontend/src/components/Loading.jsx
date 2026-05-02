import { Activity, Check } from "lucide-react";

const PIPELINE_STEPS = [
  {
    label: "NLP Extraction",
    desc: "Analyzing symptoms, condition candidates & location…",
  },
  {
    label: "Clinical Pathway Mapping",
    desc: "Searching HBP 2022 procedure database via RAG…",
  },
  {
    label: "Cost Estimation",
    desc: "Applying city-tier rates and HBP stacking rules…",
  },
  {
    label: "Provider Matching",
    desc: "Ranking hospitals by specialty, rating & distance…",
  },
];

export default function Loading({
  activeStep = 0,
  completedSteps = new Set(),
}) {
  const doneCount = completedSteps.size;
  const isRunning =
    activeStep >= 0 &&
    activeStep < PIPELINE_STEPS.length &&
    !completedSteps.has(activeStep);
  const progress = Math.min(
    Math.round((doneCount / PIPELINE_STEPS.length) * 100 + (isRunning ? 5 : 0)),
    100,
  );

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-8 px-4"
      style={{ background: "#070B14" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
          <Activity size={17} className="text-white" />
        </div>
        <span className="text-white font-bold text-[17px] tracking-tight">
          HealthNav
        </span>
      </div>

      {/* Title */}
      <div className="text-center">
        <p className="text-white font-bold text-xl mb-1">
          Analyzing your query
        </p>
        <p className="text-slate-500 text-sm">Running 4-layer AI pipeline</p>
      </div>

      {/* Overall progress bar */}
      <div className="w-full max-w-[400px]">
        <div className="flex justify-between text-[11px] text-slate-500 mb-2">
          <span>Progress</span>
          <span>{progress}%</span>
        </div>
        <div
          className="h-1.5 rounded-full overflow-hidden"
          style={{ background: "#1E2D45" }}
        >
          <div
            className="h-full rounded-full bg-blue-500 transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Step list */}
      <div className="w-full max-w-[400px] space-y-2">
        {PIPELINE_STEPS.map((step, i) => {
          const isDone = completedSteps.has(i);
          const isActive = activeStep === i && !isDone;
          const isWaiting = !isDone && !isActive;

          return (
            <div
              key={i}
              className="flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all duration-300"
              style={{
                background: isDone
                  ? "#0A1A0F"
                  : isActive
                    ? "#0D1A2E"
                    : "#0D1525",
                border: `1px solid ${isDone ? "#166534" : isActive ? "#1D4ED8" : "#1E2D45"}`,
                opacity: isWaiting ? 0.4 : 1,
              }}
            >
              {/* Status icon */}
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                  isDone
                    ? "bg-green-900 border border-green-700"
                    : isActive
                      ? "bg-blue-900 border border-blue-700"
                      : "bg-[#111C30] border border-[#1E2D45]"
                }`}
              >
                {isDone ? (
                  <Check size={12} className="text-green-400" />
                ) : isActive ? (
                  <div className="w-2.5 h-2.5 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-600" />
                )}
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p
                  className={`text-[13px] font-semibold leading-tight ${
                    isDone
                      ? "text-green-300"
                      : isActive
                        ? "text-white"
                        : "text-slate-500"
                  }`}
                >
                  {step.label}
                </p>
                {isActive && (
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {step.desc}
                  </p>
                )}
              </div>

              {/* Status badge */}
              {isDone && (
                <span className="text-[10px] text-green-500 font-semibold shrink-0">
                  done
                </span>
              )}
              {isActive && (
                <span className="text-[10px] text-blue-400 font-semibold animate-pulse shrink-0">
                  running
                </span>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-slate-600">
        This usually takes 45–60 seconds
      </p>
    </div>
  );
}
