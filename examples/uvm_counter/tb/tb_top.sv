`timescale 1ns/1ps

import uvm_pkg::*;
`include "uvm_macros.svh"
`include "counter_if.sv"
`include "counter_item.sv"
`include "counter_sequence.sv"
`include "counter_driver.sv"
`include "counter_monitor.sv"
`include "counter_scoreboard.sv"
`include "counter_agent.sv"
`include "counter_env.sv"
`include "counter_test.sv"

module tb_top;
    logic clk = 1'b0;
    always #5ns clk = ~clk;

    counter_if counter_vif(clk);

    counter dut (
        .clk    (clk),
        .rst_n  (counter_vif.rst_n),
        .enable (counter_vif.enable),
        .count  (counter_vif.count)
    );

    initial begin
        $dumpfile(".svstudio/waves.vcd");
        $dumpvars(0, tb_top);
        uvm_config_db#(virtual counter_if)::set(null, "uvm_test_top.env.agent*", "vif", counter_vif);
        run_test();
    end
endmodule
