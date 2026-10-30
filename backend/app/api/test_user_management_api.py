import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId
from fastapi import HTTPException

from app.api.auth import get_user, list_users, update_user_activation
from app.schemas.auth import UserActivationUpdate


class TestUserManagementAPI(unittest.TestCase):
    def setUp(self):
        self.database = MagicMock()
        self.admin_id = str(ObjectId())
        self.user_id = str(ObjectId())
        self.admin = {"_id": ObjectId(self.admin_id), "role": "ADMIN"}
        self.user = {
            "_id": ObjectId(self.user_id),
            "name": "Test User",
            "email": "test@example.com",
            "role": "USER",
            "is_active": True,
            "hashed_password": "must-not-be-returned",
        }

    def test_user_listing_omits_password_hash(self):
        self.database.__getitem__.return_value.find.return_value.sort.return_value = [
            self.user
        ]
        with patch("app.api.auth.get_database", return_value=self.database):
            response = list_users(self.admin)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0].id, self.user_id)
        self.assertFalse(hasattr(response[0], "hashed_password"))
        self.database.__getitem__.return_value.find.assert_called_once_with(
            {}, {"hashed_password": 0}
        )

    def test_get_user_rejects_invalid_and_missing_ids(self):
        with patch("app.api.auth.get_database", return_value=self.database):
            with self.assertRaises(HTTPException) as invalid:
                get_user("invalid", self.admin)
            self.assertEqual(invalid.exception.status_code, 400)

            self.database.__getitem__.return_value.find_one.return_value = None
            with self.assertRaises(HTTPException) as missing:
                get_user(str(ObjectId()), self.admin)
            self.assertEqual(missing.exception.status_code, 404)

    def test_admin_can_deactivate_user_and_audit_event(self):
        users = self.database.__getitem__.return_value
        users.find_one.return_value = self.user.copy()
        with (
            patch("app.api.auth.get_database", return_value=self.database),
            patch("app.api.auth.log_audit_event") as log_event,
        ):
            response = update_user_activation(
                self.user_id,
                UserActivationUpdate(is_active=False),
                self.admin,
            )

        self.assertFalse(response.is_active)
        users.update_one.assert_called_once_with(
            {"_id": ObjectId(self.user_id)},
            {"$set": {"is_active": False}},
        )
        log_event.assert_called_once_with(
            action="USER_ACTIVATION_UPDATED",
            user_id=self.admin_id,
            resource_type="user",
            resource_id=self.user_id,
            details={"is_active": False},
        )

    def test_admin_cannot_deactivate_self(self):
        with patch("app.api.auth.get_database", return_value=self.database):
            with self.assertRaises(HTTPException) as context:
                update_user_activation(
                    self.admin_id,
                    UserActivationUpdate(is_active=False),
                    self.admin,
                )

        self.assertEqual(context.exception.status_code, 400)
        self.database.__getitem__.assert_not_called()


if __name__ == "__main__":
    unittest.main()
