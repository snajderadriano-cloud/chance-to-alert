"""Unit tests for regional gazetteer location resolution."""

import pytest
from app.domain.entities import GeoCoordinate
from app.processing.gazetteer import KNOWN_LOCATIONS, RegionalGazetteer


@pytest.fixture
def gazetteer():
    return RegionalGazetteer()


class TestRegionalGazetteer:
    def test_resolve_odesa(self, gazetteer):
        coord = gazetteer.resolve("Одеса")
        assert coord is not None
        assert abs(coord.lat - 46.4825) < 0.01
        assert abs(coord.lon - 30.7233) < 0.01

    def test_resolve_odesa_district_places(self, gazetteer):
        places = ["Чорноморськ", "Фонтанка", "Южне", "Таїрове", "Овідіополь"]
        for p in places:
            coord = gazetteer.resolve(p)
            assert coord is not None, f"Failed to resolve {p}"

    def test_resolve_danube_ports(self, gazetteer):
        danube = ["Ізмаїл", "Рені", "Кілія", "Вилкове"]
        for p in danube:
            coord = gazetteer.resolve(p)
            assert coord is not None, f"Failed to resolve Danube port {p}"

    def test_resolve_transit_and_sea(self, gazetteer):
        coord_sea = gazetteer.resolve("Чорне море")
        assert coord_sea is not None
        coord_crimea = gazetteer.resolve("Крим")
        assert coord_crimea is not None

    def test_extract_places_from_ukrainian_sentence(self, gazetteer):
        text = "3 шахеди з Чорного моря повз Чорноморськ курсом на Одесу!"
        found = gazetteer.extract_places(text)
        assert any("одеса" in p or "одесса" in p for p in found)
        assert any("чорноморськ" in p or "черноморск" in p for p in found)

    def test_resolve_unknown_location(self, gazetteer):
        assert gazetteer.resolve("Лондон") is None
        assert gazetteer.resolve("") is None
