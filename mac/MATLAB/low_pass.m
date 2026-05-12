close all;
fs = 100*10^3;              % sample at 100 kHz
fc = 10*10^3;               % cutoff at 10 kHz

Wn = fc/(fs/2);             % normalize to use fir1()

N = 63;                     % filter order

b = fir1(N,Wn,'low');       % tap coefficients
numTaps = length(b);

N_samples = 4096;
t = (0:N_samples-1) / fs;
%t = 0:1/fs:10e-3;           % 10 ms -> 1000 samples at fs = 100 kHz
x = 0.5*sin(2*pi*5*10^3*t);     % 5 kHz
y = 0.5*sin(2*pi*20*10^3*t);    % 20 kHz
z = x + y;

out = filter(b, 1, z);

%out_steady = out_fixed(N/2+1:end);
%z_steady   = z(N/2+1:end);

F1 = fimath(...
    'RoundMode','Nearest',...
    'OverflowMode','Saturate',...
    'ProductMode','SpecifyPrecision',...
    'ProductWordLength',32,...
    'ProductFractionLength',30,...
    'SumMode','SpecifyPrecision',...
    'SumWordLength',40,...
    'SumFractionLength',30);

% taps
b_fixed = fi(b, 1, 16, 15, 'fimath', F1);
% input samples
z_fixed = fi(z, 1, 16, 15, 'fimath', F1);
% output samples with fixed point
out_fixed = filter(b_fixed, 1, z_fixed);

F2 = fimath(...
    'RoundMode','Nearest',...
    'OverflowMode','Saturate',...
    'SumMode','SpecifyPrecision',...
    'SumWordLength',16,...
    'SumFractionLength',15);
out_fixed_15 = fi(out_fixed, 1, 16, 15, 'fimath', F2);

figure;
subplot(4,1,1);
plot(t,x)
xlim([0 1e-3])
title('x');
xlabel('Time (s)');
ylabel('Amplitude');

subplot(4,1,2);
plot(t,y)
xlim([0 1e-3])
title('y');
xlabel('Time (s)');
ylabel('Amplitude');

subplot(4,1,3);
plot(t,z_fixed)
xlim([0 1e-3])
title('z');
xlabel('Time (s)');
ylabel('Amplitude');

subplot(4,1,4);
plot(t, out_fixed_15);
xlim([0 1e-3])
title('Filtered Signal');
xlabel('Time (s)');
ylabel('Amplitude');

N = length(z);
f = (0:N-1)*(fs/N);
Z = fft(z);
Out = fft(out);

half = 1:floor(N/2);        % only keep first half (0 to fs/2)

figure;
subplot(2,1,1);
plot(f(half), abs(Z(half)));
xlabel('Frequency (Hz)');
ylabel('|Z(f)|');

subplot(2,1,2);
plot(f(half), abs(Out(half)));
xlabel('Frequency (Hz)');
ylabel('|Out(f)|');

err = out - double(out_fixed);
SNR = 10*log10(sum(double(out).^2)/sum(err.^2));
disp(SNR);

fid = fopen('taps.mem','w');
for k = 1:length(b_fixed)
    hex_str = hex(b_fixed(k));
    fprintf(fid,'%s\n', hex_str);
end
fclose(fid);

fid = fopen('input.mem','w');
for k = 1:length(z_fixed)
    hex_str = hex(z_fixed(k));
    fprintf(fid,'%s\n', hex_str);
end
fclose(fid);

fid = fopen('output.mem','w');
for k = 1:length(out_fixed)
    hex_str = hex(out_fixed(k)); 
    fprintf(fid,'%s\n', hex_str);
end
fclose(fid);

err = out - double(out_fixed_15);
SNR = 10*log10(sum(double(out).^2)/sum(err.^2));
disp(SNR);

fid = fopen('output_15.mem','w');
for k = 1:length(out_fixed_15)
    hex_str = hex(out_fixed_15(k)); 
    fprintf(fid,'%s\n', hex_str);
end
fclose(fid);
