"""Add revision-controlled Check Sheet templates and template snapshots.

Revision ID: 20261117_0030
Revises: 20261117_0029
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_0030"
down_revision = "20261117_0029"
branch_labels = None
depends_on = None

check_template_type = sa.Enum(
    "PRE_COMM_A", "PRE_COMM_B", "COMM_C", "FUNCTIONAL_TEST",
    name="commissioning_check_template_type",
)


def upgrade():
    op.create_table(
        "commissioning_check_sheet_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("template_code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("sheet_type", check_template_type, nullable=False),
        sa.Column("discipline", sa.String(length=80), nullable=False, server_default="ANY"),
        sa.Column("equipment_type", sa.String(length=100), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_comm_check_template_revision_positive"),
        sa.CheckConstraint("status IN ('DRAFT','APPROVED','RETIRED')",
                           name="ck_comm_check_template_status"),
        sa.CheckConstraint("length(trim(template_code)) > 0",
                           name="ck_comm_check_template_code"),
        sa.ForeignKeyConstraint(
            ["project_id", "company_name"],
            ["commissioning_project.id", "commissioning_project.company_name"],
            name="fk_comm_check_template_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id", "company_name"],
            ["commissioning_check_sheet_template.id", "commissioning_check_sheet_template.company_name"],
            name="fk_comm_check_template_supersedes_tenant",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_name", "project_id", "template_code", "revision",
            name="uq_comm_check_template_revision",
        ),
        sa.UniqueConstraint("id", "company_name", name="uq_comm_check_template_id_company"),
    )
    op.create_index(
        "ix_comm_check_template_project_status",
        "commissioning_check_sheet_template",
        ["company_name", "project_id", "status", "sheet_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commissioning_check_sheet_template_company_name"),
        "commissioning_check_sheet_template", ["company_name"], unique=False,
    )

    with op.batch_alter_table("commissioning_check_sheet") as batch_op:
        batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("template_revision_snapshot", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("template_title_snapshot", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("template_snapshot_json", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            "fk_comm_check_template_tenant",
            "commissioning_check_sheet_template",
            ["template_id", "company_name"], ["id", "company_name"],
        )
        batch_op.create_index(
            "ix_comm_check_sheet_template", ["company_name", "template_id"], unique=False,
        )

    with op.batch_alter_table("commissioning_check_sheet_item") as batch_op:
        batch_op.add_column(sa.Column("acceptance_criteria", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("unit", sa.String(length=40), nullable=True))
        batch_op.add_column(
            sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade():
    with op.batch_alter_table("commissioning_check_sheet_item") as batch_op:
        batch_op.drop_column("mandatory")
        batch_op.drop_column("unit")
        batch_op.drop_column("acceptance_criteria")

    with op.batch_alter_table("commissioning_check_sheet") as batch_op:
        batch_op.drop_index("ix_comm_check_sheet_template")
        batch_op.drop_constraint("fk_comm_check_template_tenant", type_="foreignkey")
        batch_op.drop_column("template_snapshot_json")
        batch_op.drop_column("template_title_snapshot")
        batch_op.drop_column("template_revision_snapshot")
        batch_op.drop_column("template_id")

    op.drop_index(
        op.f("ix_commissioning_check_sheet_template_company_name"),
        table_name="commissioning_check_sheet_template",
    )
    op.drop_index("ix_comm_check_template_project_status", table_name="commissioning_check_sheet_template")
    op.drop_table("commissioning_check_sheet_template")
    check_template_type.drop(op.get_bind(), checkfirst=True)
