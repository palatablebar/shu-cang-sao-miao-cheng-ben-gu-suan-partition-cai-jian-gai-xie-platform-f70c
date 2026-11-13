-- partfit / PostgreSQL 16 initial schema (generated from src/models via SQLAlchemy)
-- Applied automatically at runtime by src.config.database.init_db(); kept here as the
-- reviewable DDL snapshot for DBAs who want to pre-create the schema by hand.

CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	display_name VARCHAR(80) NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	team VARCHAR(80) NOT NULL, 
	password_hash VARCHAR(200) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE table_meta (
	id SERIAL NOT NULL, 
	schema_name VARCHAR(64) NOT NULL, 
	table_name VARCHAR(96) NOT NULL, 
	layer VARCHAR(8) NOT NULL, 
	storage_format VARCHAR(24) NOT NULL, 
	partition_key VARCHAR(32) NOT NULL, 
	partition_type VARCHAR(16) NOT NULL, 
	partition_count INTEGER NOT NULL, 
	row_count BIGINT NOT NULL, 
	total_bytes BIGINT NOT NULL, 
	data_column_count INTEGER NOT NULL, 
	owner VARCHAR(80) NOT NULL, 
	description TEXT NOT NULL, 
	suggested_columns JSONB NOT NULL, 
	last_analyzed_dt VARCHAR(16), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_table_meta_table_name ON table_meta (table_name);

CREATE TABLE budget_policy (
	id SERIAL NOT NULL, 
	policy_no VARCHAR(32) NOT NULL, 
	name VARCHAR(96) NOT NULL, 
	scope VARCHAR(16) NOT NULL, 
	scope_value VARCHAR(96), 
	monthly_budget_cny FLOAT NOT NULL, 
	unit_cost_per_gib_cny FLOAT NOT NULL, 
	warn_ratio FLOAT NOT NULL, 
	critical_ratio FLOAT NOT NULL, 
	scan_alert_bytes BIGINT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	note TEXT NOT NULL, 
	updated_by VARCHAR(80), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_budget_policy_policy_no ON budget_policy (policy_no);

CREATE TABLE query_log (
	id SERIAL NOT NULL, 
	external_id VARCHAR(32) NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	sql_text TEXT NOT NULL, 
	source VARCHAR(48) NOT NULL, 
	submitted_by VARCHAR(80) NOT NULL, 
	query_date VARCHAR(16) NOT NULL, 
	duration_ms INTEGER NOT NULL, 
	is_scheduled BOOLEAN NOT NULL, 
	parse_status VARCHAR(24) NOT NULL, 
	parse_error TEXT, 
	target_table VARCHAR(96), 
	prunable BOOLEAN NOT NULL, 
	blocked_reason VARCHAR(32) NOT NULL, 
	blocked_expression TEXT, 
	predicates JSONB NOT NULL, 
	hit_partitions JSONB NOT NULL, 
	hit_partition_count INTEGER NOT NULL, 
	total_partition_count INTEGER NOT NULL, 
	col_ratio FLOAT NOT NULL, 
	projected_columns JSONB NOT NULL, 
	referenced_columns JSONB NOT NULL, 
	has_star BOOLEAN NOT NULL, 
	scan_bytes BIGINT NOT NULL, 
	scan_cost_cny FLOAT NOT NULL, 
	full_scan_bytes BIGINT NOT NULL, 
	rationale TEXT NOT NULL, 
	analyzed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_query_log_external_id ON query_log (external_id);

CREATE INDEX ix_query_log_query_date ON query_log (query_date);

CREATE INDEX ix_query_log_target_table ON query_log (target_table);

CREATE TABLE audit_log (
	id SERIAL NOT NULL, 
	actor_email VARCHAR(160) NOT NULL, 
	actor_role VARCHAR(16) NOT NULL, 
	action VARCHAR(48) NOT NULL, 
	resource_type VARCHAR(32) NOT NULL, 
	resource_id VARCHAR(64), 
	method VARCHAR(8) NOT NULL, 
	path VARCHAR(200) NOT NULL, 
	status_code INTEGER NOT NULL, 
	ip VARCHAR(64), 
	detail JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_audit_log_actor_email ON audit_log (actor_email);

CREATE INDEX ix_audit_log_action ON audit_log (action);

CREATE TABLE table_column (
	id SERIAL NOT NULL, 
	table_id INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	data_type VARCHAR(32) NOT NULL, 
	bytes BIGINT NOT NULL, 
	byte_ratio FLOAT NOT NULL, 
	ordinal INTEGER NOT NULL, 
	is_partition_key BOOLEAN NOT NULL, 
	note VARCHAR(160) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(table_id) REFERENCES table_meta (id) ON DELETE CASCADE
);

CREATE INDEX ix_table_column_table_id ON table_column (table_id);

CREATE TABLE partition_meta (
	id SERIAL NOT NULL, 
	table_id INTEGER NOT NULL, 
	dt VARCHAR(16) NOT NULL, 
	bytes BIGINT NOT NULL, 
	row_count BIGINT NOT NULL, 
	file_count INTEGER NOT NULL, 
	is_current BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(table_id) REFERENCES table_meta (id) ON DELETE CASCADE
);

CREATE INDEX ix_partition_meta_table_id ON partition_meta (table_id);

CREATE INDEX ix_partition_meta_dt ON partition_meta (dt);

CREATE TABLE estimate_run (
	id SERIAL NOT NULL, 
	run_no VARCHAR(48) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	scope VARCHAR(24) NOT NULL, 
	scope_value VARCHAR(96), 
	query_count INTEGER NOT NULL, 
	parsed_count INTEGER NOT NULL, 
	blocked_count INTEGER NOT NULL, 
	prunable_count INTEGER NOT NULL, 
	total_scan_bytes BIGINT NOT NULL, 
	total_cost_cny FLOAT NOT NULL, 
	monthly_projected_cost_cny FLOAT NOT NULL, 
	saved_by_rewrites_bytes BIGINT NOT NULL, 
	top_query_id INTEGER, 
	top_scan_bytes BIGINT NOT NULL, 
	budget_status VARCHAR(16) NOT NULL, 
	budget_policy_id INTEGER, 
	note TEXT NOT NULL, 
	error_message TEXT, 
	created_by VARCHAR(80) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(top_query_id) REFERENCES query_log (id), 
	FOREIGN KEY(budget_policy_id) REFERENCES budget_policy (id)
);

CREATE UNIQUE INDEX ix_estimate_run_run_no ON estimate_run (run_no);

CREATE TABLE rewrite_suggestion (
	id SERIAL NOT NULL, 
	suggestion_no VARCHAR(48) NOT NULL, 
	query_log_id INTEGER NOT NULL, 
	estimate_run_id INTEGER, 
	anti_patterns JSONB NOT NULL, 
	risk_level VARCHAR(16) NOT NULL, 
	confidence FLOAT NOT NULL, 
	before_scan_bytes BIGINT NOT NULL, 
	after_scan_bytes BIGINT NOT NULL, 
	saving_bytes BIGINT NOT NULL, 
	saving_cost_cny FLOAT NOT NULL, 
	saving_pct FLOAT NOT NULL, 
	score FLOAT NOT NULL, 
	rewritten_sql TEXT NOT NULL, 
	rationale TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	reviewed_by VARCHAR(80), 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(query_log_id) REFERENCES query_log (id), 
	FOREIGN KEY(estimate_run_id) REFERENCES estimate_run (id)
);

CREATE INDEX ix_rewrite_suggestion_query_log_id ON rewrite_suggestion (query_log_id);

CREATE UNIQUE INDEX ix_rewrite_suggestion_suggestion_no ON rewrite_suggestion (suggestion_no);
