import io
import os
import unittest
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["API_DEVICE_TOKEN"] = "test-device-token-at-least-32-characters"
os.environ["ADMIN_USERNAME"] = "testadmin"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-test-only"
os.environ["UPLOAD_FOLDER"] = "test_uploads"

from app import app, db, VehicleSession, UPLOAD_DIR

class ParkingApiTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        for file in UPLOAD_DIR.iterdir():
            if file.is_file():
                file.unlink()
        self.headers = {"X-Device-Token": os.environ["API_DEVICE_TOKEN"]}

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        for file in UPLOAD_DIR.iterdir():
            if file.is_file():
                file.unlink()

    def upload(self, path, plate, filename="car.jpg"):
        buffer = io.BytesIO()
        fmt = "PNG" if filename.lower().endswith(".png") else "WEBP" if filename.lower().endswith(".webp") else "JPEG"
        Image.new("RGB", (2, 2), color="white").save(buffer, format=fmt)
        buffer.seek(0)
        return self.client.post(path, headers=self.headers, data={
            "plate": plate,
            "image": (buffer, filename),
        }, content_type="multipart/form-data")

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_api_requires_token(self):
        response = self.client.get("/api/vehicles/current")
        self.assertEqual(response.status_code, 401)

    def test_entry_duplicate_and_exit(self):
        first = self.upload("/api/vehicles/entry", "51A-123.45")
        self.assertEqual(first.status_code, 201, first.get_json())
        self.assertEqual(first.get_json()["session"]["plate"], "51A12345")
        duplicate = self.upload("/api/vehicles/entry", "51A12345")
        self.assertEqual(duplicate.status_code, 409)
        current = self.client.get("/api/vehicles/current", headers=self.headers)
        self.assertEqual(current.get_json()["count"], 1)
        exited = self.upload("/api/vehicles/exit", "51A12345", "car_exit.jpg")
        self.assertEqual(exited.status_code, 200, exited.get_json())
        self.assertEqual(exited.get_json()["session"]["status"], "EXITED")
        current = self.client.get("/api/vehicles/current", headers=self.headers)
        self.assertEqual(current.get_json()["count"], 0)

    def test_rejects_bad_extension(self):
        response = self.upload("/api/vehicles/entry", "51A12345", "payload.exe")
        self.assertEqual(response.status_code, 400)

    def test_rejects_disguised_image(self):
        response = self.client.post("/api/vehicles/entry", headers=self.headers, data={
            "plate": "51A12345", "image": (io.BytesIO(b"<html>not image</html>"), "fake.jpg")
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_admin_csrf_and_delete_all_history(self):
        self.upload("/api/vehicles/entry", "51A12345")
        self.upload("/api/vehicles/exit", "51A12345", "exit.jpg")
        login_page = self.client.get("/admin/login")
        self.assertEqual(login_page.status_code, 200)
        with self.client.session_transaction() as sess:
            token = sess["_csrf_token"]
        bad = self.client.post("/admin/login", data={"username": "testadmin", "password": "test-admin-password"})
        self.assertEqual(bad.status_code, 400)
        good = self.client.post("/admin/login", data={"username": "testadmin", "password": "test-admin-password", "csrf_token": token}, follow_redirects=True)
        self.assertEqual(good.status_code, 200)
        dashboard = self.client.get("/admin")
        self.assertIn(b"51A12345", dashboard.data)
        with self.client.session_transaction() as sess:
            token = sess["_csrf_token"]
        deleted = self.client.post("/admin/delete/51A12345", data={"csrf_token": token}, follow_redirects=True)
        self.assertEqual(deleted.status_code, 200)
        with app.app_context():
            self.assertEqual(VehicleSession.query.filter_by(plate="51A12345").count(), 0)
        self.assertFalse(any(UPLOAD_DIR.iterdir()))

if __name__ == "__main__":
    unittest.main(verbosity=2)
