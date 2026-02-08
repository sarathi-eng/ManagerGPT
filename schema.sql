-- File: schema.sql
-- Purpose: Store task execution state and agent interactions

-- Main execution sessions
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_goal TEXT NOT NULL,
    status TEXT DEFAULT 'running', -- running, completed, failed
    final_decision TEXT,
    decision_narrative TEXT,
    confidence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Individual tasks created by Planner
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    task_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, in_progress, completed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Research findings from Researcher agent
CREATE TABLE IF NOT EXISTS research_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    findings TEXT NOT NULL,
    sources TEXT, -- JSON array of URLs
    source_map TEXT, -- JSON map of claim -> source URL
    metadata TEXT, -- JSON metadata for quality filtering
    confidence REAL,
    attempt_number INTEGER DEFAULT 1, -- for retries
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Analysis results from Analyst agent
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    recommendation TEXT, -- PROCEED, STOP, INVESTIGATE
    reasoning TEXT NOT NULL,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Critique feedback from Critic agent
CREATE TABLE IF NOT EXISTS critiques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    approved BOOLEAN NOT NULL,
    issues TEXT, -- JSON array of issue descriptions
    confidence_adjustment REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(id)
);

-- Real-time agent activity log (for dashboard streaming)
CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    agent_name TEXT NOT NULL, -- Planner, Researcher, Analyst, Critic
    message TEXT NOT NULL,
    status TEXT, -- working, complete, rejected, error
    metadata TEXT, -- JSON for additional context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Enhanced business analysis results
CREATE TABLE IF NOT EXISTS business_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,

    -- Business Classification
    business_type TEXT, -- B2B, B2C, B2B2C, Marketplace, SaaS, etc.
    business_model TEXT, -- Subscription, One-time, Freemium, etc.
    target_customer TEXT, -- Who is the customer
    customer_pain_points TEXT, -- JSON array

    -- Pros & Cons
    pros TEXT, -- JSON array
    cons TEXT, -- JSON array

    -- Sustainability
    sustainability_score REAL, -- 0-1
    sustainability_factors TEXT, -- JSON array
    long_term_viability TEXT, -- HIGH, MEDIUM, LOW

    -- Investment
    initial_investment_min REAL,
    initial_investment_max REAL,
    investment_breakdown TEXT, -- JSON object

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Decision defense summaries
CREATE TABLE IF NOT EXISTS decision_defenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    recommendation TEXT NOT NULL,
    why_not_stop TEXT,
    why_not_investigate TEXT,
    why_not_proceed TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Competitor analysis
CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,

    competitor_name TEXT NOT NULL,
    market_position TEXT, -- Leader, Challenger, Follower, Niche
    market_share TEXT, -- Estimated percentage or range
    strengths TEXT, -- JSON array
    weaknesses TEXT, -- JSON array

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Vendor/Supplier analysis
CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,

    vendor_name TEXT NOT NULL,
    vendor_type TEXT, -- Technology, Manufacturing, Distribution, etc.
    importance TEXT, -- CRITICAL, IMPORTANT, OPTIONAL
    advantages TEXT, -- JSON array
    disadvantages TEXT, -- JSON array
    alternatives_available BOOLEAN,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Uploaded documents
CREATE TABLE IF NOT EXISTS uploaded_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    content TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shared report links
CREATE TABLE IF NOT EXISTS shared_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    share_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_shared_reports_token ON shared_reports(share_token);

-- Enhanced business metrics
CREATE TABLE IF NOT EXISTS business_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,

    -- Break-even Analysis
    breakeven_months_min INTEGER,
    breakeven_months_max INTEGER,
    breakeven_key_driver TEXT,
    breakeven_assumptions TEXT, -- JSON

    -- Customer Segmentation
    primary_segment TEXT,
    primary_segment_size TEXT,
    secondary_segment TEXT,
    poor_fit_segments TEXT, -- JSON array
    segment_reasoning TEXT,

    -- Pricing Analysis
    optimal_price_min REAL,
    optimal_price_max REAL,
    pricing_sensitivity TEXT, -- HIGH, MEDIUM, LOW
    price_points TEXT, -- JSON: {"price": viability}

    -- Adoption Metrics
    minimum_adoption_pct REAL,
    failure_threshold_pct REAL,
    adoption_kpi_description TEXT,

    -- Unit Economics
    cost_per_unit REAL,
    revenue_per_unit REAL,
    gross_margin_pct REAL,
    unit_economics_health TEXT, -- STRONG, ACCEPTABLE, WEAK
    margin_buffer TEXT, -- HIGH, MEDIUM, LOW

    -- Launch Strategy
    launch_approach TEXT, -- Focused, Gradual, Broad
    launch_steps TEXT, -- JSON array
    timeline_days INTEGER,

    -- Failure Signals
    early_failure_signals TEXT, -- JSON array
    pivot_threshold_days INTEGER,

    -- Comparable Cases
    comparable_businesses TEXT, -- JSON array

    -- Resource Requirements
    operational_complexity TEXT, -- HIGH, MEDIUM, LOW
    time_commitment TEXT, -- HIGH, MEDIUM, LOW
    automation_potential TEXT, -- HIGH, MEDIUM, LOW
    critical_skills TEXT, -- JSON array

    -- Pivot Options (if STOP recommendation)
    pivot_suggestions TEXT, -- JSON array

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_business_metrics_session ON business_metrics(session_id);

-- Hallucination warnings
CREATE TABLE IF NOT EXISTS hallucination_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    claim TEXT NOT NULL,
    issue TEXT NOT NULL,
    severity TEXT NOT NULL, -- LOW, MEDIUM, HIGH
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Risk assessment
CREATE TABLE IF NOT EXISTS risk_assessment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,

    risk_category TEXT, -- Market, Financial, Operational, Legal, etc.
    risk_level TEXT, -- HIGH, MEDIUM, LOW
    risk_description TEXT,
    mitigation_strategy TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_research_task ON research_findings(task_id);
CREATE INDEX IF NOT EXISTS idx_analysis_session ON analysis_results(session_id);
CREATE INDEX IF NOT EXISTS idx_logs_session ON agent_logs(session_id);

CREATE INDEX IF NOT EXISTS idx_business_analysis_session ON business_analysis(session_id);
CREATE INDEX IF NOT EXISTS idx_competitors_session ON competitors(session_id);
CREATE INDEX IF NOT EXISTS idx_vendors_session ON vendors(session_id);
CREATE INDEX IF NOT EXISTS idx_risks_session ON risk_assessment(session_id);

-- Approval gates for user confirmations
CREATE TABLE IF NOT EXISTS approval_gates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    gate_type TEXT NOT NULL, -- research_plan, competitor_analysis, final_decision
    description TEXT NOT NULL,
    requires_approval BOOLEAN DEFAULT TRUE,
    approved BOOLEAN DEFAULT NULL, -- NULL = pending, TRUE = approved, FALSE = rejected
    user_modifications TEXT, -- JSON of user changes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_approval_gates_session ON approval_gates(session_id);
