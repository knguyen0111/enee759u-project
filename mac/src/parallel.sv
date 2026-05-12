// parallel multiples, pipelined additions
/*

1. shift in new samples
2. multiply in parallel
3. adder tree lvl 0
...
8. adder tree lvl 5
9. truncate to q1.15

9 cycles until pipeline fills, then 1 cycle produces 1 sample

*/
`timescale 1ns / 1ps

module fir #(parameter WIDTH = 16, ACC_WIDTH = 40, NTAPS = 64) (
    input wire clk,
    input wire rst_n,
    input wire signed [WIDTH-1:0] sample_in,
    input wire valid_in,

    output reg signed [WIDTH-1:0] sample_out,
    output wire valid_out,
    output wire ready
    );

    assign ready = 1'b1;    // keep interface same

    localparam NLEVELS = $clog2(NTAPS), PIPELINE_STAGES = NLEVELS + 3;

    // load taps
    reg signed [WIDTH-1:0] taps [0:NTAPS-1];
    initial begin
        $readmemh("io/taps.mem", taps);
    end

    // 1. shift in samples
    reg signed [WIDTH-1:0] shift [NTAPS-1:0];
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < NTAPS; i++) begin
                shift[i] <= 0;
            end
        end else begin
          if (valid_in) begin
                shift[0] <= sample_in;
                for (int i = 1; i < NTAPS; i++)
                    shift[i] <= shift[i-1];
            end
        end
    end

    // 2. multiply in parallel
    reg signed [ACC_WIDTH-1:0] prod [NTAPS-1:0];
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < NTAPS; i++) begin
                prod[i] <= 0;
            end
        end else begin
            for (int i = 0; i < NTAPS; i++) begin
            	prod[i] <= taps[NTAPS-1-i] * shift[i];
            end
        end
    end

    // 3. to 8. adder tree
    reg signed [ACC_WIDTH-1:0] sum [0:NLEVELS-1][0:NTAPS-1];
    genvar level, i;
    generate
        for (level = 0; level < NLEVELS; level++) begin : GEN_LEVEL
            for (i = 0; i < (NTAPS >> (level + 1)); i++) begin : GEN_ADD
                always @(posedge clk or negedge rst_n) begin
                    if (!rst_n)
                        sum[level][i] <= 0;
                    else begin
                        if (level == 0) begin
                            sum[0][i] <= prod[i*2] + prod[i*2+1];
                        end else begin
                            sum[level][i] <= sum[level-1][i*2] + sum[level-1][i*2+1];
                        end
                    end
                end
            end
        end
    endgenerate

    // propagate valid signal
    reg [PIPELINE_STAGES-1:0] sum_valid;
    assign valid_out = sum_valid[PIPELINE_STAGES-1];
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sum_valid <= 0;
        end else begin
            sum_valid <= {sum_valid[PIPELINE_STAGES-2:0], valid_in};    
        end
    end

    // 9. truncate to q1.15
    wire signed [ACC_WIDTH-1:0] sum_shift = (sum[NLEVELS-1][0] + 16'h4000) >> 15;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_out <= 0;
        end else begin
            if (valid_out) begin
                sample_out <= sum_shift[WIDTH-1:0];
            end
        end
    end
    
endmodule
