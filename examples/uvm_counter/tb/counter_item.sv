class counter_item extends uvm_sequence_item;
    rand bit       enable;
         bit [3:0] count;

    // A small weighted constraint that works with Verilator's Z3 backend.
    constraint c_enable_bias {
        enable dist {1'b1 := 4, 1'b0 := 1};
    }

    `uvm_object_utils_begin(counter_item)
        `uvm_field_int(enable, UVM_DEFAULT)
        `uvm_field_int(count,  UVM_DEFAULT | UVM_NOCOMPARE)
    `uvm_object_utils_end

    function new(string name = "counter_item");
        super.new(name);
    endfunction

    function string convert2string();
        return $sformatf("enable=%0b count=0x%0h", enable, count);
    endfunction
endclass
