// cycle 0 wasted on idle
// cycles 1-64 multiply
// cycle 65 accumulates
// cycle 66 rounds & truncates to q1.15
// cycle 67 latches output
// ------------------------------------
// total 68 cycles per sample
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

    // load taps
    reg signed [WIDTH-1:0] taps [0:NTAPS-1];
    initial begin
        $readmemh("io/taps.mem", taps);
    end
   
    // counter = 0, acc = 0, ready = 1, valid_in = 1, busy = 0
    // counter = 1, ready = 0, valid_in = 0, multiply, busy = 1
    // counter = 2, accumulate and multiply 
    // counter = 64,accumulate and multiply
    // counter = 65, accumulate
    // 66 truncation
    // 67 valid_out = 1, reset counter to 0
    
    assign ready = (counter == 0);
    wire busy = !ready;
    reg [$clog2(NTAPS):0] counter;                        
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin 
            counter <= 0;
        end else if (ready && valid_in) begin
            counter <= 1;
        end else if (busy) begin
            if (counter == NTAPS+3) begin
                counter <= 0;
            end else
                counter <= counter + 1;
        end
    end


    // shift in samples
    reg signed [WIDTH-1:0] shift [NTAPS-1:0];
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < NTAPS; i++) begin
                shift[i] <= 0;
            end
        end else begin
            if (valid_in && ready) begin
                shift[0] <= sample_in;
                for (int i = 1; i < NTAPS; i++)
                    shift[i] <= shift[i-1];
            end 
        end
    end

    // multiply
    reg signed [ACC_WIDTH-1:0] prod; 
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            prod <= 0;
        end else if (busy && (counter >= 1) && (counter <= NTAPS)) begin
            prod <= taps[NTAPS-counter] * shift[counter-1];
        end
    end

    // addition
    reg signed [ACC_WIDTH-1:0] sum; 
    always @ (posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sum <= 0;
        end else begin
            if (ready)
                sum <= 0;
            else if (busy && (counter >= 2) && (counter <= NTAPS+1)) 
                sum <= sum + prod;
        end
    end

    // truncate to q1.15
    wire signed [ACC_WIDTH-1:0] sum_shift = (sum + 16'h4000) >> 15;
    //wire signed [ACC_WIDTH-1:0] sum_shift = (sum + {{(ACC_WIDTH-16){1'b0}}, 16'h4000}) >>> 15;
    assign valid_out = counter == NTAPS+3;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_out <= 0;
        end else begin
            if (counter == NTAPS+2) begin
                sample_out <= sum_shift[WIDTH-1:0];
            end
        end
    end
    
endmodule
