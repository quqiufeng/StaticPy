// easing.cpp — Robert Penner 缓动（in/out/inout × quad/cubic/quart/quint/sine/expo/circ/back/elastic/bounce）
#include "easing.h"
#include <cstring>
#include <cmath>
#include <string>

namespace {
double pi() { return 3.14159265358979323846; }
// 基础 in 形
double f_quad(double t){ return t*t; }
double f_cubic(double t){ return t*t*t; }
double f_quart(double t){ return t*t*t*t; }
double f_quint(double t){ return t*t*t*t*t; }
double f_sine(double t){ return 1 - cos(t*pi()/2); }
double f_expo(double t){ return t==0 ? 0 : pow(2, 10*t-10); }
double f_circ(double t){ return 1 - sqrt(1 - t*t); }
double f_back(double t){ double c1=1.70158, c3=c1+1; return c3*t*t*t - c1*t*t; }
double f_elastic(double t){ double c4=(2*pi())/3; return t==0?0:t==1?1:-pow(2,10*t-10)*sin((t*10-10.75)*c4); }
double f_bounce(double t){
    double n1=7.5625, d1=2.75;
    if (t < 1/d1) return n1*t*t;
    else if (t < 2/d1) { t -= 1.5/d1; return n1*t*t + 0.75; }
    else if (t < 2.5/d1) { t -= 2.25/d1; return n1*t*t + 0.9375; }
    else { t -= 2.625/d1; return n1*t*t + 0.984375; }
}
typedef double (*Fn)(double);
Fn base(const std::string& k) {
    if (k=="quad") return f_quad; if (k=="cubic") return f_cubic; if (k=="quart") return f_quart;
    if (k=="quint") return f_quint; if (k=="sine") return f_sine; if (k=="expo") return f_expo;
    if (k=="circ") return f_circ; if (k=="back") return f_back; if (k=="elastic") return f_elastic;
    if (k=="bounce") return f_bounce; return nullptr;
}
}

extern "C" {

int ease_known(const char* name) {
    std::string n = name ? name : "";
    if (n == "linear") return 1;
    std::string kind;
    if (n.rfind("easeInOut", 0) == 0) kind = "inout";
    else if (n.rfind("easeIn", 0) == 0) kind = "in";
    else if (n.rfind("easeOut", 0) == 0) kind = "out";
    else return 0;
    size_t plen = (kind == "in") ? 6 : (kind == "out") ? 7 : 9;
    std::string b = n.substr(plen);
    return base(b) != nullptr;
}

double ease(const char* name, double t) {
    std::string n = name ? name : "linear";
    if (n == "linear") return t;
    // 解析 easeIn/Out/InOut + 基础
    std::string kind; Fn f = nullptr;
    if (n.rfind("easeInOut", 0) == 0) kind = "inout";
    else if (n.rfind("easeIn", 0) == 0) kind = "in";
    else if (n.rfind("easeOut", 0) == 0) kind = "out";
    else return t;
    size_t plen = (kind == "in") ? 6 : (kind == "out") ? 7 : 9;
    std::string b = n.substr(plen);
    f = base(b); if (!f) return t;
    if (kind == "in") return f(t);
    if (kind == "out") return 1 - f(1 - t);
    // inout
    return t < 0.5 ? f(2*t)/2 : 1 - f(2 - 2*t)/2;
}

}  // extern "C"
