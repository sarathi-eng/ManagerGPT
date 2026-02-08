import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Copy,
  Download,
  Share2,
  ThumbsUp,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { createShareLink } from "../utils/api.js";
import AdoptionThreshold from "./AdoptionThreshold.jsx";
import BreakEvenCard from "./BreakEvenCard.jsx";
import ComparableCases from "./ComparableCases.jsx";
import CustomerSegments from "./CustomerSegments.jsx";
import DecisionCard from "./DecisionCard.jsx";
import DecisionDefensePanel from "./DecisionDefensePanel.jsx";
import ExecutiveNarrative from "./ExecutiveNarrative.jsx";
import FailureSignals from "./FailureSignals.jsx";
import LaunchStrategy from "./LaunchStrategy.jsx";
import PivotSuggestions from "./PivotSuggestions.jsx";
import PricingFeasibility from "./PricingFeasibility.jsx";
import UnitEconomics from "./UnitEconomics.jsx";

export default function FinalReport({ result }) {
  const pros = Array.isArray(result.pros) ? result.pros : [];
  const cons = Array.isArray(result.cons) ? result.cons : [];
  const sustainability = result.sustainability || {};
  const sustainabilityScore = Number(sustainability.score || 0);
  const sustainabilityLabel = sustainability.long_term_viability || "MEDIUM";
  const sustainabilityReasoning =
    sustainability.reasoning || "No additional sustainability notes.";
  const investment = result.investment || {};
  const investmentMin = Number(investment.min || 0);
  const investmentMax = Number(investment.max || 0);
  const investmentBreakdown =
    investment.breakdown && typeof investment.breakdown === "object"
      ? investment.breakdown
      : {};
  const competitors = Array.isArray(result.competitors) ? result.competitors : [];
  const vendors = Array.isArray(result.vendors) ? result.vendors : [];
  const hallucinationWarnings = Array.isArray(result.hallucination_warnings)
    ? result.hallucination_warnings
    : [];
  const businessMetrics = result.business_metrics || null;
  const strategy =
    result.strategy ||
    result.business_strategy ||
    (businessMetrics
      ? {
          breakeven: {
            months_min: businessMetrics.breakeven_months_min,
            months_max: businessMetrics.breakeven_months_max,
            key_driver: businessMetrics.breakeven_key_driver,
            assumptions: businessMetrics.breakeven_assumptions || [],
          },
          customer_segments: {
            primary: {
              segment: businessMetrics.primary_segment,
              size: businessMetrics.primary_segment_size,
              fit_score: 0,
              reasoning: businessMetrics.segment_reasoning || "",
            },
            secondary: {
              segment: businessMetrics.secondary_segment,
              size: "",
              fit_score: 0,
              reasoning: "",
            },
            poor_fit: businessMetrics.poor_fit_segments || [],
          },
          pricing: {
            optimal_min: businessMetrics.optimal_price_min,
            optimal_max: businessMetrics.optimal_price_max,
            sensitivity: businessMetrics.pricing_sensitivity,
            price_points: businessMetrics.price_points || {},
            reasoning: "",
          },
          adoption_threshold: {
            minimum_adoption_pct: businessMetrics.minimum_adoption_pct,
            failure_threshold_pct: businessMetrics.failure_threshold_pct,
            kpi: businessMetrics.adoption_kpi_description,
            measurement_period_days: businessMetrics.pivot_threshold_days || 30,
            reasoning: "",
          },
          unit_economics: {
            cost_per_unit: businessMetrics.cost_per_unit,
            revenue_per_unit: businessMetrics.revenue_per_unit,
            gross_margin_pct: businessMetrics.gross_margin_pct,
            health: businessMetrics.unit_economics_health,
            margin_buffer: businessMetrics.margin_buffer,
            breakdown: {},
            notes: "",
          },
          launch_strategy: {
            approach: businessMetrics.launch_approach,
            steps: businessMetrics.launch_steps || [],
            total_timeline_days: businessMetrics.timeline_days,
            reasoning: "",
          },
          failure_signals: businessMetrics.early_failure_signals || [],
          comparable_cases: businessMetrics.comparable_businesses || [],
          pivot_suggestions: businessMetrics.pivot_suggestions || [],
        }
      : null);
  const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8001";
  const [shareUrl, setShareUrl] = useState("");
  const [shareError, setShareError] = useState("");

  const getVendorRiskLevel = (vendor) => {
    const importance = String(vendor?.importance || "").toUpperCase();
    const switching = String(vendor?.switching_cost || "").toUpperCase();
    const disadvantageCount = Array.isArray(vendor?.disadvantages)
      ? vendor.disadvantages.length
      : 0;
    let score = 0;
    if (importance === "CRITICAL") score += 2;
    if (importance === "IMPORTANT") score += 1;
    if (switching === "HIGH") score += 2;
    if (switching === "MEDIUM") score += 1;
    if (disadvantageCount >= 3) score += 1;

    if (score >= 4) return "HIGH";
    if (score >= 2) return "MEDIUM";
    return "LOW";
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur rounded-xl p-8 border border-slate-700 animate-fadeIn">
      <div className="space-y-6">
        <ExecutiveNarrative
          narrative={result.executive_narrative || result.executive_summary}
          recommendation={result.final_decision || result.recommendation}
        />

        <DecisionCard
          result={result}
          sourceMap={result.source_map || {}}
        />

        <DecisionDefensePanel
          recommendation={result.final_decision || result.recommendation}
          defenses={result.decision_defense}
        />

        {hallucinationWarnings.length > 0 && (
          <div className="bg-yellow-900/20 border border-yellow-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="text-yellow-400" size={20} />
              <h4 className="font-semibold">Evidence Quality Warnings</h4>
            </div>
            <ul className="space-y-2 text-sm">
              {hallucinationWarnings.map((warning, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${
                      warning.severity === "HIGH"
                        ? "bg-red-900/40 text-red-400"
                        : "bg-yellow-900/40 text-yellow-400"
                    }`}
                  >
                    {warning.severity || "MEDIUM"}
                  </span>
                  <span className="flex-1">
                    <strong>{warning.claim}</strong> - {warning.issue}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {strategy && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <BreakEvenCard breakeven={strategy.breakeven} />
              <AdoptionThreshold adoption={strategy.adoption_threshold} />
            </div>

            <CustomerSegments segments={strategy.customer_segments} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PricingFeasibility pricing={strategy.pricing} />
              <UnitEconomics economics={strategy.unit_economics} />
            </div>

            <LaunchStrategy launch={strategy.launch_strategy} />

            <FailureSignals signals={strategy.failure_signals} />

            <ComparableCases cases={strategy.comparable_cases} />

            {(result.final_decision === "STOP" || result.final_decision === "INVESTIGATE") && (
              <PivotSuggestions pivots={strategy.pivot_suggestions} />
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-green-900/20 border border-green-700 rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <ThumbsUp className="text-green-400" size={20} />
              Pros
            </h3>
            {pros.length > 0 ? (
              <ul className="space-y-2">
                {pros.map((pro, idx) => (
                  <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                    <CheckCircle
                      className="text-green-400 flex-shrink-0 mt-0.5"
                      size={16}
                    />
                    <span>{pro}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-400">No pros listed.</p>
            )}
          </div>

          <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <AlertTriangle className="text-red-400" size={20} />
              Cons
            </h3>
            {cons.length > 0 ? (
              <ul className="space-y-2">
                {cons.map((con, idx) => (
                  <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                    <XCircle className="text-red-400 flex-shrink-0 mt-0.5" size={16} />
                    <span>{con}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-400">No cons listed.</p>
            )}
          </div>
        </div>

        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <h3 className="text-lg font-semibold mb-3">Long-Term Sustainability</h3>
          <div className="flex flex-col lg:flex-row items-start lg:items-center gap-4 mb-3">
            <div className="flex-1 w-full">
              <div className="flex justify-between mb-2">
                <span className="text-sm text-slate-400">Sustainability Score</span>
                <span className="font-semibold">
                  {(sustainabilityScore * 100).toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full"
                  style={{ width: `${sustainabilityScore * 100}%` }}
                />
              </div>
            </div>
            <div
              className={`px-4 py-2 rounded-lg font-semibold ${
                sustainabilityLabel === "HIGH"
                  ? "bg-green-900/40 text-green-400"
                  : sustainabilityLabel === "MEDIUM"
                  ? "bg-yellow-900/40 text-yellow-400"
                  : "bg-red-900/40 text-red-400"
              }`}
            >
              {sustainabilityLabel}
            </div>
          </div>
          <p className="text-sm text-slate-300">{sustainabilityReasoning}</p>
        </div>

        {(investmentMin > 0 || investmentMax > 0) && (
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <h3 className="text-lg font-semibold mb-3">Initial Investment</h3>
            <div className="flex items-center gap-4 mb-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-400">
                  ${(investmentMin / 1000).toFixed(0)}K
                </div>
                <div className="text-xs text-slate-400">Minimum</div>
              </div>
              <div className="flex-1 h-px bg-slate-600" />
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-400">
                  ${(investmentMax / 1000).toFixed(0)}K
                </div>
                <div className="text-xs text-slate-400">Maximum</div>
              </div>
            </div>

            {Object.keys(investmentBreakdown).length > 0 && investmentMax > 0 && (
              <div className="space-y-2">
                {Object.entries(investmentBreakdown).map(([category, amount]) => (
                  <div key={category} className="flex items-center gap-2">
                    <span className="text-sm text-slate-400 w-24">{category}</span>
                    <div className="flex-1 bg-slate-700 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full"
                        style={{ width: `${(Number(amount) / investmentMax) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold w-20 text-right">
                      ${(Number(amount) / 1000).toFixed(1)}K
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <h3 className="text-lg font-semibold mb-3">Competitive Landscape</h3>
          {competitors.length === 0 ? (
            <div className="p-4 bg-blue-900/20 border-l-4 border-blue-500 rounded">
              <p className="text-sm text-slate-300">
                Competitive analysis will vary by specific market segment and geography. General
                competitive categories include established providers, emerging startups, and DIY
                alternatives. For detailed competitor analysis, specify company names in advanced
                options.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {competitors.map((comp, idx) => (
                <div key={idx} className="bg-slate-900/50 rounded-lg p-4 border-l-4 border-purple-500">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-semibold text-lg">{comp.competitor_name}</h4>
                    {comp.market_position && (
                      <span className="text-xs px-3 py-1 bg-purple-900/40 text-purple-400 rounded-full">
                        {comp.market_position}
                      </span>
                    )}
                  </div>

                  {comp.market_share && comp.market_share !== "Unknown" && (
                    <div className="text-sm text-slate-400 mb-3">
                      Market Share: {comp.market_share}
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <div className="text-green-400 font-medium mb-2 flex items-center gap-2">
                        <CheckCircle size={16} />
                        Strengths
                      </div>
                      <ul className="space-y-1 text-slate-400">
                        {(comp.strengths || []).slice(0, 4).map((strength, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-green-400 mt-0.5">•</span>
                            <span>{strength}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div>
                      <div className="text-red-400 font-medium mb-2 flex items-center gap-2">
                        <XCircle size={16} />
                        Weaknesses
                      </div>
                      <ul className="space-y-1 text-slate-400">
                        {(comp.weaknesses || []).slice(0, 4).map((weakness, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-red-400 mt-0.5">•</span>
                            <span>{weakness}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {competitors.some(
            (comp) =>
              String(comp.competitor_name || "").includes("Established") ||
              String(comp.competitor_name || "").includes("Emerging")
          ) && (
            <div className="mt-4 p-3 bg-blue-900/20 border-l-4 border-blue-500 rounded text-sm text-slate-400">
              <AlertCircle className="inline mr-2" size={14} />
              Showing general competitive categories. For specific company analysis, provide
              competitor names in advanced options.
            </div>
          )}
        </div>

        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <h3 className="text-lg font-semibold mb-3">Key Vendors & Suppliers</h3>
          {vendors.length > 0 ? (
            <div className="space-y-3">
              {vendors.map((vendor, idx) => {
                const riskLevel = getVendorRiskLevel(vendor);
                return (
                  <div key={idx} className="border-l-4 border-orange-500 pl-4 py-2">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <h4 className="font-semibold">{vendor.vendor_name}</h4>
                      <div className="flex items-center gap-2">
                        {vendor.vendor_type && (
                          <span className="text-xs px-2 py-1 bg-orange-900/40 text-orange-400 rounded">
                            {vendor.vendor_type}
                          </span>
                        )}
                        {vendor.importance && (
                          <span
                            className={`text-xs px-2 py-1 rounded ${
                              vendor.importance === "CRITICAL"
                                ? "bg-red-900/40 text-red-400"
                                : vendor.importance === "IMPORTANT"
                                ? "bg-yellow-900/40 text-yellow-400"
                                : "bg-slate-700 text-slate-400"
                            }`}
                          >
                            {vendor.importance}
                          </span>
                        )}
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            riskLevel === "HIGH"
                              ? "bg-red-900/40 text-red-400"
                              : riskLevel === "MEDIUM"
                              ? "bg-yellow-900/40 text-yellow-400"
                              : "bg-green-900/40 text-green-400"
                          }`}
                        >
                          Risk: {riskLevel}
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-sm">
                      <div>
                        <div className="text-green-400 font-medium mb-1">Advantages:</div>
                        <ul className="text-slate-400 space-y-1">
                          {(vendor.advantages || []).slice(0, 2).map((adv, i) => (
                            <li key={i}>• {adv}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <div className="text-red-400 font-medium mb-1">Risks:</div>
                        <ul className="text-slate-400 space-y-1">
                          {(vendor.disadvantages || []).slice(0, 2).map((risk, i) => (
                            <li key={i}>• {risk}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No vendor analysis available.</p>
          )}
        </div>

        {result.sources && result.sources.length > 0 && (
          <div>
            <h3 className="text-xl font-semibold mb-3">Sources</h3>
            <ul className="space-y-2">
              {result.sources.map((source, idx) => (
                <li key={idx}>
                  <a
                    href={source}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 underline text-sm"
                  >
                    {source}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-col gap-3">
          <button
            onClick={async () => {
              try {
                const response = await createShareLink(result.session_id);
                setShareUrl(response.share_url || "");
                setShareError("");
              } catch (err) {
                setShareError("Failed to create share link.");
              }
            }}
            className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg flex items-center justify-center gap-2"
          >
            <Share2 size={16} />
            Share Report
          </button>
          {shareUrl && (
            <div className="p-3 bg-slate-800 rounded-lg">
              <div className="text-sm text-slate-400 mb-1">Share this link:</div>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={shareUrl}
                  className="flex-1 bg-slate-900 px-3 py-2 rounded text-sm"
                />
                <button
                  onClick={() => navigator.clipboard.writeText(shareUrl)}
                  className="text-slate-300 hover:text-white"
                >
                  <Copy size={16} />
                </button>
              </div>
            </div>
          )}
          {shareError && <div className="text-sm text-red-400">{shareError}</div>}
          <button
            onClick={() => window.open(`${apiBase}/api/session/${result.session_id}/export/pdf`)}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg flex items-center justify-center gap-2"
          >
            <Download size={16} />
            Export PDF Report
          </button>
          <button
            onClick={() => window.location.reload()}
            className="w-full bg-slate-700 hover:bg-slate-600 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
          >
            Start New Analysis
          </button>
        </div>
      </div>
    </div>
  );
}
