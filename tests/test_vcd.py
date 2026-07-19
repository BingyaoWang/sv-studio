from pathlib import Path

from svstudio.vcd import parse_vcd, value_at, write_demo_vcd


def test_demo_vcd_can_be_parsed(tmp_path: Path):
    path = tmp_path / "demo.vcd"
    write_demo_vcd(path)
    data = parse_vcd(path)

    assert data.timescale == "1ns"
    assert data.end_time == 125
    assert {signal.name for signal in data.signals} == {
        "tb_top.clk",
        "tb_top.rst_n",
        "tb_top.enable",
        "tb_top.count",
    }
    count = data.signal("tb_top.count")
    assert count is not None
    assert value_at(count, 20) == "0000"
    assert value_at(count, 120) == "0111"
