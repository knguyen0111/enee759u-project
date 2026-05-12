`timescale 1ns / 1ps

module iterative_tb;
parameter WIDTH = 16, DEPTH = 32, ACC_WIDTH = 40, NTAPS = 64, NSAMPLES = 4096;

reg clk, rst_n;
reg signed [WIDTH-1:0] sample_in;
reg valid_in;

wire signed [WIDTH-1:0] sample_out;
wire valid_out;
wire ready;

fir #(WIDTH, ACC_WIDTH, NTAPS) dut (clk, rst_n, sample_in, valid_in, sample_out, valid_out, ready);

reg signed [WIDTH-1:0] mem1 [0:NSAMPLES-1];   // input samples
reg signed [WIDTH-1:0] mem2 [0:NSAMPLES-1];   // output samples

initial begin
    $readmemh("io/input.mem", mem1);
    $readmemh("io/output_15.mem", mem2);
end

always #5 clk = ~clk;

initial begin
    clk = 0;
    rst_n = 0;
    repeat (2) @(posedge clk);
    rst_n = 1;
end

integer in_idx = 0;
integer out_idx = 0;

// feed input samples to filter
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        valid_in <= 0;
        sample_in <= 0;
    end else begin
        if (!valid_in && ready && in_idx < NSAMPLES) begin
            sample_in <= mem1[in_idx];
            valid_in <= 1;
            in_idx <= in_idx + 1;
        end else begin
            sample_in <= 0;
            valid_in <= 0;
        end
    end
end


integer match = 1;

//reg valid_out_d;

// compare output samples with expected values
always @(posedge clk or negedge rst_n) begin
//    valid_out_d <= valid_out;
//    if (!rst_n) begin
//        valid_out_d <= 0;
//    if (valid_out && out_idx < 3) begin
//        $display("%d", out_idx);    
if (valid_out) begin
    $display("[%0t] sample_out = %h, mem2[%0d] = %h, match: %b", $time, sample_out, out_idx, mem2[out_idx], sample_out == mem2[out_idx]);
    if (sample_out != mem2[out_idx]) 
        match = 0;
    out_idx = out_idx + 1;
    
    if (out_idx == NSAMPLES-1) begin
      	if (match) 
          $display("PASS");
      	else 
          $display("FAIL");
    end
end
end

always @(posedge clk) begin
/*    if (dut.ready && out_idx < 3)
        $display("prod=%h sum=%h", dut.prod, dut.sum);
        $display("counter=%0d shift[0]=%h shift[1]=%h shift[2]=%h", 
    dut.counter, dut.shift[0], dut.shift[1], dut.shift[2]);
        $display("valid_in=%b sample_in=%h ready=%b, busy=%b", 
     valid_in, sample_in, ready, dut.busy);
    if (out_idx > 2)
        $finish;
*/
    if (out_idx == NSAMPLES)
        $finish;
end

endmodule
