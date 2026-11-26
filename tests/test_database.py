"""Database layer tests for CADENCE models, constraints, get_db(), and seeding."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers, sessionmaker

from database import (
    ApprovalStep,
    AttendanceRecord,
    AttendanceSheet,
    AttendanceStatus,
    AuditLog,
    Base,
    CadetProfile,
    Company,
    Contingent,
    ExamLevel,
    ExamResource,
    LeaveRequest,
    LeaveStatus,
    Notice,
    NoticeReceipt,
    OtpCode,
    Parade,
    Rank,
    RankHistory,
    RefreshToken,
    Role,
    RoleAssignment,
    ScopeType,
    SheetStatus,
    Squad,
    Unit,
    User,
    get_db,
    init_engine,
)
from database.seed import seed_database


EXPECTED_TABLES = {
    "unit",
    "contingent",
    "company",
    "squad",
    "user",
    "cadet_profile",
    "role_assignment",
    "rank_history",
    "parade",
    "attendance_sheet",
    "attendance_record",
    "leave_request",
    "approval_step",
    "notice",
    "notice_receipt",
    "exam_resource",
    "audit_log",
    "refresh_token",
    "otp_code",
    "task",
}


class DatabaseLayerTests(unittest.TestCase):
    """Verify schema metadata, constraints, session lifecycle, and idempotent seed."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_all_20_tables_and_mappers_registered(self) -> None:
        configure_mappers()
        self.assertEqual(set(Base.metadata.tables.keys()), EXPECTED_TABLES)
        inspector = inspect(self.engine)
        self.assertEqual(set(inspector.get_table_names()), EXPECTED_TABLES)

    def test_frozen_enum_values_match_contract(self) -> None:
        self.assertEqual([e.value for e in Role], ["CADET", "CADET_LEADER", "JUO", "ANO", "CO"])
        self.assertEqual(
            [e.value for e in Rank],
            ["CADET", "LCPL", "CPL", "SGT", "CQMS", "CSM", "JUO", "SUO", "OFFICER"],
        )
        self.assertEqual(
            [e.value for e in ScopeType],
            ["SELF", "SQUAD", "COMPANY", "CONTINGENT", "BATTALION"],
        )
        self.assertEqual(
            [e.value for e in AttendanceStatus],
            ["PRESENT", "ABSENT", "LEAVE", "LATE"],
        )
        self.assertEqual(
            [e.value for e in SheetStatus],
            ["DRAFT", "SUBMITTED", "JUO_REVIEWED", "ANO_APPROVED", "LOCKED"],
        )
        self.assertEqual(
            [e.value for e in LeaveStatus],
            [
                "PENDING_LEADER",
                "PENDING_JUO",
                "PENDING_ANO",
                "PENDING_CO",
                "APPROVED",
                "REJECTED",
                "CANCELLED",
            ],
        )
        self.assertEqual([e.value for e in ExamLevel], ["A", "B", "C"])

    def _create_base_org_and_cadet(self, db: Session) -> tuple[Unit, Contingent, Company, Squad, User, CadetProfile]:
        unit = Unit(name="Test Battalion", code="TB-01")
        db.add(unit)
        db.flush()

        contingent = Contingent(unit_id=unit.id, name="Alpha")
        db.add(contingent)
        db.flush()

        company = Company(unit_id=unit.id, contingent_id=contingent.id, name="Coy 1")
        db.add(company)
        db.flush()

        squad = Squad(unit_id=unit.id, contingent_id=contingent.id, company_id=company.id, name="Squad 1")
        db.add(squad)
        db.flush()

        user = User(
            unit_id=unit.id,
            contingent_id=contingent.id,
            email="test.cadet@cadence.test",
            full_name="Test Cadet",
            password_hash="hashed-value",
            role=Role.CADET,
        )
        db.add(user)
        db.flush()

        cadet = CadetProfile(
            unit_id=unit.id,
            contingent_id=contingent.id,
            company_id=company.id,
            squad_id=squad.id,
            user_id=user.id,
            cadet_no="NCC-2026-9999",
            rank=Rank.CADET,
        )
        db.add(cadet)
        db.flush()
        return unit, contingent, company, squad, user, cadet

    def test_unique_and_check_constraints(self) -> None:
        with self.Session() as db:
            unit, contingent, company, squad, user, cadet = self._create_base_org_and_cadet(db)
            db.commit()

            # 1. Duplicate cadet_profile per user is rejected.
            dup_profile = CadetProfile(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                squad_id=squad.id,
                user_id=user.id,
                cadet_no="NCC-2026-9998",
                rank=Rank.CADET,
            )
            db.add(dup_profile)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 2. Unique parade + squad on attendance_sheet.
            parade = Parade(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                title="Morning Drill",
                parade_date=date(2026, 11, 25),
                created_by_id=user.id,
            )
            db.add(parade)
            db.flush()
            sheet = AttendanceSheet(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                parade_id=parade.id,
                squad_id=squad.id,
            )
            db.add(sheet)
            db.commit()

            dup_sheet = AttendanceSheet(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                parade_id=parade.id,
                squad_id=squad.id,
            )
            db.add(dup_sheet)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 3. Check constraint: leave_request to_date >= from_date.
            bad_leave = LeaveRequest(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                squad_id=squad.id,
                cadet_id=cadet.id,
                from_date=date(2026, 12, 5),
                to_date=date(2026, 12, 1),
                reason="Invalid range",
            )
            db.add(bad_leave)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 4. Check constraint: otp_code attempt_count >= 0.
            bad_otp = OtpCode(
                unit_id=unit.id,
                contingent_id=contingent.id,
                user_id=user.id,
                code_hash="hash",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                attempt_count=-1,
            )
            db.add(bad_otp)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 5. Unique refresh_token token_hash.
            rt1 = RefreshToken(
                unit_id=unit.id,
                contingent_id=contingent.id,
                user_id=user.id,
                token_hash="unique-hash-1",
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add(rt1)
            db.commit()
            rt2 = RefreshToken(
                unit_id=unit.id,
                contingent_id=contingent.id,
                user_id=user.id,
                token_hash="unique-hash-1",
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add(rt2)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 6. Unique cadet_no on cadet_profile.
            user2 = User(
                unit_id=unit.id,
                contingent_id=contingent.id,
                email="test.cadet2@cadence.test",
                full_name="Test Cadet 2",
                password_hash="hashed-value",
                role=Role.CADET,
            )
            db.add(user2)
            db.flush()
            dup_cadet_no = CadetProfile(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                squad_id=squad.id,
                user_id=user2.id,
                cadet_no="NCC-2026-9999",
                rank=Rank.CADET,
            )
            db.add(dup_cadet_no)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 7. Unique attendance_record (sheet_id, cadet_id).
            rec1 = AttendanceRecord(
                unit_id=unit.id,
                contingent_id=contingent.id,
                sheet_id=sheet.id,
                cadet_id=cadet.id,
                status=AttendanceStatus.PRESENT,
            )
            db.add(rec1)
            db.commit()
            rec2 = AttendanceRecord(
                unit_id=unit.id,
                contingent_id=contingent.id,
                sheet_id=sheet.id,
                cadet_id=cadet.id,
                status=AttendanceStatus.ABSENT,
            )
            db.add(rec2)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 8. Unique notice_receipt (notice_id, user_id).
            notice = Notice(
                unit_id=unit.id,
                contingent_id=contingent.id,
                author_id=user.id,
                title="Drill Notice",
                body="Parade at 0600.",
                target_scope_type=ScopeType.CONTINGENT,
                target_scope_id=contingent.id,
            )
            db.add(notice)
            db.flush()
            nr1 = NoticeReceipt(
                unit_id=unit.id,
                contingent_id=contingent.id,
                notice_id=notice.id,
                user_id=user.id,
            )
            db.add(nr1)
            db.commit()
            nr2 = NoticeReceipt(
                unit_id=unit.id,
                contingent_id=contingent.id,
                notice_id=notice.id,
                user_id=user.id,
            )
            db.add(nr2)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

            # 9. Check constraint: attendance_sheet version >= 1.
            parade2 = Parade(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                title="Evening Drill",
                parade_date=date(2026, 11, 26),
                created_by_id=user.id,
            )
            db.add(parade2)
            db.flush()
            bad_sheet = AttendanceSheet(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                parade_id=parade2.id,
                squad_id=squad.id,
                version=0,
            )
            db.add(bad_sheet)
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

    def test_seed_is_idempotent_and_meets_contract_counts(self) -> None:
        with self.Session() as db:
            first_counts = seed_database(db)
            second_counts = seed_database(db)

        self.assertEqual(first_counts, second_counts)
        self.assertEqual(first_counts["units"], 1)
        self.assertEqual(first_counts["contingents"], 2)
        self.assertEqual(first_counts["companies"], 4)
        self.assertEqual(first_counts["squads"], 8)
        self.assertEqual(first_counts["cadets"], 60)
        self.assertEqual(first_counts["users"], 62)

        with self.Session() as db:
            emails = {
                row[0]
                for row in db.query(User.email)
                .filter(
                    User.email.in_(
                        [
                            "cadet@cadence.test",
                            "leader@cadence.test",
                            "juo@cadence.test",
                            "ano@cadence.test",
                            "co@cadence.test",
                        ]
                    )
                )
                .all()
            }
            self.assertEqual(len(emails), 5)

    def test_get_db_yields_and_closes_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_get_db.sqlite")
            init_engine(f"sqlite:///{db_path}")
            gen = get_db()
            session = next(gen)
            self.assertIsInstance(session, Session)
            self.assertEqual(session.execute(text("SELECT 1")).scalar_one(), 1)
            with self.assertRaises(StopIteration):
                next(gen)
            # Dispose file engine before tempdir cleanup on Windows.
            from database import session as db_session_module

            if db_session_module.engine is not None:
                db_session_module.engine.dispose()

    def test_relationships_auth_rotation_and_audit_json(self) -> None:
        from zoneinfo import ZoneInfo

        with self.Session() as db:
            unit, contingent, company, squad, user, cadet = self._create_base_org_and_cadet(db)

            assignment = RoleAssignment(
                unit_id=unit.id,
                contingent_id=contingent.id,
                user_id=user.id,
                role=Role.CADET,
                scope_type=ScopeType.SELF,
                scope_id=user.id,
            )
            rank_entry = RankHistory(
                unit_id=unit.id,
                contingent_id=contingent.id,
                cadet_id=cadet.id,
                from_rank=Rank.CADET,
                to_rank=Rank.LCPL,
                changed_by_id=user.id,
                reason="Promotion",
            )
            leave = LeaveRequest(
                unit_id=unit.id,
                contingent_id=contingent.id,
                company_id=company.id,
                squad_id=squad.id,
                cadet_id=cadet.id,
                from_date=date(2026, 12, 1),
                to_date=date(2026, 12, 3),
                reason="Medical",
            )
            db.add_all([assignment, rank_entry, leave])
            db.flush()

            step = ApprovalStep(
                unit_id=unit.id,
                contingent_id=contingent.id,
                leave_request_id=leave.id,
                actor_id=user.id,
                action="FORWARD",
                from_status=LeaveStatus.PENDING_LEADER.value,
                to_status=LeaveStatus.PENDING_JUO.value,
            )
            resource = ExamResource(
                unit_id=unit.id,
                contingent_id=None,
                title="B Certificate Guide",
                level=ExamLevel.B,
                url="https://example.org/b-cert",
                created_by_id=user.id,
            )
            audit = AuditLog(
                unit_id=unit.id,
                contingent_id=contingent.id,
                actor_id=user.id,
                action="rank.assign",
                entity_type="cadet_profile",
                entity_id=cadet.id,
                before_data={"rank": "CADET"},
                after_data={"rank": "LCPL"},
                reason="Promotion",
            )
            new_rt = RefreshToken(
                unit_id=unit.id,
                contingent_id=contingent.id,
                user_id=user.id,
                token_hash="hash-new",
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add_all([step, resource, audit, new_rt])
            db.flush()

            old_rt = RefreshToken(
                unit_id=unit.id,
                contingent_id=contingent.id,
                user_id=user.id,
                token_hash="hash-old",
                family_id=new_rt.family_id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                revoked_at=datetime.now(timezone.utc),
                replaced_by_token_id=new_rt.id,
            )
            otp = OtpCode(
                unit_id=unit.id,
                contingent_id=contingent.id,
                user_id=user.id,
                code_hash="otp-hash-1",
                purpose="mfa_email",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                consumed_at=datetime.now(timezone.utc),
                attempt_count=1,
            )
            db.add_all([old_rt, otp])
            db.commit()

            db.refresh(leave)
            db.refresh(old_rt)
            self.assertEqual(len(leave.approval_steps), 1)
            self.assertEqual(old_rt.replaced_by.id, new_rt.id)
            self.assertEqual(audit.after_data["rank"], "LCPL")
            self.assertEqual(ZoneInfo("Asia/Kolkata").key, "Asia/Kolkata")

    def test_seed_hashes_passwords_and_separates_rank_and_role(self) -> None:
        with self.Session() as db:
            seed_database(db)
            users = db.query(User).all()
            self.assertTrue(all(u.password_hash.startswith("$pbkdf2-sha256$") for u in users))
            leader = db.query(User).filter(User.email == "leader@cadence.test").one()
            self.assertEqual(leader.role, Role.CADET_LEADER)
            self.assertEqual(leader.cadet_profile.rank, Rank.CPL)
            co = db.query(User).filter(User.email == "co@cadence.test").one()
            self.assertEqual(co.role, Role.CO)
            self.assertIsNone(co.contingent_id)
            self.assertIsNone(co.cadet_profile)


@unittest.skipUnless(
    os.getenv("DATABASE_URL", "").strip(),
    "DATABASE_URL is required for PostgreSQL integration tests.",
)
class PostgreSQLIntegrationTests(unittest.TestCase):
    """Read-only integration checks against the configured PostgreSQL database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = init_engine()
        cls.inspector = inspect(cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def test_postgresql_catalog_and_migration_match_contract(self) -> None:
        self.assertEqual(self.engine.dialect.name, "postgresql")

        application_tables = set(self.inspector.get_table_names()) - {"alembic_version"}
        self.assertEqual(application_tables, EXPECTED_TABLES)

        enum_names = {enum["name"] for enum in self.inspector.get_enums()}
        self.assertEqual(
            enum_names,
            {
                "role_enum",
                "rank_enum",
                "scope_type_enum",
                "attendance_status_enum",
                "sheet_status_enum",
                "leave_status_enum",
                "exam_level_enum",
            },
        )

        with self.engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            database_name = connection.execute(text("SELECT current_database()")).scalar_one()
            current_user = connection.execute(text("SELECT current_user")).scalar_one()
            server_version = connection.execute(text("SHOW server_version")).scalar_one()

        self.assertTrue(revision)
        self.assertEqual(database_name, "cadence_db")
        self.assertEqual(current_user, "postgres")
        self.assertTrue(str(server_version).startswith("19."))

    def test_postgresql_seed_counts_and_session_lifecycle(self) -> None:
        with Session(bind=self.engine) as db:
            self.assertEqual(db.query(Unit).count(), 1)
            self.assertEqual(db.query(Contingent).count(), 2)
            self.assertEqual(db.query(Company).count(), 4)
            self.assertEqual(db.query(Squad).count(), 8)
            self.assertEqual(db.query(CadetProfile).count(), 60)
            self.assertEqual(db.query(User).count(), 62)

            account_count = (
                db.query(User)
                .filter(
                    User.email.in_(
                        [
                            "cadet@cadence.test",
                            "leader@cadence.test",
                            "juo@cadence.test",
                            "ano@cadence.test",
                            "co@cadence.test",
                        ]
                    )
                )
                .count()
            )
            self.assertEqual(account_count, 5)


if __name__ == "__main__":
    unittest.main()
