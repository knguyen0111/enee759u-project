`timescale 1ns / 1ps

module parallel_tb;
parameter WIDTH = 16, DEPTH = 32, ACC_WIDTH = 40, NTAPS = 64, NSAMPLES = 4096;
reg clk, rst_n;

reg signed [WIDTH-1:0] sample_in;
reg valid_in;
reg ready;
wire signed [WIDTH-1:0] sample_out;
wire valid_out;

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
        in_idx <= 0;
      	valid_in <= 0;
    end else if (in_idx < NSAMPLES) begin
        sample_in <= mem1[in_idx];
        in_idx <= in_idx + 1;
      	valid_in <= 1;
    end 
end

integer match = 1;
  
// compare output samples with expected values
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        out_idx <= 0;
      	match <= 1;
    end else if (valid_out) begin
      $display("[%0t] sample_out = %h, mem2[%0d] = %h, match: %b", $time, sample_out, out_idx, mem2[out_idx], sample_out == mem2[out_idx]);
      	if (sample_out != mem2[out_idx])
            match <= 0;
        out_idx <= out_idx + 1;
    end
    if (out_idx == NSAMPLES-1) begin
      	if (match) 
          $display("PASS");
      	else 
          $display("FAIL");
        $finish;
    end
end

endmodule
