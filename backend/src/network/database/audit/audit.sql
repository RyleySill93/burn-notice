-- An audit history is important on most tables. Provide an audit trigger that logs to
-- a dedicated audit table for the major relations.

-- Defined variables set with application as local to each transaction
-- auditcontext.user_type
-- auditcontext.user_id
-- auditcontext.request_id
-- auditcontext.context


-- Reload the configuration to make the changes take effect
SELECT pg_reload_conf();

CREATE OR REPLACE FUNCTION JSONB_SUBTRACT(v1 JSONB, v2 JSONB)
RETURNS JSONB AS $$
DECLARE
  result JSONB;
  v RECORD;
BEGIN
  result = v1;
  FOR v IN SELECT * FROM JSONB_EACH(v2) LOOP
    IF result->v.key IS NOT DISTINCT FROM v.value
      THEN result = result - v.key;
    END IF;
  END LOOP;
  RETURN result;
END;
$$ LANGUAGE PLPGSQL;

CREATE SCHEMA IF NOT EXISTS audit;
COMMENT ON SCHEMA audit IS 'Out-of-table audit/history logging tables and trigger functions';

-- Remember, every column you add takes up more audit table space and slows audit
-- inserts.
--
-- Every index you add has a big impact too, so avoid adding indexes to the
-- audit table unless you REALLY need them
--
-- It is sometimes worth copying the audit table, or a coarse subset of it that
-- you're interested in, into a temporary table where you CREATE any useful
-- indexes and do your analysis.
DROP TABLE IF EXISTS audit.entry;
CREATE TABLE audit.entry (
  entry_id BIGSERIAL,
  table_name TEXT NOT NULL,
--   relid OID NOT NULL,
  action_tstamp_tx TIMESTAMP WITH TIME ZONE NOT NULL,
  action_tstamp_stm TIMESTAMP WITH TIME ZONE NOT NULL,
  action_tstamp_clk TIMESTAMP WITH TIME ZONE NOT NULL,
  transaction_id BIGINT,
--   app_user_type TEXT NOT NULL CHECK (app_user_type in ('D', 'M', 'U', 'S')),
  app_user_type TEXT,
  app_user_id TEXT,
  app_request_id TEXT,
  app_context JSONB,
  client_query TEXT,
  action TEXT NOT NULL CHECK (action IN ('I', 'D', 'U', 'T')),
  row_data JSONB,
  changed_data JSONB,
  statement_only BOOLEAN NOT NULL
) PARTITION BY RANGE(action_tstamp_stm);
COMMENT ON TABLE audit.entry IS 'History of auditable actions on audited tables, from audit.if_modified_func()';
COMMENT ON COLUMN audit.entry.entry_id IS 'Unique identifier for each auditable event';
COMMENT ON COLUMN audit.entry.table_name IS 'Non-schema-qualified table name of table event occured in';
-- COMMENT ON COLUMN audit.entry.relid IS 'Table OID. Changes with drop/create. Get with ''tablename''::regclass';
COMMENT ON COLUMN audit.entry.app_user_type IS 'User type; D = direct, M = manual, U = user, S = system';
COMMENT ON COLUMN audit.entry.app_user_id IS 'Pk of user that made the change in the application.';
COMMENT ON COLUMN audit.entry.app_request_id IS 'Request id of request that caused change.';
COMMENT ON COLUMN audit.entry.app_context IS 'Additional map of context provided by app.';
COMMENT ON COLUMN audit.entry.action_tstamp_tx IS 'Transaction start timestamp for tx in which audited event occurred';
COMMENT ON COLUMN audit.entry.action_tstamp_stm IS 'Statement start timestamp for tx in which audited event occurred';
COMMENT ON COLUMN audit.entry.action_tstamp_clk IS 'Wall clock time at which audited event''s trigger call occurred';
COMMENT ON COLUMN audit.entry.transaction_id IS 'Identifier of transaction that made the change. May wrap, but unique paired with action_tstamp_tx.';
COMMENT ON COLUMN audit.entry.client_query IS 'Top-level query that caused this auditable event. May be more than one statement.';
COMMENT ON COLUMN audit.entry.action IS 'Action type; I = insert, D = delete, U = update, T = truncate';
COMMENT ON COLUMN audit.entry.row_data IS 'Record value. Null for statement-level trigger. For INSERT this is the new tuple. For DELETE and UPDATE it is the old tuple.';
COMMENT ON COLUMN audit.entry.changed_data IS 'New values of fields changed by UPDATE. Null except for row-level UPDATE events.';
COMMENT ON COLUMN audit.entry.statement_only IS '''t'' if audit event is from an FOR EACH STATEMENT trigger, ''f'' for FOR EACH ROW';

CREATE OR REPLACE FUNCTION audit.if_modified_func() RETURNS TRIGGER AS $body$
DECLARE
  audit_table_name VARCHAR;
  audit_table_start_dt VARCHAR;
  audit_table_end_dt VARCHAR;
  audit_row audit.entry;
  include_values BOOLEAN;
  log_diffs BOOLEAN;
  j_old JSONB;
  j_new JSONB;
  excluded_cols TEXT[] = ARRAY[]::TEXT[];
  inserted_entry_id INTEGER;
BEGIN
  IF TG_WHEN <> 'AFTER' THEN
    RAISE EXCEPTION 'audit.if_modified_func() may only run as an AFTER trigger';
  END IF;

  audit_row = ROW(
    NEXTVAL('audit.entry_entry_id_seq'),                    -- entry_id
    TG_TABLE_NAME::TEXT,                                    -- table_name
 -- Using OID doesnt restore cleanly which for now is not something I want to deal with
 -- TG_RELID,                                               -- relation OID for much quicker searches
    CURRENT_TIMESTAMP,                                      -- action_tstamp_tx
    STATEMENT_TIMESTAMP(),                                  -- action_tstamp_stm
    CLOCK_TIMESTAMP(),                                      -- action_tstamp_clk
    TXID_CURRENT(),                                         -- transaction ID
    'D',                                                    -- application user type
    NULL,                                                   -- application user id
    NULL,                                                   -- application request id
    NULL,                                                   -- application request context
    CURRENT_QUERY(),                                        -- top-level query or queries (if multistatement) from client
    SUBSTRING(TG_OP, 1, 1),                                 -- action
    NULL,                                                   -- row_data
    NULL,                                                   -- changed_data
    'f'                                                     -- statement_only
  );

  IF NOT TG_ARGV[0]::BOOLEAN IS DISTINCT FROM 'f'::BOOLEAN THEN
    audit_row.client_query = NULL;
  END IF;

  IF TG_ARGV[1] IS NOT NULL THEN
    excluded_cols = TG_ARGV[1]::TEXT[];
  END IF;

  IF (TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW') THEN
    audit_row.row_data = TO_JSONB(OLD) - excluded_cols;
    audit_row.changed_data = JSONB_SUBTRACT(TO_JSONB(NEW), audit_row.row_data) - excluded_cols;
    IF audit_row.changed_data = '{}'::JSONB THEN
      -- All changed fields are ignored. Skip this update.
      RETURN NULL;
    END IF;
  ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW') THEN
    audit_row.row_data = TO_JSONB(OLD) - excluded_cols;
  ELSIF (TG_OP = 'INSERT' AND TG_LEVEL = 'ROW') THEN
    audit_row.row_data = TO_JSONB(NEW) - excluded_cols;
  ELSIF (TG_LEVEL = 'STATEMENT' AND TG_OP IN ('INSERT','UPDATE','DELETE','TRUNCATE')) THEN
    audit_row.statement_only = 't';
  ELSE
    RAISE EXCEPTION '[audit.if_modified_func] - Trigger func added as trigger for unhandled case: %, %',TG_OP, TG_LEVEL;
    RETURN NULL;
  END IF;

  -- Set user_type if not null
  IF CURRENT_SETTING('auditcontext.user_type', True) IS NOT NULL THEN
    audit_row.app_user_type = CURRENT_SETTING('auditcontext.user_type');
  END IF;

  -- Set user_id if not null
  IF CURRENT_SETTING('auditcontext.user_id', True) IS NOT NULL THEN
    audit_row.app_user_id = CURRENT_SETTING('auditcontext.user_id');
  END IF;

  -- Set request_id if not null
  IF CURRENT_SETTING('auditcontext.request_id', True) IS NOT NULL THEN
    audit_row.app_request_id = CURRENT_SETTING('auditcontext.request_id');
  END IF;

  -- Set request_context if not null
  IF CURRENT_SETTING('auditcontext.context', True) IS NOT NULL THEN
    audit_row.app_context = CURRENT_SETTING('auditcontext.context')::JSONB;
  END IF;

  audit_table_name = FORMAT(
    'audit.entry_%s_%s',
    TO_CHAR(CURRENT_TIMESTAMP, 'YYYY'),
    TO_CHAR(CURRENT_TIMESTAMP, 'MM')
  );
  audit_table_start_dt = FORMAT(
	'%s',
    date_trunc('month', CURRENT_DATE)
  );
  audit_table_end_dt = FORMAT(
	'%s',
    date_trunc('month', CURRENT_DATE) + interval '1 month'
  );

  IF TO_REGCLASS(audit_table_name) IS NULL THEN
    EXECUTE FORMAT('CREATE TABLE %s PARTITION OF audit.entry FOR VALUES FROM(''%s'') TO (''%s'')', audit_table_name, audit_table_start_dt, audit_table_end_dt);
    EXECUTE FORMAT('ALTER TABLE %s SET (AUTOVACUUM_ENABLED = FALSE, TOAST.AUTOVACUUM_ENABLED = FALSE)', audit_table_name);
  END IF;
  EXECUTE FORMAT('INSERT INTO audit.entry VALUES (($1).*) RETURNING entry_id') INTO inserted_entry_id USING audit_row;

  RETURN NULL;
END;
$body$
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public;

COMMENT ON FUNCTION audit.if_modified_func() IS $body$
Track changes to a table at the statement and/or row level.

Optional parameters to trigger in CREATE TRIGGER call:

param 0: boolean, whether to log the query text. Default 't'.

param 1: text[], columns to ignore in updates. Default [].

         Updates to ignored cols are omitted from changed_data.

         Updates with only ignored cols changed are not inserted
         into the audit log.

         Almost all the processing work is still done for updates
         that ignored. If you need to save the load, you need to use
         WHEN clause on the trigger instead.

         No warning or error is issued if ignored_cols contains columns
         that do not exist in the target table. This lets you specify
         a standard set of ignored columns.

There is no parameter to disable logging of values. Add this trigger as
a 'FOR EACH STATEMENT' rather than 'FOR EACH ROW' trigger if you do not
want to log row values.

Note that the user name logged is the login role for the session. The audit trigger
cannot obtain the active role because it is reset by the SECURITY DEFINER invocation
of the audit trigger its self.
$body$;


CREATE OR REPLACE FUNCTION audit.ignore_table(target_table REGCLASS) RETURNS VOID AS $body$
BEGIN
  EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_row ON ' || target_table;
  EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_stm ON ' || target_table;
END;
$body$
language 'plpgsql';
COMMENT ON FUNCTION audit.ignore_table(REGCLASS) IS $body$
Remove auditing support for a table.
$body$;

CREATE OR REPLACE FUNCTION audit.track_table(target_table REGCLASS, audit_rows BOOLEAN, audit_query_text BOOLEAN, ignored_cols TEXT[]) RETURNS VOID AS $body$
DECLARE
  stm_targets TEXT = 'INSERT OR UPDATE OR DELETE OR TRUNCATE';
  _q_txt TEXT;
  _ignored_cols_snip TEXT = '';
BEGIN
  EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_row ON ' || target_table;
  EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_stm ON ' || target_table;

  IF audit_rows THEN
    IF ARRAY_LENGTH(ignored_cols,1) > 0 THEN
        _ignored_cols_snip = ', ' || QUOTE_LITERAL(ignored_cols);
    END IF;
    _q_txt = 'CREATE TRIGGER audit_trigger_row AFTER INSERT OR UPDATE OR DELETE ON ' ||
             target_table ||
             ' FOR EACH ROW EXECUTE PROCEDURE audit.if_modified_func(' ||
             QUOTE_LITERAL(audit_query_text) || _ignored_cols_snip || ');';
    RAISE NOTICE '%', _q_txt;
    EXECUTE _q_txt;
    stm_targets = 'TRUNCATE';
  ELSE
  END IF;

  _q_txt = 'CREATE TRIGGER audit_trigger_stm AFTER ' || stm_targets || ' ON ' ||
           target_table ||
           ' FOR EACH STATEMENT EXECUTE PROCEDURE audit.if_modified_func('||
           QUOTE_LITERAL(audit_query_text) || ');';
  RAISE NOTICE '%',_q_txt;
  EXECUTE _q_txt;
END;
$body$
language 'plpgsql';

COMMENT ON FUNCTION audit.track_table(REGCLASS, BOOLEAN, BOOLEAN, TEXT[]) IS $body$
Add auditing support to a table.

Arguments:
   target_table:     Table name, schema qualified if not on search_path
   audit_rows:       Record each row change, or only audit at a statement level
   audit_query_text: Record the text of the client query that triggered the audit event?
   ignored_cols:     Columns to exclude from update diffs, ignore updates that change only ignored cols.

Example:
    SELECT audit.track_table('my_table'::REGCLASS);
$body$;

-- Pg doesn't allow variadic calls with 0 params, so provide a wrapper
CREATE OR REPLACE FUNCTION audit.track_table(target_table REGCLASS, audit_rows BOOLEAN, audit_query_text BOOLEAN) RETURNS VOID AS $body$
SELECT audit.track_table($1, $2, $3, ARRAY[]::TEXT[]);
$body$ LANGUAGE SQL;

-- And provide a convenience call wrapper for the simplest case
-- of row-level logging with no excluded cols and query logging enabled.
CREATE OR REPLACE FUNCTION audit.track_table(target_table REGCLASS) RETURNS VOID AS $body$
SELECT audit.track_table($1, BOOLEAN 't', BOOLEAN 't');
$body$ LANGUAGE 'sql';

COMMENT ON FUNCTION audit.track_table(REGCLASS) IS $body$
Add auditing support to the given table. Row-level changes will be logged with full client query text. No cols are ignored.
$body$;
