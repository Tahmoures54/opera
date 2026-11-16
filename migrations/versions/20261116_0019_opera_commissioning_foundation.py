"""Create the OPERA commissioning foundation tables.

Revision ID: 20261116_0019
Revises: 20261017_0018
"""
from alembic import op
import sqlalchemy as sa

revision = "20261116_0019"
down_revision = "20261017_0018"
branch_labels = None
depends_on = None


def upgrade():
    # Frozen DDL for the initial OPERA schema. Existing MaterialHub tables
    # (including user and document_sequence) are referenced, never recreated.
    op.create_table('commissioning_attachment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=80), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('mime_type', sa.String(length=120), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('uploaded_by_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_comm_attachment_company_entity', 'commissioning_attachment', ['company_name', 'entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_commissioning_attachment_company_name'), 'commissioning_attachment', ['company_name'], unique=False)
    op.create_table('commissioning_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=80), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('before_json', sa.JSON(), nullable=True),
        sa.Column('after_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_comm_audit_company_entity', 'commissioning_audit_log', ['company_name', 'entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_commissioning_audit_log_company_name'), 'commissioning_audit_log', ['company_name'], unique=False)
    op.create_table('commissioning_project',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('client', sa.String(length=200), nullable=True),
        sa.Column('contractor', sa.String(length=200), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('target_end_date', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('PLANNING', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED', name='commissioning_project_status', native_enum=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'project_code', name='uq_comm_project_company_code'),
        sa.UniqueConstraint('id', 'company_name', name='uq_comm_project_id_company')
    )
    op.create_index('ix_comm_project_company_status', 'commissioning_project', ['company_name', 'status'], unique=False)
    op.create_index(op.f('ix_commissioning_project_company_name'), 'commissioning_project', ['company_name'], unique=False)
    op.create_table('commissioning_signature',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=80), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('signature_type', sa.String(length=50), nullable=False),
        sa.Column('signer_id', sa.Integer(), nullable=False),
        sa.Column('verification_method', sa.String(length=30), nullable=False),
        sa.Column('verification_reference', sa.String(length=100), nullable=True),
        sa.Column('signed_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('signature_metadata_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['signer_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_comm_signature_company_entity', 'commissioning_signature', ['company_name', 'entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_commissioning_signature_company_name'), 'commissioning_signature', ['company_name'], unique=False)
    op.create_table('commissioning_membership',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Enum('commissioning_manager', 'commissioning_engineer', 'qc_inspector', 'client_representative', 'operations_lead', 'viewer', name='commissioning_membership_role', native_enum=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_membership_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'project_id', 'user_id', name='uq_comm_membership_project_user')
    )
    op.create_index('ix_comm_membership_company_project_role', 'commissioning_membership', ['company_name', 'project_id', 'role'], unique=False)
    op.create_index(op.f('ix_commissioning_membership_company_name'), 'commissioning_membership', ['company_name'], unique=False)
    op.create_table('commissioning_system',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('system_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('p_and_id_ref', sa.String(length=200), nullable=True),
        sa.Column('weight_percent', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('weight_percent >= 0 AND weight_percent <= 100', name='ck_comm_system_weight'),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_system_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'project_id', 'system_code', name='uq_comm_system_code'),
        sa.UniqueConstraint('id', 'company_name', name='uq_comm_system_id_company')
    )
    op.create_index('ix_comm_system_company_project', 'commissioning_system', ['company_name', 'project_id'], unique=False)
    op.create_index(op.f('ix_commissioning_system_company_name'), 'commissioning_system', ['company_name'], unique=False)
    op.create_table('commissioning_subsystem',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=False),
        sa.Column('subsystem_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('weight_percent', sa.Float(), nullable=False),
        sa.Column('mc_target_date', sa.Date(), nullable=True),
        sa.Column('rf_target_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('weight_percent >= 0 AND weight_percent <= 100', name='ck_comm_subsystem_weight'),
        sa.ForeignKeyConstraint(['system_id', 'company_name'], ['commissioning_system.id', 'commissioning_system.company_name'], name='fk_comm_subsystem_system_tenant'),
        sa.ForeignKeyConstraint(['system_id'], ['commissioning_system.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'system_id', 'subsystem_code', name='uq_comm_subsystem_code'),
        sa.UniqueConstraint('id', 'company_name', name='uq_comm_subsystem_id_company')
    )
    op.create_index('ix_comm_subsystem_company_system', 'commissioning_subsystem', ['company_name', 'system_id'], unique=False)
    op.create_index(op.f('ix_commissioning_subsystem_company_name'), 'commissioning_subsystem', ['company_name'], unique=False)
    op.create_table('commissioning_equipment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('subsystem_id', sa.Integer(), nullable=False),
        sa.Column('tag_number', sa.String(length=100), nullable=False),
        sa.Column('equipment_type', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('manufacturer', sa.String(length=150), nullable=True),
        sa.Column('model_number', sa.String(length=100), nullable=True),
        sa.Column('serial_no', sa.String(length=100), nullable=True),
        sa.Column('specs_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_equipment_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subsystem_id', 'company_name'], ['commissioning_subsystem.id', 'commissioning_subsystem.company_name'], name='fk_comm_equipment_subsystem_tenant'),
        sa.ForeignKeyConstraint(['subsystem_id'], ['commissioning_subsystem.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'project_id', 'tag_number', name='uq_comm_equipment_tag'),
        sa.UniqueConstraint('id', 'company_name', name='uq_comm_equipment_id_company')
    )
    op.create_index('ix_comm_equipment_company_subsystem', 'commissioning_equipment', ['company_name', 'subsystem_id'], unique=False)
    op.create_index(op.f('ix_commissioning_equipment_company_name'), 'commissioning_equipment', ['company_name'], unique=False)
    op.create_table('commissioning_handover_package',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('subsystem_id', sa.Integer(), nullable=False),
        sa.Column('package_number', sa.String(length=100), nullable=False),
        sa.Column('mc_certificate_number', sa.String(length=100), nullable=True),
        sa.Column('rf_certificate_number', sa.String(length=100), nullable=True),
        sa.Column('mc_certificate_date', sa.Date(), nullable=True),
        sa.Column('rf_certificate_date', sa.Date(), nullable=True),
        sa.Column('mc_issued_by_id', sa.Integer(), nullable=True),
        sa.Column('rf_issued_by_id', sa.Integer(), nullable=True),
        sa.Column('accepted_by_operations', sa.Boolean(), nullable=False),
        sa.Column('operations_accepted_by_id', sa.Integer(), nullable=True),
        sa.Column('operations_accepted_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('documents_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'MC_PENDING', 'MC_CERTIFIED', 'RF_PENDING', 'RF_CERTIFIED', 'RFSU', 'ACCEPTED', 'REJECTED', name='commissioning_handover_status', native_enum=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['mc_issued_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['operations_accepted_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_handover_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rf_issued_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subsystem_id', 'company_name'], ['commissioning_subsystem.id', 'commissioning_subsystem.company_name'], name='fk_comm_handover_subsystem_tenant'),
        sa.ForeignKeyConstraint(['subsystem_id'], ['commissioning_subsystem.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'package_number', name='uq_comm_handover_package_number')
    )
    op.create_index('ix_comm_handover_company_subsystem_status', 'commissioning_handover_package', ['company_name', 'subsystem_id', 'status'], unique=False)
    op.create_index(op.f('ix_commissioning_handover_package_company_name'), 'commissioning_handover_package', ['company_name'], unique=False)
    op.create_table('commissioning_progress_snapshot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=True),
        sa.Column('subsystem_id', sa.Integer(), nullable=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('percent_complete', sa.Float(), nullable=False),
        sa.Column('weighted_percent', sa.Float(), nullable=False),
        sa.Column('punch_open_count', sa.Integer(), nullable=False),
        sa.Column('punch_closed_count', sa.Integer(), nullable=False),
        sa.Column('checksheet_total', sa.Integer(), nullable=False),
        sa.Column('checksheet_signed_off', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('percent_complete >= 0 AND percent_complete <= 100', name='ck_comm_progress_percent_range'),
        sa.CheckConstraint('weighted_percent >= 0 AND weighted_percent <= 100', name='ck_comm_progress_weighted_range'),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_progress_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subsystem_id', 'company_name'], ['commissioning_subsystem.id', 'commissioning_subsystem.company_name'], name='fk_comm_progress_subsystem_tenant'),
        sa.ForeignKeyConstraint(['subsystem_id'], ['commissioning_subsystem.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['system_id', 'company_name'], ['commissioning_system.id', 'commissioning_system.company_name'], name='fk_comm_progress_system_tenant'),
        sa.ForeignKeyConstraint(['system_id'], ['commissioning_system.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'project_id', 'system_id', 'subsystem_id', 'snapshot_date', name='uq_comm_progress_snapshot_scope_date')
    )
    op.create_index('ix_comm_progress_company_project_date', 'commissioning_progress_snapshot', ['company_name', 'project_id', 'snapshot_date'], unique=False)
    op.create_index(op.f('ix_commissioning_progress_snapshot_company_name'), 'commissioning_progress_snapshot', ['company_name'], unique=False)
    op.create_table('commissioning_check_sheet',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=False),
        sa.Column('subsystem_id', sa.Integer(), nullable=False),
        sa.Column('equipment_id', sa.Integer(), nullable=True),
        sa.Column('sheet_number', sa.String(length=100), nullable=False),
        sa.Column('sheet_type', sa.Enum('PRE_COMM_A', 'PRE_COMM_B', 'COMM_C', 'FUNCTIONAL_TEST', name='commissioning_check_sheet_type', native_enum=False), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('supersedes_id', sa.Integer(), nullable=True),
        sa.Column('sheet_weight', sa.Float(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'ISSUED', 'IN_PROGRESS', 'SIGNED_OFF', 'REJECTED', name='commissioning_check_sheet_status', native_enum=False), nullable=False),
        sa.Column('issued_by_id', sa.Integer(), nullable=True),
        sa.Column('issued_at', sa.DateTime(), nullable=True),
        sa.Column('signed_by_client_id', sa.Integer(), nullable=True),
        sa.Column('signed_by_contractor_id', sa.Integer(), nullable=True),
        sa.Column('signed_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('revision >= 0', name='ck_comm_check_revision_nonnegative'),
        sa.CheckConstraint('sheet_weight > 0', name='ck_comm_check_sheet_weight_positive'),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['equipment_id', 'company_name'], ['commissioning_equipment.id', 'commissioning_equipment.company_name'], name='fk_comm_check_equipment_tenant'),
        sa.ForeignKeyConstraint(['equipment_id'], ['commissioning_equipment.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['issued_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_check_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['signed_by_client_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['signed_by_contractor_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subsystem_id', 'company_name'], ['commissioning_subsystem.id', 'commissioning_subsystem.company_name'], name='fk_comm_check_subsystem_tenant'),
        sa.ForeignKeyConstraint(['subsystem_id'], ['commissioning_subsystem.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supersedes_id', 'company_name'], ['commissioning_check_sheet.id', 'commissioning_check_sheet.company_name'], name='fk_comm_check_supersedes_tenant'),
        sa.ForeignKeyConstraint(['supersedes_id'], ['commissioning_check_sheet.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['system_id', 'company_name'], ['commissioning_system.id', 'commissioning_system.company_name'], name='fk_comm_check_system_tenant'),
        sa.ForeignKeyConstraint(['system_id'], ['commissioning_system.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'sheet_number', 'revision', name='uq_comm_check_sheet_revision'),
        sa.UniqueConstraint('id', 'company_name', name='uq_comm_check_sheet_id_company')
    )
    op.create_index('ix_comm_check_company_project_status', 'commissioning_check_sheet', ['company_name', 'project_id', 'status'], unique=False)
    op.create_index('ix_comm_check_company_subsystem_type', 'commissioning_check_sheet', ['company_name', 'subsystem_id', 'sheet_type'], unique=False)
    op.create_index(op.f('ix_commissioning_check_sheet_company_name'), 'commissioning_check_sheet', ['company_name'], unique=False)
    op.create_table('commissioning_check_sheet_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('check_sheet_id', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('expected_result', sa.Text(), nullable=True),
        sa.Column('actual_result', sa.Text(), nullable=True),
        sa.Column('result_status', sa.Enum('PENDING', 'OK', 'NOK', 'NA', name='commissioning_item_result_status', native_enum=False), nullable=False),
        sa.Column('witness_required', sa.Boolean(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=True),
        sa.Column('verified_by_id', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('sequence >= 1', name='ck_comm_check_item_sequence_positive'),
        sa.ForeignKeyConstraint(['check_sheet_id', 'company_name'], ['commissioning_check_sheet.id', 'commissioning_check_sheet.company_name'], name='fk_comm_check_item_sheet_tenant'),
        sa.ForeignKeyConstraint(['check_sheet_id'], ['commissioning_check_sheet.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['operator_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['verified_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'check_sheet_id', 'sequence', name='uq_comm_check_item_sequence'),
        sa.UniqueConstraint('id', 'company_name', name='uq_comm_check_item_id_company')
    )
    op.create_index('ix_comm_check_item_company_sheet', 'commissioning_check_sheet_item', ['company_name', 'check_sheet_id'], unique=False)
    op.create_index(op.f('ix_commissioning_check_sheet_item_company_name'), 'commissioning_check_sheet_item', ['company_name'], unique=False)
    op.create_table('commissioning_check_sheet_revision',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('sheet_number', sa.String(length=100), nullable=False),
        sa.Column('previous_check_sheet_id', sa.Integer(), nullable=False),
        sa.Column('new_check_sheet_id', sa.Integer(), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('revision_reason', sa.Text(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['new_check_sheet_id', 'company_name'], ['commissioning_check_sheet.id', 'commissioning_check_sheet.company_name'], name='fk_comm_revision_new_tenant'),
        sa.ForeignKeyConstraint(['new_check_sheet_id'], ['commissioning_check_sheet.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['previous_check_sheet_id', 'company_name'], ['commissioning_check_sheet.id', 'commissioning_check_sheet.company_name'], name='fk_comm_revision_previous_tenant'),
        sa.ForeignKeyConstraint(['previous_check_sheet_id'], ['commissioning_check_sheet.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'sheet_number', 'revision_number', name='uq_comm_revision_number')
    )
    op.create_index(op.f('ix_commissioning_check_sheet_revision_company_name'), 'commissioning_check_sheet_revision', ['company_name'], unique=False)
    op.create_table('commissioning_punch_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('subsystem_id', sa.Integer(), nullable=False),
        sa.Column('equipment_id', sa.Integer(), nullable=True),
        sa.Column('check_sheet_id', sa.Integer(), nullable=True),
        sa.Column('punch_number', sa.String(length=100), nullable=False),
        sa.Column('category', sa.Enum('A', 'B', 'C', 'D', name='commissioning_punch_category', native_enum=False), nullable=False),
        sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='commissioning_punch_severity', native_enum=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('raised_by_id', sa.Integer(), nullable=False),
        sa.Column('raised_at', sa.DateTime(), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('target_closure_date', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'IN_PROGRESS', 'CLOSED', 'VERIFIED', 'WAIVED', name='commissioning_punch_status', native_enum=False), nullable=False),
        sa.Column('closed_by_id', sa.Integer(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('verified_by_id', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('waived_by_id', sa.Integer(), nullable=True),
        sa.Column('waived_at', sa.DateTime(), nullable=True),
        sa.Column('waiver_reason', sa.Text(), nullable=True),
        sa.Column('photos_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['check_sheet_id', 'company_name'], ['commissioning_check_sheet.id', 'commissioning_check_sheet.company_name'], name='fk_comm_punch_sheet_tenant'),
        sa.ForeignKeyConstraint(['check_sheet_id'], ['commissioning_check_sheet.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['closed_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['equipment_id', 'company_name'], ['commissioning_equipment.id', 'commissioning_equipment.company_name'], name='fk_comm_punch_equipment_tenant'),
        sa.ForeignKeyConstraint(['equipment_id'], ['commissioning_equipment.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_punch_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['raised_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subsystem_id', 'company_name'], ['commissioning_subsystem.id', 'commissioning_subsystem.company_name'], name='fk_comm_punch_subsystem_tenant'),
        sa.ForeignKeyConstraint(['subsystem_id'], ['commissioning_subsystem.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['verified_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['waived_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_name', 'punch_number', name='uq_comm_punch_number'),
        sa.UniqueConstraint('id', 'company_name', name='uq_comm_punch_id_company')
    )
    op.create_index('ix_comm_punch_company_category_status', 'commissioning_punch_item', ['company_name', 'category', 'status'], unique=False)
    op.create_index('ix_comm_punch_company_project_status', 'commissioning_punch_item', ['company_name', 'project_id', 'status'], unique=False)
    op.create_index('ix_comm_punch_company_raised_at', 'commissioning_punch_item', ['company_name', 'raised_at'], unique=False)
    op.create_index(op.f('ix_commissioning_punch_item_company_name'), 'commissioning_punch_item', ['company_name'], unique=False)
    op.create_table('commissioning_punch_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('punch_item_id', sa.Integer(), nullable=False),
        sa.Column('old_status', sa.Enum('OPEN', 'IN_PROGRESS', 'CLOSED', 'VERIFIED', 'WAIVED', name='commissioning_punch_old_status', native_enum=False), nullable=True),
        sa.Column('new_status', sa.Enum('OPEN', 'IN_PROGRESS', 'CLOSED', 'VERIFIED', 'WAIVED', name='commissioning_punch_new_status', native_enum=False), nullable=False),
        sa.Column('changed_by_id', sa.Integer(), nullable=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['changed_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['punch_item_id', 'company_name'], ['commissioning_punch_item.id', 'commissioning_punch_item.company_name'], name='fk_comm_punch_history_item_tenant'),
        sa.ForeignKeyConstraint(['punch_item_id'], ['commissioning_punch_item.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_comm_punch_history_company_item', 'commissioning_punch_history', ['company_name', 'punch_item_id'], unique=False)
    op.create_index(op.f('ix_commissioning_punch_history_company_name'), 'commissioning_punch_history', ['company_name'], unique=False)
    op.create_table('commissioning_witness_point',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('check_sheet_id', sa.Integer(), nullable=False),
        sa.Column('check_sheet_item_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.Enum('WITNESS', 'HOLD', 'REVIEW', name='commissioning_witness_type', native_enum=False), nullable=False),
        sa.Column('notified_party', sa.String(length=200), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('attended_by_id', sa.Integer(), nullable=True),
        sa.Column('attended_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.String(length=30), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('released_by_id', sa.Integer(), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('PLANNED', 'NOTIFIED', 'ATTENDED', 'RELEASED', 'CANCELLED', name='commissioning_witness_status', native_enum=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['attended_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['check_sheet_id', 'company_name'], ['commissioning_check_sheet.id', 'commissioning_check_sheet.company_name'], name='fk_comm_witness_sheet_tenant'),
        sa.ForeignKeyConstraint(['check_sheet_id'], ['commissioning_check_sheet.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['check_sheet_item_id', 'company_name'], ['commissioning_check_sheet_item.id', 'commissioning_check_sheet_item.company_name'], name='fk_comm_witness_item_tenant'),
        sa.ForeignKeyConstraint(['check_sheet_item_id'], ['commissioning_check_sheet_item.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_id', 'company_name'], ['commissioning_project.id', 'commissioning_project.company_name'], name='fk_comm_witness_project_tenant'),
        sa.ForeignKeyConstraint(['project_id'], ['commissioning_project.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['released_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_comm_witness_company_schedule', 'commissioning_witness_point', ['company_name', 'scheduled_at'], unique=False)
    op.create_index(op.f('ix_commissioning_witness_point_company_name'), 'commissioning_witness_point', ['company_name'], unique=False)
        # ### end Alembic commands ###


def downgrade():
    # Only OPERA-owned tables and indexes are removed.
    op.drop_index(op.f('ix_commissioning_witness_point_company_name'), table_name='commissioning_witness_point')
    op.drop_index('ix_comm_witness_company_schedule', table_name='commissioning_witness_point')
    op.drop_table('commissioning_witness_point')
    op.drop_index(op.f('ix_commissioning_punch_history_company_name'), table_name='commissioning_punch_history')
    op.drop_index('ix_comm_punch_history_company_item', table_name='commissioning_punch_history')
    op.drop_table('commissioning_punch_history')
    op.drop_index(op.f('ix_commissioning_punch_item_company_name'), table_name='commissioning_punch_item')
    op.drop_index('ix_comm_punch_company_raised_at', table_name='commissioning_punch_item')
    op.drop_index('ix_comm_punch_company_project_status', table_name='commissioning_punch_item')
    op.drop_index('ix_comm_punch_company_category_status', table_name='commissioning_punch_item')
    op.drop_table('commissioning_punch_item')
    op.drop_index(op.f('ix_commissioning_check_sheet_revision_company_name'), table_name='commissioning_check_sheet_revision')
    op.drop_table('commissioning_check_sheet_revision')
    op.drop_index(op.f('ix_commissioning_check_sheet_item_company_name'), table_name='commissioning_check_sheet_item')
    op.drop_index('ix_comm_check_item_company_sheet', table_name='commissioning_check_sheet_item')
    op.drop_table('commissioning_check_sheet_item')
    op.drop_index(op.f('ix_commissioning_check_sheet_company_name'), table_name='commissioning_check_sheet')
    op.drop_index('ix_comm_check_company_subsystem_type', table_name='commissioning_check_sheet')
    op.drop_index('ix_comm_check_company_project_status', table_name='commissioning_check_sheet')
    op.drop_table('commissioning_check_sheet')
    op.drop_index(op.f('ix_commissioning_progress_snapshot_company_name'), table_name='commissioning_progress_snapshot')
    op.drop_index('ix_comm_progress_company_project_date', table_name='commissioning_progress_snapshot')
    op.drop_table('commissioning_progress_snapshot')
    op.drop_index(op.f('ix_commissioning_handover_package_company_name'), table_name='commissioning_handover_package')
    op.drop_index('ix_comm_handover_company_subsystem_status', table_name='commissioning_handover_package')
    op.drop_table('commissioning_handover_package')
    op.drop_index(op.f('ix_commissioning_equipment_company_name'), table_name='commissioning_equipment')
    op.drop_index('ix_comm_equipment_company_subsystem', table_name='commissioning_equipment')
    op.drop_table('commissioning_equipment')
    op.drop_index(op.f('ix_commissioning_subsystem_company_name'), table_name='commissioning_subsystem')
    op.drop_index('ix_comm_subsystem_company_system', table_name='commissioning_subsystem')
    op.drop_table('commissioning_subsystem')
    op.drop_index(op.f('ix_commissioning_system_company_name'), table_name='commissioning_system')
    op.drop_index('ix_comm_system_company_project', table_name='commissioning_system')
    op.drop_table('commissioning_system')
    op.drop_index(op.f('ix_commissioning_membership_company_name'), table_name='commissioning_membership')
    op.drop_index('ix_comm_membership_company_project_role', table_name='commissioning_membership')
    op.drop_table('commissioning_membership')
    op.drop_index(op.f('ix_commissioning_signature_company_name'), table_name='commissioning_signature')
    op.drop_index('ix_comm_signature_company_entity', table_name='commissioning_signature')
    op.drop_table('commissioning_signature')
    op.drop_index(op.f('ix_commissioning_project_company_name'), table_name='commissioning_project')
    op.drop_index('ix_comm_project_company_status', table_name='commissioning_project')
    op.drop_table('commissioning_project')
    op.drop_index(op.f('ix_commissioning_audit_log_company_name'), table_name='commissioning_audit_log')
    op.drop_index('ix_comm_audit_company_entity', table_name='commissioning_audit_log')
    op.drop_table('commissioning_audit_log')
    op.drop_index(op.f('ix_commissioning_attachment_company_name'), table_name='commissioning_attachment')
    op.drop_index('ix_comm_attachment_company_entity', table_name='commissioning_attachment')
    op.drop_table('commissioning_attachment')
        # ### end Alembic commands ###
