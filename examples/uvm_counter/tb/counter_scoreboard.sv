class counter_scoreboard extends uvm_scoreboard;
    `uvm_component_utils(counter_scoreboard)

    uvm_analysis_imp #(counter_item, counter_scoreboard) analysis_export;
    bit [3:0] expected_count;
    int unsigned matches;

    function new(string name, uvm_component parent);
        super.new(name, parent);
        analysis_export = new("analysis_export", this);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        expected_count = '0;
        matches = 0;
    endfunction

    function void write(counter_item sample);
        if (sample.count !== expected_count) begin
            `uvm_error("MISMATCH", $sformatf(
                "expected=0x%0h actual=0x%0h enable=%0b",
                expected_count, sample.count, sample.enable
            ))
        end else begin
            matches++;
            `uvm_info("MATCH", $sformatf(
                "expected=%0d actual=%0d", expected_count, sample.count
            ), UVM_MEDIUM)
        end
        if (sample.enable)
            expected_count++;
    endfunction

    function void report_phase(uvm_phase phase);
        if (matches == 0)
            `uvm_error("EMPTY", "The scoreboard did not receive any samples")
        else
            `uvm_info("SCOREBOARD", $sformatf("Checked %0d matching samples", matches), UVM_LOW)
    endfunction
endclass
