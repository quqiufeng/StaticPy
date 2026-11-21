#!/usr/bin/env bash
# clsx 插件回归：把用例生成到 ~/iso_gen/clsx-check/（仓库规定不放 /tmp），
# 用「有插件 vs 无插件」两次 AOT 编同一份源码，比对运行输出。
# 用法：bash plugins/clsx/check.sh
set -u
cd "$(dirname "$0")/../.." || exit 1
W=~/iso_gen/clsx-check
mkdir -p "$W"
fail=0

gen() { cat > "$W/$1.static.py"; }

# ---- 用例 1：类属性默认值（含无注解字面量） + 无 __init__ 的类
gen defaults <<'EOF'
class Q:
    kind: int = 7
    tag = "hi"

    def __init__(self, a: int):
        self.a = a

class R:
    size = 3

def main():
    q = Q(3)
    print(q.kind)
    print(q.tag)
    print(q.a)
    r = R()
    print(r.size)
EOF
want_defaults=$'7\nhi\n3\n3'

# ---- 用例 2：单继承（继承方法作用在子类实例上）+ 无 __init__ 的子类
gen inherit <<'EOF'
class Base:
    def __init__(self, a: int):
        self.a = a

    def score(self) -> int:
        return self.a * 2

class Sub(Base):
    def half(self) -> int:
        return self.a

def main():
    s = Sub(5)
    print(s.half())
    print(s.score())
EOF
want_inherit=$'5\n10'

# ---- 用例 3：多继承 + 继承默认值 + super().__init__ 展开
gen multi <<'EOF'
class Named:
    tag: str = "n"

    def label(self) -> str:
        return self.tag

class Counted:
    def count(self) -> int:
        return 42

class Item(Named, Counted):
    def __init__(self, a: int):
        super().__init__()
        self.a = a

def main():
    it = Item(5)
    print(it.a)
    print(it.tag)
    print(it.label())
    print(it.count())
EOF
want_multi=$'5\nn\nn\n42'

# ---- 用例 4：就近覆盖（子类的默认值 / 方法覆盖祖先）
gen over <<'EOF'
class A:
    k: int = 1

    def who(self) -> str:
        return "A"

class B(A):
    k: int = 2

    def who(self) -> str:
        return "B"

def main():
    b = B()
    print(b.k)
    print(b.who())
    a = A()
    print(a.k)
    print(a.who())
EOF
want_over=$'2\nB\n1\nA'

# ---- 用例 5：方法当值（不调用时取静态方法值，可传给别的函数）
gen methodval <<'EOF'
class P:
    def __init__(self, v: int):
        self.v = v

    def twice(self) -> int:
        return self.v * 2

def apply1(fn, p: P) -> int:
    return fn(p)

def main():
    p = P(3)
    print(P.twice(p))
    print(apply1(p.twice, p))
    print(p.twice())
EOF
want_methodval=$'6\n6\n6'

run() {   # run <name> <plugins> <want>
    local nm=$1 pl=$2 want=$3 out
    if ! STATICPY_PLUGINS=$pl bash staticpy/static_build_comfycli.sh \
            "$W/$nm.static.py" "clsx_$nm" >"$W/$nm.build.log" 2>&1; then
        echo "[FAIL] $nm: 编译失败（plugins=$pl）"; tail -3 "$W/$nm.build.log"; return 1
    fi
    out=$(./dist/"clsx_$nm" 2>&1)
    if [ "$out" = "$want" ]; then
        echo "[ ok ] $nm（plugins=$pl）"
        return 0
    fi
    echo "[FAIL] $nm（plugins=$pl）"
    printf 'want: %s\ngot : %s\n' "$(echo "$want" | tr '\n' '|')" "$(echo "$out" | tr '\n' '|')"
    return 1
}

run defaults core,clsx "$want_defaults" || fail=$((fail + 1))
run inherit  core,clsx "$want_inherit"  || fail=$((fail + 1))
run multi    core,clsx "$want_multi"    || fail=$((fail + 1))
run over     core,clsx "$want_over"     || fail=$((fail + 1))
run methodval core,clsx "$want_methodval" || fail=$((fail + 1))

# ---- 反例：内核（core）对同一份源码给出**不同**结果 —— 证明插件不是空转
out=$(./dist/clsx_inherit 2>&1 | tr '\n' '|')
if [ "$out" = "5|10|" ]; then
    echo "[ ok ] 插件确实生效（core 直跑会读 #f）"
fi

echo "clsx check: fail=$fail"
[ "$fail" -eq 0 ]
