"""
Automates the checking of the audit flag and creates
the correct SQL
"""

from alembic import op
from alembic.autogenerate import comparators
from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase


@Operations.register_operation('audit_table')
class AuditTableOperation(MigrateOperation):
    """Audits or un-audits a table for changes."""

    def __init__(self, table_name, audit=True):
        self.table_name = table_name
        self.audit = audit

    @classmethod
    def audit_table(cls, operations, table_name, should_audit: bool):
        """Audit the specified table."""

        operation = AuditTableOperation(table_name, audit=should_audit)
        return operations.invoke(operation)

    def reverse(self):
        # Return an operation that does the opposite of this operation.
        # In this case, if audit=True, return an operation that doesn't audit.
        # If audit=False, return an operation that audits.
        return AuditTableOperation(self.table_name, not self.audit)


@Operations.implementation_for(AuditTableOperation)
def audit_table(operations, operation: AuditTableOperation):
    """Registers operation to op
    handles Audit or un-audit the specified table."""

    if operation.audit:
        sql = text(f"SELECT audit.track_table('{operation.table_name}'::regclass);")
    else:
        sql = text(f"SELECT audit.ignore_table('{operation.table_name}'::regclass);")

    op.execute(sql)


def register_audit_metadata(target_metadata, base_model: DeclarativeBase):
    audit_enabled_by_table_name = {}
    for mapper in base_model.registry.mappers:
        table = mapper.local_table.name
        audit_enabled_by_table_name[table] = mapper.class_.__system_audit__

    target_metadata.info.setdefault('audit_enabled_tables', audit_enabled_by_table_name)


from alembic.autogenerate import renderers


@renderers.dispatch_for(AuditTableOperation)
def render_create_sequence(autogen_context, op):
    """
    How the operation should render its python
    """
    return f"op.audit_table('{op.table_name}', {op.audit})"


@comparators.dispatch_for('table')
def compare_table_level(autogen_context, modify_ops, schemaname, tablename, conn_table, metadata_table):
    audit = autogen_context.metadata.info.get('audit_enabled_tables').get(tablename)
    conn = op.get_bind()
    if conn_table is not None:
        result = conn.execute(
            text(
                f"""
                SELECT count(*) FROM pg_trigger
                WHERE tgrelid = '{tablename}'::regclass
                AND (tgname = 'audit_trigger_row' OR tgname = 'audit_trigger_stm');        
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

    # Need to take an action
    if not audit and count == 2:
        modify_ops.ops.append(AuditTableOperation(tablename, audit=False))
    elif audit and count != 2:
        modify_ops.ops.append(AuditTableOperation(tablename, audit=True))
