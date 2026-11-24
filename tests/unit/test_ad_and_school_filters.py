"""Unit tests for advertising, spam, noise filtering, and school remote learning analysis."""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.processing.ad_filter import ContentFilter, PostClassification
from app.processing.school_analyzer import RemoteStudyStatus, SchoolRemoteAnalyzer
from app.processing.threat_parser import ThreatParser


@pytest.fixture
def content_filter():
    return ContentFilter()


@pytest.fixture
def school_analyzer():
    return SchoolRemoteAnalyzer()


@pytest.fixture
def threat_parser():
    return ThreatParser()


class TestContentFilter:
    def test_explicit_ad_rejection(self, content_filter):
        text = "#РЕКЛАМА! Лише сьогодні знижка 50% на піцу в Одесі! Замовляйте за промокодом ODESA."
        res = content_filter.filter_post(text, "xydessa_live")
        assert res.is_threat_relevant is False
        assert res.classification == PostClassification.ADVERTISEMENT
        assert res.rejection_reason is not None

    def test_casino_and_gambling_rejection(self, content_filter):
        text = "Нове онлайн-казино дарує 250 фріспінів без депозиту! Забирай бонус за посиланням."
        res = content_filter.filter_post(text, "UaOnlii")
        assert res.is_threat_relevant is False
        assert res.classification == PostClassification.SCAM_OR_CASINO

    def test_crypto_scam_rejection(self, content_filter):
        text = "Схема заробітку від 1500$ на день! Безкоштовні USDT та роздача крипти кожному."
        res = content_filter.filter_post(text, "times_ukraina")
        assert res.is_threat_relevant is False
        assert res.classification == PostClassification.SCAM_OR_CASINO

    def test_clickbait_invite_trap_rejection(self, content_filter):
        text = "Шокуючі кадри нічних подій! Читати продовження за посиланням: https://t.me/+NqpMx-Dd0TQzZTcy"
        res = content_filter.filter_post(text, "voynareal")
        assert res.is_threat_relevant is False
        assert res.classification == PostClassification.CLICKBAIT_SPAM

    def test_general_news_rejection(self, content_filter):
        text = "Президент провів зустріч з міністром фінансів щодо держбюджету на наступний рік."
        res = content_filter.filter_post(text, "times_ukraina")
        assert res.is_threat_relevant is False
        assert res.classification == PostClassification.GENERAL_NEWS

    def test_genuine_threat_post_in_news_channel_accepted(self, content_filter):
        text = "⚡ В Одесі пролунав вибух! Працює ППО по шахедам над морем!"
        res = content_filter.filter_post(text, "xydessa_live")
        assert res.is_threat_relevant is True
        assert res.classification == PostClassification.THREAT_SIGNAL
        assert any(k in ["вибух", "ппо", "шахедам"] for k in res.detected_keywords)

    def test_parser_ignores_filtered_ads(self, threat_parser):
        ad_text = "Знижки на одяг у ТЦ Європа до -70%! #реклама"
        signals = threat_parser.parse(ad_text, channel="xydessa_live")
        assert len(signals) == 0


class TestSchoolRemoteAnalyzer:
    def test_official_remote_decision_dep_osvity(self, school_analyzer):
        text = "Шановні батьки та педагоги! Завтра, 24 листопада, усі школи Одеси навчаються дистанційно."
        res = school_analyzer.analyze_post(text, channel="dep_osvity")
        assert res.is_remote is True
        assert res.status == RemoteStudyStatus.OFFICIAL_REMOTE
        assert res.remote_probability_percent == 100
        assert "ДИСТАНЦІЙНО" in res.headline

    def test_blackout_and_infrastructure_remote_detection(self, school_analyzer):
        # Post matching the user's actual screenshot from @svet_odessa
        text = (
            "Близько половини міста досі без світла, 40% - без тепла. "
            "Води немає лише на верхніх поверхах. "
            "Усі школярі сьогодні навчаються дистанційно. Електротранспорт не курсує."
        )
        res = school_analyzer.analyze_post(text, channel="svet_odessaa")
        assert res.is_remote is True
        assert res.status == RemoteStudyStatus.OFFICIAL_REMOTE
        assert res.remote_probability_percent == 100

    def test_return_to_in_person_classes(self, school_analyzer):
        text = "З понеділка одеські школи повертаються до очного навчання у звичайному режимі."
        res = school_analyzer.analyze_post(text, channel="dep_osvity")
        assert res.is_remote is False
        assert res.status == RemoteStudyStatus.NORMAL_IN_PERSON
        assert res.remote_probability_percent <= 10


def test_api_school_status_endpoint():
    with TestClient(app) as client:
        # 1. Check baseline
        resp = client.get("/api/v1/school/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_remote" in data
        assert "remote_probability_percent" in data
        assert "headline" in data

        # 2. Simulate post from dep_osvity
        post_payload = {
            "text": "Увага! Через погодні умови та безпекову ситуацію школи Одеси переходять на дистанційне навчання.",
            "channel": "dep_osvity",
        }
        sim_resp = client.post("/api/v1/simulate", json=post_payload)
        assert sim_resp.status_code == 200

        # 3. Verify school status updated
        updated_resp = client.get("/api/v1/school/status")
        assert updated_resp.status_code == 200
        updated_data = updated_resp.json()
        assert updated_data["is_remote"] is True
        assert updated_data["status"] == "OFFICIAL_REMOTE"
        assert updated_data["remote_probability_percent"] == 100

        # 4. Verify also included in /api/v1/probability
        prob_resp = client.get("/api/v1/probability")
        assert prob_resp.status_code == 200
        prob_data = prob_resp.json()
        assert "school_status" in prob_data
        assert prob_data["school_status"]["is_remote"] is True
