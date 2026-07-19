class counter_base_test extends uvm_test;
    `uvm_component_utils(counter_base_test)

    counter_env env;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        env = counter_env::type_id::create("env", this);
        `uvm_info("TEST", "Build phase created the counter environment", UVM_MEDIUM)
    endfunction
endclass


class counter_smoke_test extends counter_base_test;
    `uvm_component_utils(counter_smoke_test)

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    task run_phase(uvm_phase phase);
        counter_smoke_sequence sequence;
        phase.raise_objection(this, "counter smoke sequence running");
        sequence = counter_smoke_sequence::type_id::create("sequence");
        sequence.start(env.agent.sequencer);
        repeat (3) @(env.agent.monitor.vif.monitor_cb);
        `uvm_info("TEST", "Counter smoke test passed", UVM_LOW)
        phase.drop_objection(this, "counter smoke sequence complete");
    endtask
endclass


class counter_pause_test extends counter_base_test;
    `uvm_component_utils(counter_pause_test)

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    task run_phase(uvm_phase phase);
        counter_pause_sequence sequence;
        phase.raise_objection(this);
        sequence = counter_pause_sequence::type_id::create("sequence");
        sequence.start(env.agent.sequencer);
        repeat (3) @(env.agent.monitor.vif.monitor_cb);
        phase.drop_objection(this);
    endtask
endclass


class counter_random_test extends counter_base_test;
    `uvm_component_utils(counter_random_test)

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    task run_phase(uvm_phase phase);
        counter_random_sequence sequence;
        phase.raise_objection(this, "constrained-random sequence running");
        sequence = counter_random_sequence::type_id::create("sequence");
        sequence.start(env.agent.sequencer);
        repeat (3) @(env.agent.monitor.vif.monitor_cb);
        `uvm_info("TEST", "Constrained-random counter test passed", UVM_LOW)
        phase.drop_objection(this, "constrained-random sequence complete");
    endtask
endclass
