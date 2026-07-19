`timescale 1ns/1ps

module tb_top;
    logic [7:0] a;
    logic [7:0] b;
    logic [7:0] result;

    simple_adder dut (.*);

    initial begin
        $dumpfile(".svstudio/waves.vcd");
        $dumpvars(0, tb_top);
        a = 8'd1;  b = 8'd2;  #10;
        a = 8'd10; b = 8'd20; #10;
        a = 8'hff; b = 8'd1;  #10;
        $finish;
    end
endmodule
