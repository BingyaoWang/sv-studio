class counter_monitor extends uvm_monitor;
    `uvm_component_utils(counter_monitor)

    virtual counter_if vif;
    uvm_analysis_port #(counter_item) observed;

    function new(string name, uvm_component parent);
        super.new(name, parent);
        observed = new("observed", this);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual counter_if)::get(this, "", "vif", vif))
            `uvm_fatal("NOVIF", "counter_if was not placed in the config database")
    endfunction

    task run_phase(uvm_phase phase);
        counter_item sample;
        forever begin
            @(vif.monitor_cb);
            if (vif.monitor_cb.rst_n) begin
                sample = counter_item::type_id::create("sample");
                sample.enable = vif.monitor_cb.enable;
                sample.count  = vif.monitor_cb.count;
                observed.write(sample);
                `uvm_info("MON", {"Observed ", sample.convert2string()}, UVM_HIGH)
            end
        end
    endtask
endclass
