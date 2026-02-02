-- Defined variables set with application as local to each transaction
-- auditcontext.user_id
-- auditcontext.request_id
-- auditcontext.event_id
-- auditcontext.event_type

-- Enable uuid generation extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create default users
INSERT INTO "user" (id, first_name, last_name, email, is_active)
  VALUES (
      'user-system',
      'System',
      'System',
      'system@mewtwo.com',
      true
  ), (
      'user-engineer',
      'Engineer',
      'Engineer',
      'dev@mewtwo.com',
      true
  )
  ON CONFLICT (email) DO NOTHING;


INSERT INTO "permission" (user_id, scope)
  VALUES ('user-engineer', 'staff::admin'),
        ('user-system', 'staff::admin')
  ON CONFLICT (scope, user_id) DO NOTHING;


CREATE OR REPLACE FUNCTION app_audit_log() RETURNS TRIGGER AS $$
DECLARE
    v_operation_type TEXT;
    v_row_data JSONB;
    v_changed_data JSONB;
    v_row_id VARCHAR(50);
    v_return_obj RECORD;

    -- From application context
    v_event_id UUID;
    v_event_type VARCHAR(200);
    v_request_id TEXT;
    v_user_id VARCHAR(50);
    v_breadcrumb TEXT;
    v_context JSONB;
    v_context_func_name TEXT;
    v_event_context JSONB;
BEGIN
    -- Set all context variables
    -- Set audit_event_id if not null
    IF CURRENT_SETTING('auditcontext.event_id', True) IS NOT NULL THEN
      v_event_id := CURRENT_SETTING('auditcontext.event_id');
    ELSE
        -- Set this by default
        v_event_id := uuid_generate_v4();
    END IF;

    -- Set event_type if not null
    IF CURRENT_SETTING('auditcontext.event_type', True) IS NOT NULL THEN
      v_event_type := CURRENT_SETTING('auditcontext.event_type');
    ELSE
      v_event_type := 'UNKNOWN';
    END IF;

    -- Set user_id if not null
    IF CURRENT_SETTING('auditcontext.user_id', True) IS NOT NULL THEN
      v_user_id := CURRENT_SETTING('auditcontext.user_id');
    END IF;

    -- Set user_id if not null
    IF CURRENT_SETTING('auditcontext.request_id', True) IS NOT NULL THEN
      v_request_id := CURRENT_SETTING('auditcontext.request_id');
    END IF;

    -- Set breadcrumb if not null
    IF CURRENT_SETTING('auditcontext.breadcrumb', True) IS NOT NULL THEN
      v_breadcrumb := CURRENT_SETTING('auditcontext.breadcrumb');
    END IF;

    IF CURRENT_SETTING('auditcontext.event_context', True) IS NOT NULL THEN
      v_event_context := CURRENT_SETTING('auditcontext.event_context');
    END IF;

    -- Determine the type of operation and set the corresponding data:
        -- operation type, before / after
      IF (TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW') THEN
        v_return_obj := NEW;
        v_row_id := OLD.id;
        v_operation_type := 'UPDATE';
        v_row_data := TO_JSONB(OLD);
        -- Subtract function available from system level audit
        v_changed_data := JSONB_SUBTRACT(TO_JSONB(NEW), v_row_data);
        v_changed_data := v_changed_data - 'modified_at';
        IF v_changed_data = '{}'::JSONB THEN
          -- All changed fields are ignored. Skip this update.
          RETURN NULL;
        END IF;
      ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW') THEN
        v_return_obj := OLD;
        v_row_id := OLD.id;
        v_operation_type := 'DELETE';
        v_row_data = TO_JSONB(OLD);
      ELSIF (TG_OP = 'INSERT' AND TG_LEVEL = 'ROW') THEN
        v_return_obj := NEW;
        v_row_id := NEW.id;
        v_operation_type := 'INSERT';
        v_row_data := TO_JSONB(NEW);
      ELSE
        RAISE EXCEPTION '[audit.] - Trigger func added as trigger for unhandled case: %, %',TG_OP, TG_LEVEL;
      END IF;

    -- Get context for this particular table in the format
    -- app_audit_get_{table_name}_context
    v_context_func_name := 'app_audit_get_' || TG_TABLE_NAME || '_context';

    -- Executing the dynamic function and getting the result into v_context
    EXECUTE 'SELECT ' || v_context_func_name || '(''' || v_row_id || ''')' INTO v_context;

    -- Insert an entry into the AuditEvent table with conflict handling to
    -- prevent duplicate event entries
    INSERT INTO auditevent (id, request_id, txn_id, breadcrumb, user_id, occurred_at, event_type, context)
    VALUES (
        v_event_id,
        v_request_id,
        TXID_CURRENT(),
        v_breadcrumb,
        v_user_id,
        NOW(),
        v_event_type,
        v_event_context
    )
    ON CONFLICT (id) DO NOTHING;

    -- Insert an entry into the AuditLog table
    INSERT INTO auditlog (id, event_id, table_name, operation_type, context, row_data, changed_data)
    VALUES (
        uuid_generate_v4(),
        v_event_id,
        TG_TABLE_NAME::TEXT,
        v_operation_type,
        v_context,
        v_row_data,
        v_changed_data
    );
    RETURN v_return_obj;
END;
$$ LANGUAGE plpgsql;



CREATE OR REPLACE FUNCTION app_audit_track_table(target_table REGCLASS) RETURNS VOID AS $$
BEGIN
    -- Remove existing triggers if they exist
    EXECUTE 'DROP TRIGGER IF EXISTS app_audit_delete_trigger ON ' || target_table;
    EXECUTE 'DROP TRIGGER IF EXISTS app_audit_insert_update_trigger ON ' || target_table;

    -- Create a BEFORE DELETE trigger
    EXECUTE 'CREATE TRIGGER app_audit_delete_trigger
             BEFORE DELETE ON ' || target_table || '
             FOR EACH ROW EXECUTE PROCEDURE app_audit_log();';

    -- Create an AFTER INSERT OR UPDATE trigger
    EXECUTE 'CREATE TRIGGER app_audit_insert_update_trigger
             AFTER INSERT OR UPDATE ON ' || target_table || '
             FOR EACH ROW EXECUTE PROCEDURE app_audit_log();';
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION app_audit_ignore_table(target_table REGCLASS) RETURNS VOID as $$
BEGIN
  EXECUTE 'DROP TRIGGER IF EXISTS app_audit_trigger ON ' || target_table;
  EXECUTE 'DROP TRIGGER IF EXISTS app_audit_insert_update_trigger ON ' || target_table;
  EXECUTE 'DROP FUNCTION IF EXISTS app_audit_get_'|| target_table ||'_context(TEXT)';
END;
$$ LANGUAGE plpgsql;
