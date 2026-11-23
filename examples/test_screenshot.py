import asyncio
import base64
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "app" / "__init__.py").is_file()
)
sys.path.insert(0, str(ROOT))

from app.agents.json_utils import parse_json_response
from app.agents.llm_client import get_client
from app.bootstrap import create_executor, create_platform_session
from app.browser.browser_manager import BrowserManager
from app.config import get_settings
from app.tools.browser.screenshot import default_screenshot_dir

PLATFORM = "amazon"
SHOW_BROWSER = False
TASK_INTERVAL_SECONDS = 3
LOCATION_ATTEMPTS = 2
TASKS = [
    {
        "sku": "B07Q3DYMRD",
        "url": "https://www.amazon.de/dp/B07Q3DYMRD?language=en-GB",
        "market": "DE",
    },
     {
        "sku": "B07Q3DYMRD",
        "url": "https://www.amazon.it/dp/B07Q3DYMRD?language=en-GB",
        "market": "IT",

    }, {
        "sku": "B0CVVHN1GQ",
        "url": "https://www.amazon.de/dp/B0CVVHN1GQ?th=1&language=en-GB",
        "market": "DE",
    }
    , {
        "sku": "B0CSF7XYJY",
        "url": "https://www.amazon.de/dp/B0CSF7XYJY?th=1&language=en-GB",
        "market": "DE",
    }, {
        "sku": "B0CFLQ256C",
        "url": "https://www.amazon.de/dp/B0CFLQ256C?th=1&language=en-GB",
        "market": "DE",
    }, {
        "sku": "B0CY5FS7V9",
        "url": "https://www.amazon.de/dp/B0CY5FS7V9?th=1&language=en-GB",
        "market": "DE",
    }, {
        "sku": "B08CHBBB9D",
        "url": "https://www.amazon.fr/-/en/Childrens-Bookcase-Lockable-Storage-Children/dp/B08CHBBB9D/ref=sr_1_1?crid=2SXGBURMMLOEJ&dib=eyJ2IjoiMSJ9.8I6C43HByqCMEA4-B8Sbpg.SCFzhqv-dHn6ZI89hd8cCoRM0GAu5glpp8w2uQ0a_hI&dib_tag=se&keywords=B08CHBBB9D&qid=1792390374&sprefix=b08chbbb9d%2Caps%2C384&sr=8-1",
        "market": "FR",
    }, {
        "sku": "B08CHBBB9D",
        "url": "https://www.amazon.it/WOLTU-Libreria-Scaffale-Organizzatore-Cameretta/dp/B08CHBBB9D/ref=sr_1_1?__mk_it_IT=%C3%85M%C3%85%C5%BD%C3%95%C3%91&dib=eyJ2IjoiMSJ9.8I6C43HByqCMEA4-B8Sbpg.hWxkx8VMw6C-adAeR-yVHbp7YjoOw8OS9WQj9M785D4&dib_tag=se&keywords=B08CHBBB9D&qid=1792390414&sr=8-1",
        "market": "IT",
    }, {
        "sku": "B0CLLP37J7",
        "url": "https://www.amazon.fr/dp/B0CLLP37J7?th=1&language=en-GB",
        "market": "FR",
    }, {
        "sku": "B0CPCX2KWT",
        "url": "https://www.amazon.de/dp/B0CPCX2KWT?th=1&language=en-GB",
        "market": "DE",
    }
]

# 亚马逊站点配送邮编。键是站点国家码，打开对应域名时自动使用。
MARKET_POSTAL_CODES = {
    "DE": "10115",
    "IT": "00174",
    "FR": "75001",
    "ES": "28001",
    "UK": "SW1A 1AA",
    "NL": "1012",
    "SE": "111 22",
    "BE": "1049",
    "PL": "00-001",
}
BUTTON_NAME = "Add to Basket"
LINK_MISSING_REASON = "链接不存在"
_ASIN_IN_PATH = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)")
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC = "alert-basket"
# MQ_SEND_MODE = "each"
MQ_SEND_MODE = "batch"



def asin_from_url(url: str) -> str:
    match = _ASIN_IN_PATH.search(urlparse(url or "").path)
    return match.group(1).upper() if match else ""


def postal_code_for_market(market: str) -> str:
    code = market.upper()
    if code not in MARKET_POSTAL_CODES:
        known = ", ".join(MARKET_POSTAL_CODES)
        raise KeyError(f"unsupported market: {market}. known: {known}")
    return MARKET_POSTAL_CODES[code]


def hourly_screenshot_dir(platform: str) -> Path:
    now = datetime.now()
    return default_screenshot_dir(platform) / f"{now:%Y-%m-%d}" / f"{now:%H}-{now:%M}-{now:%S}"


async def button_in_screenshot(image_path: str, button_name: str, market: str) -> dict:
    """把截图发给大模型，判断画面里是否有指定按钮名称。"""
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode()
    prompt = f"""
请查看这张网页截图，判断画面中是否出现名为「{button_name}」的按钮或可点击文字。
名称要按可见文字匹配，大小写和首尾空格可以忽略，不要根据猜测补全没有显示的按钮。

只返回 JSON，不要 markdown：
{{"present": true, "button_name": "{button_name}", "reason": "简短说明看到了什么"}}
"""
    settings = get_settings()

    def _call():
        response = get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded}",
                            },
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content

    text = await asyncio.to_thread(_call)
    data = parse_json_response(text)
    return {
        "present": bool(data.get("present")),
        "button_name": button_name,
        "market": market,
        "reason": data.get("reason", ""),
    }


def build_alert(item: dict) -> dict:
    return {
        "biz_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "warning_type": "购物车缺失",
        "sku": item["sku"],
        "market": item["market"],
        "url": item["url"],
        "present": item["present"],
        "button_name": BUTTON_NAME,
        "reason": item.get("reason", ""),
        "error": item.get("error", ""),
        "oper_supervisor_name": "Katie Wang",
        "group": "1",
    }


def publish_alert(message: dict | list) -> None:
    """把按钮判断结果投递到 Kafka topic alert-basket。"""
    # Kafka belongs to the post-MVP production path. Keep this legacy example
    # importable without installing kafka-python for the local MVP.
    from kafka import KafkaProducer

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
    )
    try:
        producer.send(KAFKA_TOPIC, value=message).get(timeout=10)
    finally:
        producer.flush()
        producer.close()


async def apply_market_location(executor, session, url: str, postal_code: str):
    """打开商品页并设置邮编。地址栏刷新慢时重新进入页面再试一次。"""
    location = None
    for attempt in range(LOCATION_ATTEMPTS):
        if attempt:
            await executor.execute("goto", session, url=url)
            await executor.execute(
                "wait",
                session,
                state="domcontentloaded",
                timeout=20000,
            )
        location = await executor.execute(
            "set_location",
            session,
            postal_code=postal_code,
        )
        detail = location.data if location.success else {
            "error": location.error,
            "data": location.data,
        }
        print("LOCATION:", detail)
        if location.success:
            return location
    return location


async def run_sku(
    executor,
    session,
    market: str,
    sku: str,
    url: str,
    postal_code: str,
    output_dir: Path,
) -> dict:
    item = {
        "sku": sku,
        "market": market,
        "url": url,
        "postal_code": postal_code,
        "success": False,
        "present": None,
        "error": "",
    }

    try:
        await executor.execute("goto", session, url=url)
        await executor.execute(
            "wait",
            session,
            state="domcontentloaded",
            timeout=20000,
        )

        landed = session.page.url if session.page is not None else ""
        landed_sku = asin_from_url(landed)
        if landed_sku and landed_sku != sku.upper():
            print("REDIRECT:", landed)
            item["success"] = True
            item["present"] = False
            item["reason"] = LINK_MISSING_REASON
            return item

        result = await executor.execute(
            "screenshot",
            session,
            name=f"amazon_{market.lower()}_{postal_code}_{sku}",
            dir=str(output_dir),
            market=market,
        )
        print("SCREENSHOT:", result.data if result.success else result.error)
        if not result.success:
            item["error"] = result.error or "screenshot failed"
            return item

        check = await button_in_screenshot(result.data["path"], BUTTON_NAME, market)
        print("BUTTON:", check)
        item["success"] = True
        item["present"] = check["present"]
        item["reason"] = check["reason"]
        item["screenshot"] = result.data.get("path")
        item["url"] = result.data.get("url") or url
    except Exception as error:
        item["error"] = str(error)

    return item


def summarize(items: list[dict]) -> dict:
    return {
        "total": len(items),
        "success": sum(1 for item in items if item["success"]),
        "failed": sum(1 for item in items if not item["success"]),
        "button_present": sum(1 for item in items if item["present"] is True),
        "button_missing": sum(1 for item in items if item["present"] is False),
        "items": items,
    }


async def send_alerts(items: list[dict], mq_send_mode: str) -> None:
    messages = [build_alert(item) for item in items]
    if not messages:
        return
    if mq_send_mode == "batch":
        await asyncio.to_thread(publish_alert, messages)
        print("KAFKA BATCH:", messages)
        return
    for message in messages:
        await asyncio.to_thread(publish_alert, message)
        print("KAFKA:", message)


async def main(
    show_browser: bool = SHOW_BROWSER,
    mq_send_mode: str = MQ_SEND_MODE,
    tasks: list[dict] | None = None,
):

    bm = BrowserManager(headless=not show_browser)
    items = []
    try:
        await bm.start()

        executor = create_executor()
        session, _platform = await create_platform_session(bm, PLATFORM, executor=executor)
        output_dir = hourly_screenshot_dir(PLATFORM)
        print("OUTPUT:", output_dir)

        located_market = ""
        pending_alerts = []
        task_list = TASKS if tasks is None else tasks
        for index, task in enumerate(task_list):
            if index:
                await asyncio.sleep(TASK_INTERVAL_SECONDS)
            market = task["market"].upper()
            sku = task["sku"]
            url = task["url"]
            postal_code = postal_code_for_market(market)
            print(f"\nSKU: {market} {sku}")
            location_error = ""
            if located_market != market:
                await executor.execute("goto", session, url=url)
                await executor.execute(
                    "wait",
                    session,
                    state="domcontentloaded",
                    timeout=20000,
                )
                location = await apply_market_location(
                    executor,
                    session,
                    url,
                    postal_code,
                )
                if location.success:
                    located_market = market
                else:
                    location_error = location.error or "set_location failed"

            item = await run_sku(
                executor,
                session,
                market,
                sku,
                url,
                postal_code,
                output_dir,
            )
            if location_error:
                item["error"] = (
                    location_error
                    if not item["error"]
                    else f"{location_error}; {item['error']}"
                )
                item["success"] = False
            items.append(item)
            pending_alerts.append(item)
            if mq_send_mode != "batch":
                await send_alerts([item], mq_send_mode)
        if mq_send_mode == "batch":
            await send_alerts(pending_alerts, mq_send_mode)
    finally:
        await bm.close()

    summary = summarize(items)
    print("\nSUMMARY:", json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":

    show_browser = SHOW_BROWSER or "--show-browser" in sys.argv[1:]
    mq_send_mode = "batch" if "--mq-batch" in sys.argv[1:] else MQ_SEND_MODE
    asyncio.run(main(show_browser=show_browser, mq_send_mode=mq_send_mode))
