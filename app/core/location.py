from __future__ import annotations

import json
import math
import random
from typing import Iterable

from app.core.models import CheckinLocation
from app.utils.time_utils import now_string


CAMPUS_LOCATIONS: dict[str, list[CheckinLocation]] = {
    "宜宾": [
        CheckinLocation("宜宾", "四川省宜宾市翠屏区白沙湾街道大学路四川轻化工大学宜宾校区", 104.674665, 28.804867),
        CheckinLocation("宜宾", "四川省宜宾市翠屏区白沙湾街道四川轻化工大学宜宾校区A4教学楼", 104.673060, 28.803896),
        CheckinLocation("宜宾", "四川省宜宾市翠屏区白沙湾街道四川轻化工大学宜宾校区品正园", 104.674568, 28.804578),
        CheckinLocation("宜宾", "四川省宜宾市翠屏区白沙湾街道四川轻化工大学宜宾校区B6宿舍楼", 104.666897, 28.806461),
    ],
    "李白河": [
        CheckinLocation("李白河", "四川省自贡市大安区大山铺镇四川轻化工大学李白河校区", 104.832512, 29.378790),
        CheckinLocation("李白河", "四川省自贡市大安区大山铺镇四川轻化工大学李白河校区艺雅苑", 104.829322, 29.377620),
        CheckinLocation("李白河", "四川省自贡市大安区大山铺镇艺雅苑1号楼四川轻化工大学李白河校区", 104.828110, 29.377335),
        CheckinLocation("李白河", "四川省自贡市大安区大山铺镇东环路四川轻化工大学李白河校区", 104.827969, 29.376971),
    ],
    "汇东": [
        CheckinLocation("汇东", "四川省自贡市自流井区学苑街道汇雅路15号四川轻化工大学汇东校区", 104.763952, 29.330347),
        CheckinLocation("汇东", "四川省自贡市自流井区学苑街道四川轻化工大学汇东校区学生公寓6栋", 104.763525, 29.330216),
        CheckinLocation("汇东", "四川省自贡市自流井区学苑街道汇勤路四川轻化工大学汇东校区", 104.766355, 29.331665),
        CheckinLocation("汇东", "四川省自贡市自流井区学苑街道南苑街四川轻化工大学汇东校区", 104.761283, 29.329964),
    ],
}

DEFAULT_CAMPUS = "宜宾"


def campus_names() -> list[str]:
    return list(CAMPUS_LOCATIONS.keys())


def locations_for_campus(campus: str | None) -> list[CheckinLocation]:
    return CAMPUS_LOCATIONS.get(campus or "", CAMPUS_LOCATIONS[DEFAULT_CAMPUS])


def default_location(campus: str | None = None) -> CheckinLocation:
    return locations_for_campus(campus)[0]


def random_location_for_campus(campus: str | None = None, random_offset: bool = False, max_meters: float = 35.0) -> CheckinLocation:
    location = random.choice(locations_for_campus(campus))
    if random_offset:
        return offset_location(location, max_meters=max_meters)
    return location


def fixed_location(campus: str | None, index: int = 0) -> CheckinLocation:
    locations = locations_for_campus(campus)
    if not locations:
        return default_location()
    return locations[max(0, min(index, len(locations) - 1))]


def offset_location(location: CheckinLocation, max_meters: float = 35.0) -> CheckinLocation:
    angle = random.uniform(0, math.tau)
    distance = random.uniform(0, max_meters)
    delta_lat = (distance * math.cos(angle)) / 111_320.0
    lng_scale = 111_320.0 * math.cos(math.radians(location.latitude))
    delta_lng = (distance * math.sin(angle)) / lng_scale if lng_scale else 0
    return CheckinLocation(
        campus=location.campus,
        address=location.address,
        longitude=round(location.longitude + delta_lng, 6),
        latitude=round(location.latitude + delta_lat, 6),
    )


def build_checkin_body(task_id: int, location: CheckinLocation) -> dict[str, object]:
    return {
        "id": task_id,
        "qdzt": 1,
        "qdsj": now_string(),
        "isOuted": 0,
        "isLated": 0,
        "dkddPhoto": "",
        "qdddjtdz": location.address,
        "location": location.location_json,
        "txxx": "{}",
    }


def location_summary(location: CheckinLocation) -> str:
    return f"{location.address} ({location.longitude:.6f}, {location.latitude:.6f})"


def serialize_locations(locations: Iterable[CheckinLocation]) -> str:
    return json.dumps([location.__dict__ for location in locations], ensure_ascii=False)
