"""
Automates the checking of the audit flag and creates
the correct SQL
"""

from alembic import op
from alembic.autogenerate import comparators, renderers
from alembic.operations import MigrateOperation, Operations
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase


@Operations.register_operation('app_audit')
class AppAuditTableOperation(MigrateOperation):
    """Audits or un-audits a table for changes at an application level."""

    def __init__(self, table_name, audit=True, context_function: str | None = None):
        self.table_name = table_name
        self.audit = audit
        self.context_function = context_function

    @classmethod
    def app_audit(cls, operations, table_name, should_audit: bool, context_function: str | None = None):
        """Audit the specified table."""

        operation = AppAuditTableOperation(table_name, audit=should_audit, context_function=context_function)
        return operations.invoke(operation)

    def reverse(self):
        # Return an operation that does the opposite of this operation.
        # In this case, if audit=True, return an operation that doesn't audit.
        # If audit=False, return an operation that audits.
        return AppAuditTableOperation(self.table_name, not self.audit, self.context_function)


@Operations.implementation_for(AppAuditTableOperation)
def app_audit(operations, operation: AppAuditTableOperation):
    """Registers operation to op
    handles Audit or un-audit the specified table."""

    if operation.audit:
        # Create context function
        op.execute(
            text(
                f"""
            CREATE OR REPLACE FUNCTION app_audit_get_{operation.table_name}_context(arg_pk TEXT)
            RETURNS JSONB AS $$
            DECLARE
                v_context JSONB;
            BEGIN
                {operation.context_function}
                RETURN v_context;
            END;
            $$ LANGUAGE plpgsql;
            """
            )
        )
        op.execute(text(f"SELECT app_audit_track_table('{operation.table_name}'::regclass);"))
    else:
        op.execute(text(f"SELECT app_audit_ignore_table('{operation.table_name}'::regclass);"))


def register_audit_metadata(target_metadata, base_model: DeclarativeBase):
    application_audit_by_table_name = {}
    for mapper in base_model.registry.mappers:
        table = mapper.local_table.name
        if mapper.class_.__app_audit__:
            context_builder_function = mapper.class_.__app_audit_context_builder__
            application_audit_by_table_name[table] = mapper.class_.__app_audit__, context_builder_function
        else:
            application_audit_by_table_name[table] = mapper.class_.__app_audit__, None

    target_metadata.info.setdefault('app_audit_enabled_tables', application_audit_by_table_name)


@renderers.dispatch_for(AppAuditTableOperation)
def render_create_sequence(autogen_context, op):
    """
    How the operation should render its python
    """
    if op.audit:
        return (
            f'op.app_audit(\n' f"    '{op.table_name}',\n" f'    {op.audit},\n' f'    """{op.context_function}"""' f')'
        )
    # If auditing is not enabled, return a simpler function call
    else:
        return f"op.app_audit('{op.table_name}', {op.audit})"


@comparators.dispatch_for('table')
def compare_table_level(autogen_context, modify_ops, schemaname, tablename, conn_table, metadata_table):
    if metadata_table is None:
        # Table has been removed from code but still may exist in database
        modify_ops.ops.append(AppAuditTableOperation(tablename, audit=False, context_function=None))
        return

    app_audit_enabled_tables = autogen_context.metadata.info.get('app_audit_enabled_tables')
    app_audit_enabled, context_function = app_audit_enabled_tables.get(tablename)
    conn = op.get_bind()
    if conn_table is not None:
        result = conn.execute(
            text(
                f"""
                SELECT count(*) FROM pg_trigger
                WHERE tgrelid = '{tablename}'::regclass
                AND (tgname = 'app_audit_delete_trigger' OR tgname = 'app_audit_insert_update_trigger');     
            """
            )
        )
        try:
            count = result.fetchone()[0]
        except:  # noqa: E722
            count = 0
        result.close()
    else:
        # Assume new table to be created
        count = 0

    # Determine if we need to take an action
    # Is not enabled but exists in DB
    if not app_audit_enabled and count == 2:
        modify_ops.ops.append(AppAuditTableOperation(tablename, audit=False, context_function=context_function))
    # Enabled but doesnt exist in db
    elif app_audit_enabled and count != 2:
        modify_ops.ops.append(AppAuditTableOperation(tablename, audit=True, context_function=context_function))
    # Enabled and exists in db
    elif app_audit_enabled and count == 2:
        # Detect potential changes for context function format
        existing_trigger = conn.execute(
            text(
                f"""
            SELECT pg_get_functiondef('app_audit_get_{tablename}_context'::regproc);            
            """
            )
        )
        pg_func = existing_trigger.fetchone()[0]
        norm_pg_func = normalize_sql(pg_func)
        norm_context_function = normalize_sql(context_function)
        if norm_context_function not in norm_pg_func:
            logger.info(f'detected different __app_audit_context_builder__ for {tablename}')
            modify_ops.ops.append(AppAuditTableOperation(tablename, audit=True, context_function=context_function))


def normalize_sql(sql: str):
    """
    Normalize an SQL string to facilitate comparison.
    - Remove comments
    - Convert all whitespace sequences to a single space
    - Strip leading/trailing whitespace
    """
    import re

    # Remove comments (simple single line -- comments)
    no_comments = re.sub(r'--.*', '', sql)

    # Replace multiple whitespace (including new lines and tabs) with a single space
    normalized = re.sub(r'\s+', ' ', no_comments)

    # Convert to lower case for case-insensitive comparison (optional)
    normalized = normalized.lower()

    # Strip leading/trailing whitespace
    return normalized.strip()
