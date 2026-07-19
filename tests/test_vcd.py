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


def test_shared_identifier_updates_all_signal_aliases(tmp_path: Path):
    path = tmp_path / "aliases.vcd"
    path.write_text(
        """$timescale 1ns $end
$scope module tb_top $end
$scope module bus $end
$var wire 8 ! data [7:0] $end
$upscope $end
$scope module dut $end
$var wire 8 ! data [7:0] $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b00000000 !
#5
b10100101 !
""",
        encoding="utf-8",
    )

    data = parse_vcd(path)
    interface_data = data.signal("tb_top.bus.data")
    dut_data = data.signal("tb_top.dut.data")

    assert interface_data is not None
    assert dut_data is not None
    assert interface_data.changes == dut_data.changes
    assert value_at(interface_data, 5) == "10100101"
