import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from app.schemas.activity_log import ActivityLogChange


FIELD_LABELS = {
    "key": "Mã công việc", "title": "Tiêu đề", "description": "Mô tả",
    "type": "Loại công việc", "priority": "Ưu tiên", "status": "Trạng thái",
    "position": "Thứ tự trong cột", "startDate": "Ngày bắt đầu", "endDate": "Ngày kết thúc",
    "assigneeIds": "Người thực hiện", "reviewerId": "Người duyệt",
    "overdueReason": "Lý do quá hạn", "acceptanceResult": "Kết quả nghiệm thu",
    "completedAt": "Thời điểm hoàn thành", "deletedAt": "Thời điểm xóa",
    "comment": "Bình luận", "startTime": "Bắt đầu ghi giờ", "endTime": "Kết thúc ghi giờ",
    "note": "Nội dung ghi giờ",
}
VALUE_LABELS = {
    "priority": {"urgent": "Khẩn cấp", "high": "Cao", "medium": "Trung bình", "low": "Thấp"},
    "type": {"epic": "Epic", "story": "Story", "task": "Công việc", "bug": "Lỗi"},
    "status": {"backlog": "Cần làm", "in-progress": "Đang làm", "review": "Đang duyệt", "done": "Hoàn thành"},
}


def change_values(value):
    if isinstance(value, dict) and "old" in value and "new" in value:
        return True, value["old"], value["new"]
    return False, None, value


def referenced_users(changes: dict) -> set[uuid.UUID]:
    ids = set()
    for field in ("assigneeIds", "reviewerId"):
        _, old, new = change_values(changes.get(field))
        for value in (old, new):
            for item in value if isinstance(value, list) else [value]:
                try:
                    ids.add(uuid.UUID(str(item)))
                except (ValueError, TypeError):
                    pass
    return ids


def format_value(field: str, value, names: dict[str, str], statuses: dict[str, str], zone: ZoneInfo) -> str | None:
    if value is None or value == "" or value == []:
        return None
    if field in ("assigneeIds", "reviewerId"):
        values = value if isinstance(value, list) else [value]
        return ", ".join(names.get(str(uid), "Người dùng không còn tồn tại") for uid in values)
    if field == "comment":
        return str(value.get("body", "")) if isinstance(value, dict) else str(value)
    text = str(value)
    if field in VALUE_LABELS:
        labels = {**VALUE_LABELS[field], **(statuses if field == "status" else {})}
        return labels.get(text, text)
    try:
        if field in ("startDate", "endDate"):
            return date.fromisoformat(text).strftime("%d/%m/%Y")
        if field in ("completedAt", "deletedAt", "startTime", "endTime"):
            instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=timezone.utc)
            return instant.astimezone(zone).strftime("%d/%m/%Y %H:%M:%S")
        if field == "position":
            return format(Decimal(text).normalize(), "f")
    except (ValueError, InvalidOperation):
        pass
    return text


def describe_changes(changes: dict, names: dict[str, str], statuses: dict[str, str], timezone_name: str):
    zone = ZoneInfo(timezone_name)
    details = []
    for field, label in FIELD_LABELS.items():
        if field not in changes:
            continue
        has_previous, old, new = change_values(changes[field])
        details.append(ActivityLogChange(
            field=field, label=label, hasPreviousValue=has_previous,
            oldValue=format_value(field, old, names, statuses, zone),
            newValue=format_value(field, new, names, statuses, zone),
        ))
    return details
