class counter_driver extends uvm_driver #(counter_item);
    `uvm_component_utils(counter_driver)

    virtual counter_if vif;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual counter_if)::get(this, "", "vif", vif))
            `uvm_fatal("NOVIF", "counter_if was not placed in the config database")
    endfunction

    task reset_dut();
        vif.driver_cb.rst_n  <= 1'b0;
        vif.driver_cb.enable <= 1'b0;
        repeat (2) @(vif.driver_cb);
        vif.driver_cb.rst_n <= 1'b1;
        `uvm_info("DRV", "Reset complete", UVM_MEDIUM)
    endtask

    task run_phase(uvm_phase phase);
        counter_item request;
        reset_dut();
        forever begin
            seq_item_port.get_next_item(request);
            @(vif.driver_cb);
            vif.driver_cb.enable <= request.enable;
            `uvm_info("DRV", {"Driving ", request.convert2string()}, UVM_HIGH)
            seq_item_port.item_done();
        end
    endtask
endclass
