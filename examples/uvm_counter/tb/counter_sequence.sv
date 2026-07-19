class counter_smoke_sequence extends uvm_sequence #(counter_item);
    `uvm_object_utils(counter_smoke_sequence)

    function new(string name = "counter_smoke_sequence");
        super.new(name);
    endfunction

    task body();
        counter_item request;
        `uvm_info("SEQ", "Starting 8 directed transactions", UVM_MEDIUM)
        repeat (8) begin
            request = counter_item::type_id::create("request");
            start_item(request);
            // Directed stimulus keeps this first lab compatible with the
            // current open-source UVM toolchain. Try randomize() after it works.
            request.enable = 1'b1;
            finish_item(request);
        end
    endtask
endclass


class counter_pause_sequence extends uvm_sequence #(counter_item);
    `uvm_object_utils(counter_pause_sequence)

    function new(string name = "counter_pause_sequence");
        super.new(name);
    endfunction

    task body();
        counter_item request;
        for (int index = 0; index < 12; index++) begin
            request = counter_item::type_id::create($sformatf("request_%0d", index));
            start_item(request);
            request.enable = (index % 4 != 2);
            finish_item(request);
        end
    endtask
endclass


class counter_random_sequence extends uvm_sequence #(counter_item);
    `uvm_object_utils(counter_random_sequence)

    function new(string name = "counter_random_sequence");
        super.new(name);
    endfunction

    task body();
        counter_item request;
        `uvm_info("RANDOM", "Starting 20 constrained-random transactions", UVM_LOW)
        repeat (20) begin
            request = counter_item::type_id::create("request");
            start_item(request);
            if (!request.randomize())
                `uvm_fatal("RANDFAIL", "counter_item constraints are unsatisfiable")
            finish_item(request);
        end
    endtask
endclass
