`timescale 1ns/1ps

module simple_adder (
    input  logic [7:0] a,
    input  logic [7:0] b,
    output logic [7:0] result
);
    assign result = a + b;
endmodule
