#pragma once
#include <stdint.h>

template<int W>
struct ap_int {
    int64_t val;
    ap_int() : val(0) {}
    ap_int(int64_t v) : val(v) {}
    ap_int& operator=(int64_t v) { val = v; return *this; }
    ap_int operator+(ap_int o) const { return val + o.val; }
    ap_int operator*(ap_int o) const { return val * o.val; }
    ap_int& operator+=(ap_int o) { val += o.val; return *this; }
    ap_int operator>>(int s) const { return val >> s; }
    bool operator!=(ap_int o) const { return val != o.val; }
    int64_t to_int() const { return val; }
};
