from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Greenhouse, IrrigationCycle, PpeIssue, Zone

User = get_user_model()


class PpeIssueApiTests(APITestCase):
    """喷药日防护领用：字段校验、开放唯一、已关冻结、轮灌互斥、开放核对一致性。"""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass1234")
        self.client.force_authenticate(self.user)
        self.g1 = Greenhouse.objects.create(name="一号棚", location="东区")
        self.g2 = Greenhouse.objects.create(name="二号棚", location="西区")
        self.z1 = Zone.objects.create(greenhouse=self.g1, zone_code="A-01")
        self.z2 = Zone.objects.create(greenhouse=self.g2, zone_code="B-01")
        self.today = date(2026, 9, 21)

    def create_issue(self, **overrides):
        payload = {
            "greenhouseId": self.g1.id,
            "workDate": self.today.isoformat(),
            "suitCount": 4,
            "maskCount": 8,
            "issuer": "张工",
            "status": "open",
        }
        payload.update(overrides)
        return self.client.post("/api/ppe-issues/", payload, format="json")

    def close_issue(self, issue_id):
        return self.client.patch(
            f"/api/ppe-issues/{issue_id}/", {"status": "closed"}, format="json"
        )

    def create_irrigation(self, zone):
        payload = {
            "zoneId": zone.id,
            "startAt": timezone.now().isoformat(),
            "durationMin": 30,
            "waterLiters": "100.00",
            "status": "scheduled",
        }
        return self.client.post("/api/irrigation-cycles/", payload, format="json")

    # --- 字段校验 ---

    def test_counts_must_be_positive_integers(self):
        for bad in (0, -1, -5):
            resp = self.create_issue(suitCount=bad)
            self.assertEqual(resp.status_code, 400, bad)
            resp = self.create_issue(maskCount=bad)
            self.assertEqual(resp.status_code, 400, bad)
        self.assertEqual(PpeIssue.objects.count(), 0)

    def test_counts_reject_non_integer(self):
        resp = self.create_issue(suitCount="abc")
        self.assertEqual(resp.status_code, 400)
        resp = self.create_issue(maskCount=1.5)
        self.assertEqual(resp.status_code, 400)

    def test_create_open_issue_ok(self):
        resp = self.create_issue()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["status"], "open")
        self.assertEqual(resp.data["greenhouseName"], "一号棚")

    # --- 同温室同日只许一张开放单 ---

    def test_only_one_open_issue_per_greenhouse_per_day(self):
        self.assertEqual(self.create_issue().status_code, 201)
        # 同温室同日第二张开放单 → 拒绝
        resp = self.create_issue()
        self.assertEqual(resp.status_code, 400)
        # 关闭后同日可再开
        issue_id = PpeIssue.objects.get().id
        self.assertEqual(self.close_issue(issue_id).status_code, 200)
        self.assertEqual(self.create_issue().status_code, 201)
        # 不同作业日可另开；不同温室同日也可开
        tomorrow = (self.today + timedelta(days=1)).isoformat()
        self.assertEqual(self.create_issue(workDate=tomorrow).status_code, 201)
        self.assertEqual(self.create_issue(greenhouseId=self.g2.id).status_code, 201)

    def test_update_to_open_conflicting_day_rejected(self):
        self.assertEqual(self.create_issue().status_code, 201)
        other_day = (self.today + timedelta(days=1)).isoformat()
        resp = self.create_issue(workDate=other_day)
        self.assertEqual(resp.status_code, 201)
        second_id = resp.data["id"]
        # 把第二张改到与第一张同温室同日且保持开放 → 拒绝
        resp = self.client.patch(
            f"/api/ppe-issues/{second_id}/",
            {"workDate": self.today.isoformat()},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    # --- 已关后禁止改数量 ---

    def test_closed_issue_quantities_frozen(self):
        issue_id = self.create_issue().data["id"]
        self.assertEqual(self.close_issue(issue_id).status_code, 200)
        for field in ("suitCount", "maskCount"):
            resp = self.client.patch(
                f"/api/ppe-issues/{issue_id}/", {field: 99}, format="json"
            )
            self.assertEqual(resp.status_code, 400, field)
        issue = PpeIssue.objects.get(id=issue_id)
        self.assertEqual((issue.suit_count, issue.mask_count), (4, 8))

    def test_open_issue_quantities_editable(self):
        issue_id = self.create_issue().data["id"]
        resp = self.client.patch(
            f"/api/ppe-issues/{issue_id}/", {"suitCount": 6}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PpeIssue.objects.get(id=issue_id).suit_count, 6)

    # --- 领用与轮灌互斥 ---

    def test_open_issue_blocks_new_irrigation_in_same_greenhouse(self):
        self.assertEqual(self.create_issue().status_code, 201)
        resp = self.create_irrigation(self.z1)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(IrrigationCycle.objects.count(), 0)

    def test_other_greenhouse_irrigation_not_blocked(self):
        self.assertEqual(self.create_issue().status_code, 201)
        resp = self.create_irrigation(self.z2)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_irrigation_restored_after_close(self):
        issue_id = self.create_issue().data["id"]
        self.assertEqual(self.create_irrigation(self.z1).status_code, 400)
        self.assertEqual(self.close_issue(issue_id).status_code, 200)
        self.assertEqual(self.create_irrigation(self.z1).status_code, 201)

    def test_existing_irrigation_editable_while_blocked(self):
        self.assertEqual(self.create_irrigation(self.z1).status_code, 201)
        cycle = IrrigationCycle.objects.get()
        self.assertEqual(self.create_issue().status_code, 201)
        resp = self.client.patch(
            f"/api/irrigation-cycles/{cycle.id}/", {"durationMin": 45}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    # --- 温室列表标记与开放核对总数一致 ---

    def test_greenhouse_flag_matches_open_check_totals(self):
        self.assertEqual(self.create_issue().status_code, 201)
        tomorrow = (self.today + timedelta(days=1)).isoformat()
        self.assertEqual(self.create_issue(workDate=tomorrow).status_code, 201)
        self.assertEqual(self.create_issue(greenhouseId=self.g2.id).status_code, 201)

        resp = self.client.get("/api/greenhouses/")
        rows = resp.data["results"] if "results" in resp.data else resp.data
        flagged = [r for r in rows if r["hasOpenPpeIssue"]]
        self.assertEqual({r["id"] for r in flagged}, {self.g1.id, self.g2.id})

        check = self.client.get("/api/ppe-issues/open-check/")
        self.assertEqual(check.status_code, 200)
        self.assertEqual(check.data["openIssueCount"], 3)
        self.assertEqual(check.data["openGreenhouseCount"], len(flagged))
        self.assertEqual(
            set(check.data["greenhouseIds"]), {r["id"] for r in flagged}
        )

        # 全部关闭后：列表无标记，核对总数归零
        for issue in PpeIssue.objects.all():
            self.assertEqual(self.close_issue(issue.id).status_code, 200)
        rows = self.client.get("/api/greenhouses/").data
        rows = rows["results"] if "results" in rows else rows
        self.assertFalse(any(r["hasOpenPpeIssue"] for r in rows))
        check = self.client.get("/api/ppe-issues/open-check/").data
        self.assertEqual(check["openIssueCount"], 0)
        self.assertEqual(check["openGreenhouseCount"], 0)

    def test_open_check_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/ppe-issues/open-check/").status_code, 401)
