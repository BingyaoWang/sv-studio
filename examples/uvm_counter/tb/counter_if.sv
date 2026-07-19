`timescale 1ns/1ps

interface counter_if(input logic clk);
    logic       rst_n;
    logic       enable;
    logic [3:0] count;

    // The driver changes inputs away from the active clock edge.
    clocking driver_cb @(negedge clk);
        output rst_n;
        output enable;
        input  count;
    endclocking

    // The monitor samples a stable, race-free view at each positive edge.
    clocking monitor_cb @(posedge clk);
        input rst_n;
        input enable;
        input count;
    endclocking
endinterface
