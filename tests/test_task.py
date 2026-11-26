"""Database tests for the Task model."""

from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers, sessionmaker

from database import Base, Company, Contingent, Squad, Task, Unit, User


class TaskModelTests(unittest.TestCase):
    """Verify Task persistence, relationships, nullability, and constraints."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        configure_mappers()

        with self.Session() as db:
            self.unit = Unit(name="Task Test Battalion")
            db.add(self.unit)
            db.flush()
            self.contingent = Contingent(unit_id=self.unit.id, name="Task Test Contingent")
            db.add(self.contingent)
            db.flush()
            self.squad = Squad(
                unit_id=self.unit.id,
                contingent_id=self.contingent.id,
                company_id=self._create_company(db).id,
                name="Task Test Squad",
            )
            self.creator = User(
                unit_id=self.unit.id,
                contingent_id=self.contingent.id,
                email="task.creator@cadence.test",
                full_name="Task Creator",
                password_hash="hash",
            )
            self.assignee = User(
                unit_id=self.unit.id,
                contingent_id=self.contingent.id,
                email="task.assignee@cadence.test",
                full_name="Task Assignee",
                password_hash="hash",
            )
            db.add_all([self.squad, self.creator, self.assignee])
            db.commit()
            self.unit_id = self.unit.id
            self.contingent_id = self.contingent.id
            self.squad_id = self.squad.id
            self.creator_id = self.creator.id
            self.assignee_id = self.assignee.id

    def tearDown(self) -> None:
        self.engine.dispose()

    def _create_company(self, db: Session) -> Company:
        company = Company(
            unit_id=self.unit.id,
            contingent_id=self.contingent.id,
            name="Task Test Company",
        )
        db.add(company)
        db.flush()
        return company

    def _task(self, **overrides) -> Task:
        values = {
            "unit_id": self.unit_id,
            "contingent_id": self.contingent_id,
            "squad_id": self.squad_id,
            "created_by_id": self.creator_id,
            "assignee_id": self.assignee_id,
            "title": "Prepare parade checklist",
            "description": "Review equipment before the parade.",
            "due_date": date(2026, 12, 1),
        }
        values.update(overrides)
        return Task(**values)

    def test_create_retrieve_update_and_relationships(self) -> None:
        with self.Session() as db:
            task = self._task()
            db.add(task)
            db.commit()
            task_id = task.id

            stored = db.get(Task, task_id)
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertEqual(stored.status, "TODO")
            self.assertEqual(stored.priority, "MEDIUM")
            self.assertEqual(stored.creator.full_name, "Task Creator")
            self.assertIsNotNone(stored.assignee)
            assert stored.assignee is not None
            self.assertEqual(stored.assignee.full_name, "Task Assignee")
            self.assertIsNotNone(stored.squad)
            assert stored.squad is not None
            self.assertEqual(stored.squad.name, "Task Test Squad")
            self.assertEqual(stored.unit.name, "Task Test Battalion")
            self.assertIsNotNone(stored.contingent)
            assert stored.contingent is not None
            self.assertEqual(stored.contingent.name, "Task Test Contingent")

            stored.status = "IN_PROGRESS"
            stored.priority = "HIGH"
            stored.title = "Updated parade checklist"
            db.commit()
            db.refresh(stored)

            self.assertEqual(stored.status, "IN_PROGRESS")
            self.assertEqual(stored.priority, "HIGH")
            self.assertEqual(stored.title, "Updated parade checklist")

    def test_optional_assignment_scope_and_content_fields(self) -> None:
        with self.Session() as db:
            task = self._task(
                contingent_id=None,
                squad_id=None,
                assignee_id=None,
                description=None,
                due_date=None,
            )
            db.add(task)
            db.commit()
            stored = db.get(Task, task.id)

            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertIsNone(stored.contingent)
            self.assertIsNone(stored.squad)
            self.assertIsNone(stored.assignee)
            self.assertIsNone(stored.description)
            self.assertIsNone(stored.due_date)

    def test_required_fields_and_status_priority_checks(self) -> None:
        required_field_cases = [
            {"unit_id": None},
            {"created_by_id": None},
            {"title": None},
        ]
        for values in required_field_cases:
            with self.subTest(values=values):
                with self.Session() as db:
                    db.add(self._task(**values))
                    with self.assertRaises(IntegrityError):
                        db.commit()

        for values in ({"status": "UNKNOWN"}, {"priority": "UNKNOWN"}):
            with self.subTest(values=values):
                with self.Session() as db:
                    db.add(self._task(**values))
                    with self.assertRaises(IntegrityError):
                        db.commit()

    def test_foreign_keys_reject_unknown_references(self) -> None:
        invalid_references = [
            {"unit_id": "00000000-0000-0000-0000-000000000001"},
            {"contingent_id": "00000000-0000-0000-0000-000000000001"},
            {"squad_id": "00000000-0000-0000-0000-000000000001"},
            {"created_by_id": "00000000-0000-0000-0000-000000000001"},
            {"assignee_id": "00000000-0000-0000-0000-000000000001"},
        ]
        for reference in invalid_references:
            with self.subTest(reference=reference):
                with self.Session() as db:
                    db.add(self._task(**reference))
                    with self.assertRaises(IntegrityError):
                        db.commit()

    def test_foreign_key_delete_policies(self) -> None:
        foreign_keys = inspect(self.engine).get_foreign_keys("task")
        policies = {
            (tuple(fk["constrained_columns"]), tuple(fk["referred_columns"])): fk["options"].get("ondelete")
            for fk in foreign_keys
        }
        self.assertEqual(policies[(("created_by_id",), ("id",))], "RESTRICT")
        self.assertEqual(policies[(("assignee_id",), ("id",))], "SET NULL")
        self.assertEqual(policies[(("squad_id",), ("id",))], "RESTRICT")
        self.assertEqual(policies[(("contingent_id",), ("id",))], "RESTRICT")
        self.assertEqual(policies[(("unit_id",), ("id",))], "RESTRICT")


if __name__ == "__main__":
    unittest.main()
