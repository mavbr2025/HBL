from datetime import date

from mtm_hbl.config import AppConfig


def format_guatemala_issue_date(value: date, app_config: AppConfig) -> str:
    config = app_config.date_formats["Guatemala"]
    month_name = config["months"][value.month]
    return config["format"].format(
        place=config["issue_place"],
        day=value.day,
        month_name=month_name,
        year=value.year,
    )
