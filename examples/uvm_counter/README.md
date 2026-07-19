# UVM Counter Lab

This project is a compact, complete UVM environment for a 4-bit counter.

## Learning order

1. `rtl/counter.sv` — the design under test.
2. `tb/counter_if.sv` — signal-level connection and clocking blocks.
3. `tb/counter_item.sv` — the transaction object.
4. `tb/counter_sequence.sv` — stimulus generation.
5. `tb/counter_driver.sv` — transaction-to-pin conversion.
6. `tb/counter_monitor.sv` — pin-to-transaction observation.
7. `tb/counter_scoreboard.sv` — self-checking reference model.
8. `tb/counter_agent.sv` and `tb/counter_env.sv` — reusable hierarchy.
9. `tb/counter_test.sv` — test policy and objections.
10. `tb/tb_top.sv` — HDL/UVM connection and test launch.

Press **F5** in SV Studio to run. Without a simulator, the Demo Engine walks
through the same flow and generates a VCD waveform. For real compilation, open
**Project → Toolchains** and set up the free Verilator + UVM toolchain.

Choose `counter_random_test` to exercise `rand`, a weighted `dist` constraint,
and reproducible seeds. Press **F6** to run it in debug mode: the test stops on
the first UVM error and records the constraint solver exchange for diagnosis.
