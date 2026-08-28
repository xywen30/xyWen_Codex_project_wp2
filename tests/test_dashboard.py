from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


pytestmark = pytest.mark.skip(reason="Windows 映射盘下 Streamlit AppTest 与 pyarrow 存在线程级原生崩溃；使用独立服务进程验收")


def test_dashboard_home_renders_without_exception():
    app_path = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "📡 Ozon 家居爆品趋势雷达"
    assert any("当前为 REAL" in item.value for item in app.success)
    assert len(app.metric) >= 8
